"""Authenticated local PostgreSQL backups; restores only create disposable databases.

Credentials and keys come from environment variables, never CLI arguments. No
provider is provisioned, existing database overwritten, or database dropped.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import ipaddress
import json
import math
import os
import re
import shutil
import struct
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO, Iterator, Protocol, cast
from uuid import UUID, uuid4

import psycopg
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from filelock import FileLock, Timeout
from psycopg import sql
from sqlalchemy.engine import make_url

MAGIC = b"SFBK1\n"
CHUNK = 1024 * 1024
DEFAULT_MAX_BYTES = 512 * CHUNK
MAX_BYTES = 8 * 1024 * CHUNK
NAME = re.compile(r"siteforge-backup-([0-9a-f]{32})\.sfb\Z")
TARGET = re.compile(r"siteforge_restore_[0-9a-f]{32}\Z")


class BackupError(RuntimeError):
    """Operator-safe errors never contain credentials or subprocess output."""


class Writer(Protocol):
    def write(self, data: bytes) -> int: ...


@dataclass(frozen=True)
class Connection:
    host: str
    port: int
    database: str
    username: str
    password: str = field(repr=False)
    sslmode: str = "verify-full"
    sslrootcert: str | None = None

    def __post_init__(self) -> None:
        try:
            local = ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            local = self.host == "localhost"
        if (not re.fullmatch(r"[A-Za-z0-9._:-]{1,253}", self.host)
                or type(self.port) is not int or not 1 <= self.port <= 65535
                or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,62}", self.database)
                or not self.username or not self.password
                or self.sslmode not in {"disable", "prefer", "require", "verify-ca", "verify-full"}
                or (not local and self.sslmode != "verify-full")):
            raise BackupError("Explicit PostgreSQL identity and verified TLS for remote hosts are required")

    def identity(self) -> dict[str, Any]:
        return {"host": self.host, "port": self.port, "database": self.database}

    def environment(self) -> dict[str, str]:
        # Prevent inherited libpq service/options/hostaddr/password files from
        # silently changing the explicitly selected destination or role.
        allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG", "LC_ALL"}
        result = {name: value for name, value in os.environ.items() if name.upper() in allowed}
        result.update(PGHOST=self.host, PGPORT=str(self.port), PGDATABASE=self.database,
                      PGUSER=self.username, PGPASSWORD=self.password, PGSSLMODE=self.sslmode,
                      PGCONNECT_TIMEOUT="10", PGPASSFILE=os.devnull)
        if self.sslrootcert:
            result["PGSSLROOTCERT"] = self.sslrootcert
        return result

    def parameters(self, *, database: str | None = None) -> dict[str, Any]:
        return {"host": self.host, "port": self.port, "dbname": database or self.database,
                "user": self.username, "password": self.password, "sslmode": self.sslmode,
                "connect_timeout": 10, "options": "",
                **({"sslrootcert": self.sslrootcert} if self.sslrootcert else {})}


def connection_from_env(name: str) -> Connection:
    if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", name):
        raise BackupError("Invalid connection environment variable name")
    try:
        url = make_url(os.environ[name])
        if (url.drivername not in {"postgresql", "postgresql+psycopg", "postgres"}
                or not url.host or not re.fullmatch(r"[A-Za-z0-9._:-]{1,253}", url.host)
                or not url.username or len(url.username) > 128 or not url.password
                or not url.database or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,62}", url.database)
                or not set(url.query) <= {"sslmode", "sslrootcert"}):
            raise ValueError()
        port = url.port or 5432
        if not 1 <= port <= 65535:
            raise ValueError()
        try:
            loopback = ipaddress.ip_address(url.host).is_loopback
        except ValueError:
            loopback = url.host == "localhost"
        mode = url.query.get("sslmode", "prefer" if loopback else "verify-full")
        rootcert = url.query.get("sslrootcert")
        if (not isinstance(mode, str) or mode not in {"disable", "prefer", "require", "verify-ca", "verify-full"}
                or (not loopback and mode != "verify-full")
                or (rootcert is not None and not isinstance(rootcert, str))):
            raise ValueError()
        return Connection(url.host, port, url.database, url.username, url.password, mode, rootcert)
    except (KeyError, ValueError, TypeError):
        raise BackupError("Explicit PostgreSQL URI with credentials and safe TLS settings is required in the configured environment variable") from None


def key_from_env(name: str = "SITEFORGE_BACKUP_KEY") -> bytes:
    try:
        key = base64.b64decode(os.environ[name], validate=True)
        if len(key) != 32:
            raise ValueError()
        return key
    except (KeyError, ValueError):
        raise BackupError("Backup key environment variable must contain a base64-encoded random 32-byte key") from None


def _key_id(value: str, key: bytes | None = None) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value):
        raise BackupError("A bounded public key identifier is required")
    if key is not None and (not isinstance(key, bytes) or len(key) != 32):
        raise BackupError("AES-256-GCM requires a 32-byte key")


def _limits(max_bytes: int, timeout: float) -> None:
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES or not 0 < timeout <= 3600:
        raise BackupError("Backup limits must be positive: at most 8 GiB and 3600 seconds")


def _directory(path: Path) -> Path:
    if not path.is_absolute() or path == Path(path.anchor):
        raise BackupError("Use an explicit absolute non-root backup directory")
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise BackupError("Linked backup paths are forbidden")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path.resolve()


def _file(root: Path, path: Path) -> Path:
    if (path.parent != root or path.is_symlink() or path.is_junction()
            or not path.is_file() or path.resolve().parent != root):
        raise BackupError("Backup files must be regular files directly inside the configured directory")
    return path


def _binary(name: str, directory: Path | None) -> str:
    path = (directory / (name + ".exe" if os.name == "nt" else name)) if directory else shutil.which(name)
    if path is None or not Path(path).is_file():
        raise BackupError("Install the matching PostgreSQL client binaries or supply their directory")
    return str(path)


@contextmanager
def _process(arguments: list[str], connection: Connection, timeout: float, *,
             stdin: Any = subprocess.DEVNULL, stdout: Any = subprocess.PIPE) -> Iterator[subprocess.Popen]:
    process = subprocess.Popen(arguments, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE,
                               env=connection.environment(), shell=False,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
    timed_out = threading.Event()

    def stop() -> None:
        timed_out.set()
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass  # Process may have completed between poll and termination.

    def drain() -> None:
        if process.stderr:
            while process.stderr.read(CHUNK):
                pass  # Never log provider text or buffer an unbounded error stream.

    timer = threading.Timer(timeout, stop)
    timer.daemon = True
    reader = threading.Thread(target=drain, daemon=True)
    timer.start()
    reader.start()
    try:
        yield process
        process.wait(timeout=timeout)
        if timed_out.is_set() or process.returncode:
            raise BackupError("PostgreSQL client failed or exceeded its deadline; raw output is withheld")
    except subprocess.TimeoutExpired:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        raise BackupError("PostgreSQL client exceeded its deadline; raw output is withheld") from None
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        raise
    finally:
        timer.cancel()
        reader.join(10)
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()


def _json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def encrypt_stream(source: BinaryIO, destination: Writer, *, key: bytes, header: dict[str, Any],
                   max_bytes: int) -> dict[str, Any]:
    """Encrypt bounded custom-format dump bytes; metadata is authenticated AAD."""
    raw_header = _json(header)
    prefix = MAGIC + struct.pack(">I", len(raw_header)) + raw_header
    encryptor = Cipher(algorithms.AES256(key), modes.GCM(bytes.fromhex(header["nonce"]))).encryptor()
    encryptor.authenticate_additional_data(prefix)
    destination.write(prefix)
    total, digest = 0, hashlib.sha256()
    while data := source.read(CHUNK):
        if total == 0 and not data.startswith(b"PGDMP"):
            raise BackupError("Expected PostgreSQL custom-format dump")
        total += len(data)
        if total > max_bytes:
            raise BackupError("Database dump exceeds the configured size limit")
        digest.update(data)
        destination.write(encryptor.update(data))
    if total < 5:
        raise BackupError("Database dump is empty or incomplete")
    destination.write(encryptor.finalize())
    destination.write(encryptor.tag)
    return {"dump_bytes": total, "dump_sha256": digest.hexdigest()}


def _header(source: BinaryIO) -> tuple[dict[str, Any], bytes]:
    if source.read(len(MAGIC)) != MAGIC:
        raise BackupError("Unknown backup envelope")
    size = source.read(4)
    if len(size) != 4 or not 1 <= (length := struct.unpack(">I", size)[0]) <= 16_384:
        raise BackupError("Invalid backup header size")
    raw = source.read(length)
    try:
        header = json.loads(raw)
        required = {"schema_version", "backup_id", "created_at", "key_id", "nonce", "cipher", "source"}
        if (not isinstance(header, dict) or set(header) != required or header["schema_version"] != 1
                or header["cipher"] != "AES-256-GCM" or len(bytes.fromhex(header["nonce"])) != 12
                or UUID(header["backup_id"]).hex != header["backup_id"]
                or not isinstance(header["source"], dict) or set(header["source"]) != {"host", "port", "database"}):
            raise ValueError()
        _key_id(header["key_id"])
        observed = datetime.fromisoformat(header["created_at"])
        if observed.tzinfo is None or observed.utcoffset() != timedelta(0):
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        raise BackupError("Malformed backup metadata") from None
    return header, MAGIC + size + raw


def decrypt_stream(source: BinaryIO, destination: Writer, *, key: bytes, key_id: str,
                   max_bytes: int, deadline: float | None = None) -> dict[str, Any]:
    """Destination remains quarantined until GCM authentication fully succeeds."""
    header, prefix = _header(source)
    if header["key_id"] != key_id:
        raise BackupError("Backup belongs to a different key identifier")
    payload_start = source.tell()
    source.seek(0, 2)
    size = source.tell()
    ciphertext_size = size - payload_start - 16
    if not 5 <= ciphertext_size <= max_bytes:
        raise BackupError("Encrypted dump size is outside the configured limit")
    source.seek(-16, 2)
    tag = source.read(16)
    source.seek(payload_start)
    decryptor = Cipher(algorithms.AES256(key), modes.GCM(bytes.fromhex(header["nonce"]), tag)).decryptor()
    decryptor.authenticate_additional_data(prefix)
    remaining, digest, first = ciphertext_size, hashlib.sha256(), True
    try:
        while remaining:
            if deadline is not None and time.monotonic() > deadline:
                raise BackupError("Backup authentication exceeded its inspection deadline")
            data = source.read(min(CHUNK, remaining))
            if not data:
                raise BackupError("Truncated backup ciphertext")
            remaining -= len(data)
            plain = decryptor.update(data)
            if first and not plain.startswith(b"PGDMP"):
                raise BackupError("Backup does not contain a PostgreSQL custom-format archive")
            first = False
            digest.update(plain)
            destination.write(plain)
        destination.write(decryptor.finalize())
    except InvalidTag:
        raise BackupError("Backup authentication failed; no database operation is permitted") from None
    return {**header, "dump_bytes": ciphertext_size, "dump_sha256": digest.hexdigest()}


def _manifest_path(archive: Path) -> Path:
    return archive.with_suffix(".manifest.json")


def _verify(root: Path, archive: Path, destination: Writer, key: bytes, key_id: str,
            max_bytes: int, deadline: float | None = None) -> dict[str, Any]:
    if not NAME.fullmatch(archive.name):
        raise BackupError("Backup filename must contain its canonical UUID")
    _file(root, archive)
    manifest_path = _file(root, _manifest_path(archive))
    if manifest_path.stat().st_size > 16_384:
        raise BackupError("Backup manifest exceeds its size limit")
    try:
        manifest = json.loads(manifest_path.read_bytes())
        with archive.open("rb") as source:
            authenticated = decrypt_stream(source, destination, key=key, key_id=key_id,
                                           max_bytes=max_bytes, deadline=deadline)
            source.seek(0)
            checksum = hashlib.file_digest(source, "sha256").hexdigest()
        expected = {**authenticated, "file": archive.name, "archive_sha256": checksum,
                    "archive_bytes": archive.stat().st_size}
        if manifest != expected or archive.name != f"siteforge-backup-{authenticated['backup_id']}.sfb":
            raise BackupError("Backup manifest does not match authenticated data and checksums")
        return expected
    except (ValueError, TypeError):
        raise BackupError("Malformed backup manifest") from None


@contextmanager
def _locked(root: Path) -> Iterator[None]:
    lock_path = root / ".backup.lock"
    if lock_path.is_symlink() or lock_path.is_junction():
        raise BackupError("Linked backup lock files are forbidden")
    try:
        with FileLock(str(lock_path), timeout=0):
            yield
    except Timeout:
        raise BackupError("Another local backup operation holds this directory") from None


def backup(connection: Connection, directory: Path, *, key: bytes, key_id: str,
           pg_bin: Path | None = None, max_bytes: int = DEFAULT_MAX_BYTES, timeout: float = 600) -> dict[str, Any]:
    _key_id(key_id, key)
    _limits(max_bytes, timeout)
    root = _directory(directory)
    identifier = uuid4().hex
    archive = root / f"siteforge-backup-{identifier}.sfb"
    header = {"schema_version": 1, "backup_id": identifier, "created_at": datetime.now(timezone.utc).isoformat(),
              "key_id": key_id, "nonce": os.urandom(12).hex(), "cipher": "AES-256-GCM", "source": connection.identity()}
    prepared = archive.with_suffix(".part")
    manifest_path = _manifest_path(archive)
    prepared_created = False
    with _locked(root):
        try:
            if archive.exists() or manifest_path.exists():
                raise BackupError("Backup UUID already exists; no overwrite is permitted")
            with prepared.open("xb") as output:
                prepared_created = True
                with _process([_binary("pg_dump", pg_bin), "--format=custom", "--no-owner", "--no-acl", "--no-password"],
                              connection, timeout) as process:
                    metadata = encrypt_stream(cast(BinaryIO, process.stdout), output, key=key, header=header, max_bytes=max_bytes)
                output.flush()
                os.fsync(output.fileno())
            with prepared.open("rb") as source:
                checksum = hashlib.file_digest(source, "sha256").hexdigest()
            manifest = {**header, **metadata, "file": archive.name, "archive_sha256": checksum,
                        "archive_bytes": prepared.stat().st_size}
            # Hard-link publication is atomic and refuses existing targets. The
            # manifest is the commit marker; orphan archives are never retained/deleted.
            os.link(prepared, archive)
            manifest_temp = manifest_path.with_suffix(".part")
            with manifest_temp.open("xb") as output:
                output.write(_json(manifest) + b"\n")
                output.flush()
                os.fsync(output.fileno())
            os.link(manifest_temp, manifest_path)
            manifest_temp.unlink()
            return manifest
        finally:
            if prepared_created and prepared.exists() and not prepared.is_symlink():
                prepared.unlink()


class _Discard:
    def write(self, data: bytes) -> int:
        return len(data)


def retain(directory: Path, *, key: bytes, key_id: str, days: int = 30, keep: int = 7,
           max_bytes: int = DEFAULT_MAX_BYTES, now: datetime | None = None) -> dict[str, Any]:
    _key_id(key_id, key)
    _limits(max_bytes, 60)
    if type(days) is not int or not 1 <= days <= 3650 or type(keep) is not int or not 1 <= keep <= 1000:
        raise BackupError("Retention requires 1–3650 days and at least 1–1000 retained backups")
    root = _directory(directory)
    observed = now or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise BackupError("Retention time must include a timezone")
    verified: dict[str, list[tuple[datetime, Path]]] = {}
    skipped, removed = [], []
    deadline = time.monotonic() + 60
    with _locked(root):
        candidates = list(root.glob("siteforge-backup-*.sfb"))
        if len(candidates) > 1000:
            raise BackupError("Retention directory exceeds the 1000-candidate inspection limit")
        for archive in candidates:
            if time.monotonic() > deadline:
                raise BackupError("Retention inspection exceeded its 60-second deadline; no deletions performed")
            if not NAME.fullmatch(archive.name):
                continue
            try:
                manifest = _verify(root, archive, _Discard(), key, key_id, max_bytes, deadline)
                created = datetime.fromisoformat(manifest["created_at"])
                if created > observed:
                    raise BackupError("Backup timestamp is in the future")
                verified.setdefault(json.dumps(manifest["source"], sort_keys=True), []).append((created, archive))
            except (BackupError, OSError):
                skipped.append(archive.name)
        for group in verified.values():
            group.sort(reverse=True)
            for created, archive in group[keep:]:
                if created < observed - timedelta(days=days):
                    manifest_path = _file(root, _manifest_path(archive))
                    _file(root, archive).unlink()
                    manifest_path.unlink()
                    removed.append(archive.name)
    return {"removed": removed, "skipped_unverified": skipped,
            "verified": sum(len(group) for group in verified.values())}


@contextmanager
def _quarantine(root: Path) -> Iterator[BinaryIO]:
    directory = Path(tempfile.mkdtemp(prefix=".restore-", dir=root))
    try:
        if os.name == "nt":
            system = Path(os.environ["SystemRoot"]) / "System32"
            identity = subprocess.run([str(system / "whoami.exe"), "/user", "/fo", "csv", "/nh"],
                capture_output=True, check=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            match = re.search(rb"S-1-(?:[0-9]+-)*[0-9]+", identity.stdout)
            if match is None:
                raise BackupError("Cannot verify the current Windows identity")
            sid = match.group().decode("ascii")
            subprocess.run([str(system / "icacls.exe"), str(directory), "/inheritance:r", "/grant:r",
                f"*{sid}:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"], capture_output=True, check=True,
                timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            directory.chmod(0o700)
        # Authentication completes in an owner-only, delete-on-close temporary
        # file before any target creation. pg_restore receives this handle only.
        with tempfile.TemporaryFile(mode="w+b", prefix="dump-", dir=directory) as handle:
            yield cast(BinaryIO, handle)
    finally:
        directory.rmdir()  # Never recursively delete an operator-controlled tree.


def restore(archive: Path, directory: Path, target: Connection, admin: Connection, *,
            key: bytes, key_id: str, disposable: bool = False, pg_bin: Path | None = None,
            max_bytes: int = DEFAULT_MAX_BYTES, timeout: float = 600) -> dict[str, Any]:
    _key_id(key_id, key)
    _limits(max_bytes, timeout)
    root = _directory(directory)
    if (not disposable or not TARGET.fullmatch(target.database) or admin.database != "postgres"
            or (target.host, target.port, target.username, target.password, target.sslmode, target.sslrootcert)
            != (admin.host, admin.port, admin.username, admin.password, admin.sslmode, admin.sslrootcert)):
        raise BackupError("Restore requires explicit disposable opt-in, a new siteforge_restore_<UUID> database and a matching postgres admin URI")
    with _locked(root), _quarantine(root) as verified_dump:
        # No database connection or client launch occurs before full GCM and
        # manifest authentication. Never stream unauthenticated plaintext to PG.
        manifest = _verify(root, archive, verified_dump, key, key_id, max_bytes, time.monotonic() + timeout)
        if target.database == manifest["source"]["database"]:
            raise BackupError("Restore target must differ from the authenticated backup source")
        verified_dump.seek(0)
        binary = _binary("pg_restore", pg_bin)
        # psycopg/libpq resolves additional options from the parent environment
        # even with explicit host/user parameters (notably PGHOSTADDR). Refuse
        # inherited settings instead of mutating shared process environment.
        if any(name.upper().startswith("PG") for name in os.environ):
            raise BackupError("Clear inherited PG environment settings; restore uses explicit URI configuration only")
        parameters = admin.parameters()
        milliseconds = max(1, math.ceil(timeout * 1000))
        parameters.update(connect_timeout=min(10, max(1, math.ceil(timeout))),
                          options=f"-c statement_timeout={milliseconds} -c lock_timeout={min(milliseconds, 10000)}")
        try:
            with psycopg.connect(**parameters, autocommit=True) as connection:
                # CREATE DATABASE fails if the target already exists; no DROP,
                # --clean, overwrite, production promotion or URL switch exists.
                connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(target.database)))
        except psycopg.Error:
            raise BackupError("Disposable target creation failed; existing databases are never overwritten") from None
        with _process([binary, "--exit-on-error", "--single-transaction", "--no-owner", "--no-acl", "--no-password",
                       "--dbname", target.database], target, timeout, stdin=verified_dump, stdout=subprocess.DEVNULL):
            pass
        return {"status": "restored_disposable", "database": target.database, "backup_id": manifest["backup_id"],
                "archive_sha256": manifest["archive_sha256"], "production_promoted": False}


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    commands = cli.add_subparsers(dest="command", required=True)
    for name in ("backup", "restore", "retain"):
        command = commands.add_parser(name)
        command.add_argument("--directory", required=True, type=Path)
        command.add_argument("--key-id", required=True)
        command.add_argument("--key-env", default="SITEFORGE_BACKUP_KEY")
        command.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
        if name != "retain":
            command.add_argument("--pg-bin", type=Path)
            command.add_argument("--timeout", type=float, default=600)
        if name == "backup":
            command.add_argument("--source-env", default="SITEFORGE_BACKUP_DATABASE_URL")
        if name == "restore":
            command.add_argument("--archive", required=True, type=Path)
            command.add_argument("--target-env", default="SITEFORGE_RESTORE_DATABASE_URL")
            command.add_argument("--admin-env", default="SITEFORGE_RESTORE_ADMIN_URL")
            command.add_argument("--disposable", action="store_true")
        if name == "retain":
            command.add_argument("--days", type=int, default=30)
            command.add_argument("--keep", type=int, default=7)
    return cli


def main() -> None:
    args = parser().parse_args()
    try:
        key = key_from_env(args.key_env)
        shared = {"key": key, "key_id": args.key_id, "max_bytes": args.max_bytes}
        if args.command == "backup":
            result = backup(connection_from_env(args.source_env), args.directory, pg_bin=args.pg_bin,
                            timeout=args.timeout, **shared)
        elif args.command == "restore":
            result = restore(args.archive, args.directory, connection_from_env(args.target_env),
                             connection_from_env(args.admin_env), disposable=args.disposable,
                             pg_bin=args.pg_bin, timeout=args.timeout, **shared)
        else:
            result = retain(args.directory, days=args.days, keep=args.keep, **shared)
        print(json.dumps(result, sort_keys=True))
    except (BackupError, OSError, ValueError, TimeoutError, subprocess.SubprocessError):
        # No exception repr/traceback, URI, key, password, or provider error body.
        print(json.dumps({"status": "failed", "error": "backup_operation_failed", "details": "Check configuration, integrity, limits and private operator diagnostics; credentials and client output are withheld"}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
