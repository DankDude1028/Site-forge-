import base64
import hashlib
import io
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import psycopg
import pytest

from siteforge import backups

KEY = b"k" * 32
DUMP = b"PGDMP" + b"fixture database rows\x00" * 100


def connection(database="fixture"):
    return backups.Connection("127.0.0.1", 5432, database, "fixture_user", "fixture_password", "disable")


@pytest.fixture
def client_tools(monkeypatch):
    calls = []

    @contextmanager
    def process(arguments, selected, timeout, *, stdin=None, stdout=None):
        calls.append({"arguments": arguments, "connection": selected, "timeout": timeout,
                      "plaintext": stdin.read() if stdin is not None else None})
        yield SimpleNamespace(stdout=io.BytesIO(DUMP))

    monkeypatch.setattr(backups, "_binary", lambda name, _: name)
    monkeypatch.setattr(backups, "_process", process)
    return calls


def saved(tmp_path, client_tools, *, selected=None):
    root = tmp_path / "backups"
    manifest = backups.backup(selected or connection(), root, key=KEY, key_id="fixture-key")
    return root, root / manifest["file"], manifest


@pytest.mark.parametrize("data", [DUMP, b"PGDMP" + os.urandom(2 * backups.CHUNK + 19)], ids=["small", "multi_chunk"])
def test_envelope_round_trip_authenticated_metadata_and_streamed_bytes(data):
    header = {"schema_version": 1, "backup_id": uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(),
              "key_id": "fixture-key", "nonce": os.urandom(12).hex(), "cipher": "AES-256-GCM",
              "source": connection().identity()}
    encrypted = io.BytesIO()
    measured = backups.encrypt_stream(io.BytesIO(data), encrypted, key=KEY, header=header, max_bytes=len(data))
    assert data not in encrypted.getvalue()
    encrypted.seek(0)
    restored = io.BytesIO()
    verified = backups.decrypt_stream(encrypted, restored, key=KEY, key_id="fixture-key", max_bytes=len(data))
    assert restored.getvalue() == data
    assert measured["dump_sha256"] == hashlib.sha256(data).hexdigest()
    assert verified == {**header, **measured}


