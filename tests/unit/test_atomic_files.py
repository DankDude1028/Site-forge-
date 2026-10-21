"""Real Windows reader contention plus portable bounded error behavior."""
import errno
import json
import sys
import threading
import time
from contextlib import contextmanager
from os import replace as real_replace

import pytest

from siteforge import atomic_files


def windows_error(code):
    error = PermissionError(errno.EACCES, "fixture file replacement denial")
    error.winerror = code
    return error


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_transient_windows_denial_retries_without_rewriting_old_target(tmp_path, monkeypatch, winerror):
    target, temporary = tmp_path / "report.json", tmp_path / "report.tmp"
    target.write_text('{"version":1}', encoding="utf-8")
    temporary.write_text('{"version":2}', encoding="utf-8")
    attempts, delays = [], []
    clock = [0.0]

    def commit(source, destination):
        attempts.append(1)
        assert json.loads(target.read_text()) == {"version": 1}
        if len(attempts) <= 2:
            raise windows_error(winerror)
        real_replace(source, destination)

    def advance(seconds):
        delays.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(atomic_files, "_IS_WINDOWS", True)
    monkeypatch.setattr(atomic_files, "replace", commit)
    monkeypatch.setattr(atomic_files, "monotonic", lambda: clock[0])
    monkeypatch.setattr(atomic_files, "sleep", advance)
    atomic_files.atomic_replace(temporary, target)
    assert len(attempts) == 3 and 0 < sum(delays) < 2
    assert json.loads(target.read_text()) == {"version": 2}
    assert not temporary.exists()


@pytest.mark.parametrize("winerror", [None, 2, 112])
def test_other_errors_propagate_without_delay(tmp_path, monkeypatch, winerror):
    target, temporary = tmp_path / "report.json", tmp_path / "report.tmp"
    target.write_bytes(b"previous valid target")
    temporary.write_bytes(b"prepared next version")
    error, attempts = windows_error(winerror), []

    def deny(*_):
        attempts.append(1)
        raise error

    def forbidden_sleep(_):
        pytest.fail("Unrelated errors must not be retried")

    monkeypatch.setattr(atomic_files, "_IS_WINDOWS", True)
    monkeypatch.setattr(atomic_files, "replace", deny)
    monkeypatch.setattr(atomic_files, "sleep", forbidden_sleep)
    with pytest.raises(PermissionError) as caught:
        atomic_files.atomic_replace(temporary, target)
    assert caught.value is error and len(attempts) == 1
    assert target.read_bytes() == b"previous valid target"
    assert temporary.read_bytes() == b"prepared next version"


def test_non_windows_denial_is_immediate(tmp_path, monkeypatch):
    error = windows_error(5)
    calls = []

    def deny(*_):
        calls.append(1)
        raise error

    monkeypatch.setattr(atomic_files, "_IS_WINDOWS", False)
    monkeypatch.setattr(atomic_files, "replace", deny)
    with pytest.raises(PermissionError) as caught:
        atomic_files.atomic_replace(tmp_path / "source", tmp_path / "target")
    assert caught.value is error and len(calls) == 1


def test_permanent_denial_stops_at_deadline_and_retains_valid_bytes(tmp_path, monkeypatch):
    target, temporary = tmp_path / "report.json", tmp_path / "report.tmp"
    previous, prepared = b'{"version":1}', b'{"version":2}'
    target.write_bytes(previous)
    temporary.write_bytes(prepared)
    clock, calls, error = [0.0], [], windows_error(5)

    def deny(*_):
        calls.append(1)
        raise error

    def advance(seconds):
        clock[0] += seconds

    monkeypatch.setattr(atomic_files, "_IS_WINDOWS", True)
    monkeypatch.setattr(atomic_files, "replace", deny)
    monkeypatch.setattr(atomic_files, "monotonic", lambda: clock[0])
    monkeypatch.setattr(atomic_files, "sleep", advance)
    with pytest.raises(PermissionError) as caught:
        atomic_files.atomic_replace(temporary, target)
    assert caught.value is error
    assert clock[0] == pytest.approx(2.0) and 2 <= len(calls) < 20
    assert target.read_bytes() == previous and temporary.read_bytes() == prepared


@contextmanager
def deny_delete_share(path):
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    # GENERIC_READ, share READ/WRITE but deliberately omit FILE_SHARE_DELETE.
    handle = kernel.CreateFileW(str(path), 0x80000000, 0x3, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    closed, guard = False, threading.Lock()

    def close():
        nonlocal closed
        with guard:
            if not closed:
                if not kernel.CloseHandle(handle):
                    raise ctypes.WinError(ctypes.get_last_error())
                closed = True

    try:
        yield close
    finally:
        close()


@pytest.mark.skipif(sys.platform != "win32", reason="requires actual Windows delete-sharing semantics")
@pytest.mark.parametrize("writer", ["benchmark", "endurance", "artifact"])
def test_actual_windows_reader_release_allows_each_writer_to_commit(tmp_path, monkeypatch, writer):
    from benchmarks.runners.report import atomic_write
    from siteforge.endurance import atomic_json
    from siteforge.site_factory import write_artifact

    target = tmp_path / "observed.json"
    target.write_text('{"version":1}', encoding="utf-8")
    denied, errors, releaser_errors = threading.Event(), [], []

    def observed_replace(source, destination):
        try:
            real_replace(source, destination)
        except OSError as error:
            errors.append(error.winerror)
            denied.set()
            raise

    monkeypatch.setattr(atomic_files, "replace", observed_replace)
    with deny_delete_share(target) as close:
        def release_after_denial():
            try:
                if not denied.wait(2):
                    raise AssertionError("Writer did not encounter the held read handle")
                time.sleep(0.05)
                close()
            except BaseException as error:
                releaser_errors.append(error)

        thread = threading.Thread(target=release_after_denial, daemon=True)
        thread.start()
        try:
            if writer == "benchmark":
                atomic_write(target, '{"version":2}\n')
            elif writer == "endurance":
                atomic_json(target, {"version": 2})
            else:
                write_artifact(tmp_path, target.name, {"version": 2})
        finally:
            thread.join(3)
    assert not thread.is_alive() and not releaser_errors
    assert errors and set(errors) <= {5, 32, 33}
    assert json.loads(target.read_text(encoding="utf-8")) == {"version": 2}