def test_backup_manifest_has_checksums_times_unique_nonce_and_no_credentials(tmp_path, client_tools):
    root, archive, manifest = saved(tmp_path, client_tools)
    second = backups.backup(connection(), root, key=KEY, key_id="fixture-key")
    assert manifest["backup_id"] != second["backup_id"] and manifest["nonce"] != second["nonce"]
    assert manifest["archive_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert manifest["dump_sha256"] == hashlib.sha256(DUMP).hexdigest()
    assert datetime.fromisoformat(manifest["created_at"]).utcoffset() == timedelta(0)
    assert "fixture_password" not in json.dumps(manifest) and "fixture_user" not in json.dumps(manifest)
    assert client_tools[0]["arguments"] == ["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--no-password"]
    assert not list(root.glob("*.part"))


@pytest.mark.parametrize("uri", [
    "postgresql://user:password@db.example.test/database?sslmode=disable",
    "postgresql://user:password@db.example.test/database?sslmode=require",
    "postgresql://user:password@127.0.0.1/database?options=evil",
    "postgresql://user:password@127.0.0.1/database?host=elsewhere",
    "postgresql://user:password@127.0.0.1/unsafe%20database",
    "postgresql://user@127.0.0.1/database", "sqlite:///not-postgresql",
])
def test_uri_rejects_remote_unverified_tls_and_implicit_or_injected_settings(monkeypatch, uri):
    monkeypatch.setenv("FIXTURE_DB_URI", uri)
    with pytest.raises(backups.BackupError) as error:
        backups.connection_from_env("FIXTURE_DB_URI")
    assert "password" not in str(error.value)


def test_uri_parsing_tls_and_environment_are_explicit_without_secret_arguments(monkeypatch):
    monkeypatch.setenv("FIXTURE_DB_URI", "postgresql+psycopg://fixture_user:private%40pass@db.example.test:5433/database?sslmode=verify-full")
    monkeypatch.setenv("PGHOSTADDR", "203.0.113.99")
    monkeypatch.setenv("PGOPTIONS", "unsafe")
    monkeypatch.setenv("UNRELATED_PROVIDER_TOKEN", "must-not-enter-child")
    monkeypatch.setenv("SITEFORGE_BACKUP_KEY", "must-not-enter-child")
    selected = backups.connection_from_env("FIXTURE_DB_URI")
    assert selected.sslmode == "verify-full" and selected.port == 5433
    assert "private" not in repr(selected)
    env = selected.environment()
    assert env["PGPASSWORD"] == "private@pass" and env["PGHOST"] == "db.example.test"
    assert not {"PGHOSTADDR", "PGOPTIONS", "UNRELATED_PROVIDER_TOKEN", "SITEFORGE_BACKUP_KEY"} & env.keys()


def test_key_decoding_exact_256_bits_and_invalid_identifiers_fail_early(tmp_path, monkeypatch, client_tools):
    monkeypatch.setenv("SITEFORGE_BACKUP_KEY", base64.b64encode(KEY).decode())
    assert backups.key_from_env() == KEY
    for encoded in ("not base64!", base64.b64encode(b"short").decode()):
        monkeypatch.setenv("SITEFORGE_BACKUP_KEY", encoded)
        with pytest.raises(backups.BackupError):
            backups.key_from_env()
    for key, identifier in ((b"short", "fixture"), (KEY, "../../outside")):
        with pytest.raises(backups.BackupError):
            backups.backup(connection(), tmp_path / "backups", key=key, key_id=identifier)
    assert not client_tools


def test_dump_failure_size_limit_and_uuid_collision_do_not_replace_files(tmp_path, client_tools, monkeypatch):
    root, archive, _ = saved(tmp_path, client_tools)
    original = archive.read_bytes()
    with pytest.raises(backups.BackupError, match="size"):
        backups.backup(connection(), root, key=KEY, key_id="fixture-key", max_bytes=5)
    assert archive.read_bytes() == original and not list(root.glob("*.part"))
    identifier = UUID(hex="a" * 32)
    monkeypatch.setattr(backups, "uuid4", lambda: identifier)
    preexisting_part = root / f"siteforge-backup-{identifier.hex}.part"
    preexisting_part.write_bytes(b"do not remove an unowned partial file")
    with pytest.raises(FileExistsError):
        backups.backup(connection(), root, key=KEY, key_id="fixture-key")
    assert preexisting_part.read_bytes() == b"do not remove an unowned partial file"
    assert archive.read_bytes() == original


@pytest.mark.parametrize("damage", ["ciphertext", "tag", "header", "manifest", "wrong_key", "wrong_key_id", "oversize"])
def test_every_authentication_failure_precedes_any_database_connection_or_restore(tmp_path, client_tools, monkeypatch, damage):
    root, archive, manifest = saved(tmp_path, client_tools)
    client_tools.clear()
    key, key_id, maximum = KEY, "fixture-key", backups.DEFAULT_MAX_BYTES
    if damage in {"ciphertext", "tag", "header"}:
        data = bytearray(archive.read_bytes())
        offset = -25 if damage == "ciphertext" else (-1 if damage == "tag" else data.index(b"fixture-key"))
        data[offset] ^= 1
        archive.write_bytes(data)
    elif damage == "manifest":
        manifest["created_at"] = "2000-01-01T00:00:00+00:00"
        backups._manifest_path(archive).write_text(json.dumps(manifest))
    elif damage == "wrong_key":
        key = b"x" * 32
    elif damage == "wrong_key_id":
        key_id = "different-key"
    else:
        maximum = 5
    def forbidden(*args, **kwargs):
        pytest.fail("Unauthenticated data must never reach any database operation")
    monkeypatch.setattr(backups.psycopg, "connect", forbidden)
    target = connection("siteforge_restore_" + uuid4().hex)
    with pytest.raises(backups.BackupError):
        backups.restore(archive, root, target, replace(target, database="postgres"), key=key,
                        key_id=key_id, max_bytes=maximum, disposable=True)
    assert not client_tools and not list(root.glob(".restore-*"))


def test_restore_authenticates_first_creates_only_new_database_and_uses_single_transaction(tmp_path, client_tools, monkeypatch):
    root, archive, manifest = saved(tmp_path, client_tools)
    client_tools.clear()
    commands = []
    @contextmanager
    def admin(**kwargs):
        assert kwargs["dbname"] == "postgres" and kwargs["password"] == "fixture_password"
        assert kwargs["connect_timeout"] == 10
        assert kwargs["options"] == "-c statement_timeout=600000 -c lock_timeout=10000"
        yield SimpleNamespace(execute=lambda statement: commands.append(statement.as_string()))
    monkeypatch.setattr(backups.psycopg, "connect", admin)
    target = connection("siteforge_restore_" + uuid4().hex)
    result = backups.restore(archive, root, target, replace(target, database="postgres"),
        key=KEY, key_id="fixture-key", disposable=True)
    assert commands == [f'CREATE DATABASE "{target.database}" TEMPLATE template0']
    assert result["status"] == "restored_disposable" and not result["production_promoted"]
    assert result["backup_id"] == manifest["backup_id"]
    assert client_tools[0]["plaintext"] == DUMP
    assert "--single-transaction" in client_tools[0]["arguments"]
    assert not {"--clean", "--create"} & set(client_tools[0]["arguments"])
    assert "fixture_password" not in repr(client_tools[0]["arguments"])


@pytest.mark.parametrize("name,opt_in", [("production", True), ("siteforge_restore_not-a-uuid", True),
                                        ("siteforge_restore_" + "a" * 32, False)])
def test_restore_refuses_non_disposable_or_noncanonical_targets(tmp_path, client_tools, monkeypatch, name, opt_in):
    root, archive, _ = saved(tmp_path, client_tools)
    monkeypatch.setattr(backups.psycopg, "connect", lambda **kwargs: pytest.fail("Target rejected before connection"))
    with pytest.raises(backups.BackupError, match="disposable"):
        backups.restore(archive, root, connection(name), connection("postgres"),
                        key=KEY, key_id="fixture-key", disposable=opt_in)


def test_existing_database_creation_failure_never_runs_pg_restore(tmp_path, client_tools, monkeypatch):
    root, archive, _ = saved(tmp_path, client_tools)
    client_tools.clear()
    @contextmanager
    def occupied(**kwargs):
        def execute(statement):
            raise psycopg.errors.DuplicateDatabase("fixture existing database")
        yield SimpleNamespace(execute=execute)
    monkeypatch.setattr(backups.psycopg, "connect", occupied)
    target = connection("siteforge_restore_" + uuid4().hex)
    with pytest.raises(backups.BackupError, match="never overwritten"):
        backups.restore(archive, root, target, replace(target, database="postgres"), key=KEY,
                        key_id="fixture-key", disposable=True)
    assert not client_tools


def test_retention_authenticates_age_preserves_minimum_per_source_and_unknown_files(tmp_path, client_tools, monkeypatch):
    root = tmp_path / "backups"
    old = datetime(2026, 1, 1, tzinfo=timezone.utc)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return old
    monkeypatch.setattr(backups, "datetime", Clock)
    first = backups.backup(connection("source_a"), root, key=KEY, key_id="fixture-key")
    second = backups.backup(connection("source_a"), root, key=KEY, key_id="fixture-key")
    third = backups.backup(connection("source_b"), root, key=KEY, key_id="fixture-key")
    corrupt = backups.backup(connection("source_a"), root, key=KEY, key_id="fixture-key")
    (root / corrupt["file"]).write_bytes(b"corrupt and never remove")
    unrelated = root / "operator-notes.txt"
    unrelated.write_text("preserve")
    malformed = root / "siteforge-backup-not-a-uuid.sfb"
    malformed.write_bytes(b"preserve")
    retained = backups.retain(root, key=KEY, key_id="fixture-key", days=30, keep=1,
                              now=datetime(2026, 10, 21, tzinfo=timezone.utc))
    assert len(retained["removed"]) == 1
    assert sum((root / item["file"]).exists() for item in (first, second)) == 1
    assert (root / third["file"]).exists() and (root / corrupt["file"]).exists()
    assert corrupt["file"] in retained["skipped_unverified"]
    assert unrelated.read_text() == "preserve" and malformed.read_bytes() == b"preserve"


def test_other_key_rotation_archives_are_never_deleted_by_retention(tmp_path, client_tools):
    root, archive, _ = saved(tmp_path, client_tools)
    result = backups.retain(root, key=b"x" * 32, key_id="next-key", days=1, keep=1,
                             now=datetime(2100, 1, 1, tzinfo=timezone.utc))
    assert not result["removed"] and result["skipped_unverified"] == [archive.name]
    assert archive.is_file()


def test_linked_or_outside_paths_fail_closed_and_operation_lock_is_exclusive(tmp_path, client_tools):
    root, archive, _ = saved(tmp_path, client_tools)
    with pytest.raises(backups.BackupError, match="directly inside"):
        backups._verify(root, tmp_path / archive.name, io.BytesIO(), KEY, "fixture-key", backups.DEFAULT_MAX_BYTES)
    with backups._locked(root):
        with pytest.raises(backups.BackupError, match="holds"):
            backups.retain(root, key=KEY, key_id="fixture-key")
    with pytest.raises(backups.BackupError, match="absolute"):
        backups.backup(connection(), Path("relative"), key=KEY, key_id="fixture-key")


def test_cli_does_not_leak_bad_key_or_uri_on_failure(tmp_path):
    env = {**os.environ, "SITEFORGE_BACKUP_KEY": "private-invalid-key",
           "SITEFORGE_BACKUP_DATABASE_URL": "postgresql://user:private-password@127.0.0.1/db"}
    result = subprocess.run([sys.executable, "-m", "siteforge.backups", "backup", "--directory", str(tmp_path),
                             "--key-id", "fixture-key"], env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout)["error"] == "backup_operation_failed"
    assert not result.stderr
    assert "private-invalid-key" not in result.stdout and "private-password" not in result.stdout


def test_pg_dump_failure_never_publishes_a_commit_manifest(tmp_path, monkeypatch):
    @contextmanager
    def failed(*args, **kwargs):
        yield SimpleNamespace(stdout=io.BytesIO(DUMP))
        raise backups.BackupError("fixture nonzero client exit")
    monkeypatch.setattr(backups, "_binary", lambda *args: "pg_dump")
    monkeypatch.setattr(backups, "_process", failed)
    root = tmp_path / "backups"
    with pytest.raises(backups.BackupError):
        backups.backup(connection(), root, key=KEY, key_id="fixture-key")
    assert not list(root.glob("*.sfb")) and not list(root.glob("*.manifest.json"))
    assert not list(root.glob("*.part"))


def test_real_client_deadline_kills_and_reaps_without_logging_stderr():
    # Executes only this fixed Python fixture, no PostgreSQL service or shell.
    with pytest.raises(backups.BackupError, match="deadline") as error:
        with backups._process([sys.executable, "-c", "import sys,time;sys.stderr.write('fixture_private_password');sys.stderr.flush();time.sleep(30)"],
                              connection(), .1, stdout=subprocess.DEVNULL) as process:
            pass
    assert process.poll() is not None
    assert "fixture_private_password" not in str(error.value)


def test_source_identity_and_admin_mismatch_are_rejected_before_restore(tmp_path, client_tools, monkeypatch):
    database = "siteforge_restore_" + uuid4().hex
    root, archive, _ = saved(tmp_path, client_tools, selected=connection(database))
    monkeypatch.setattr(backups.psycopg, "connect", lambda **kwargs: pytest.fail("Rejected before any database operation"))
    with pytest.raises(backups.BackupError, match="differ"):
        backups.restore(archive, root, connection(database), connection("postgres"),
                        key=KEY, key_id="fixture-key", disposable=True)
    with pytest.raises(backups.BackupError, match="matching"):
        backups.restore(archive, root, connection("siteforge_restore_" + uuid4().hex),
                        replace(connection("postgres"), port=5433), key=KEY, key_id="fixture-key", disposable=True)


@pytest.mark.parametrize("variable", ["PGHOSTADDR", "PGSERVICE", "PGOPTIONS", "PGPASSWORD"])
def test_inherited_libpq_settings_cannot_redirect_direct_admin_connection(tmp_path, client_tools, monkeypatch, variable):
    root, archive, _ = saved(tmp_path, client_tools)
    client_tools.clear()
    monkeypatch.setenv(variable, "untrusted-parent-setting")
    monkeypatch.setattr(backups.psycopg, "connect", lambda **kwargs: pytest.fail("Inherited destination must be rejected before admin connect"))
    with pytest.raises(backups.BackupError, match="inherited PG"):
        backups.restore(archive, root, connection("siteforge_restore_" + uuid4().hex), connection("postgres"),
                        key=KEY, key_id="fixture-key", disposable=True)
    assert not client_tools


def test_powershell_wrappers_parse_without_execution():
    import shutil
    executable = shutil.which("pwsh")
    if executable is None:
        pytest.skip("PowerShell7 parser unavailable on this test host")
    root = Path(__file__).parents[2]
    script = "$bad=$false; foreach($name in @('Backup-Postgres.ps1','Restore-Postgres.ps1')){$tokens=$null;$errors=$null;[System.Management.Automation.Language.Parser]::ParseFile((Join-Path 'scripts' $name),[ref]$tokens,[ref]$errors)|Out-Null;if($errors.Count){$bad=$true}};if($bad){exit 1}"
    result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-Command", script], cwd=root,
                             capture_output=True, timeout=15)
    assert result.returncode == 0
