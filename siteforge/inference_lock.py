"""Cross-process inference exclusion with safe legacy-marker interoperability.

The OS releases the persistent sibling mutex when a process exits or crashes.
The JSON marker supports older benchmark processes that only use O_EXCL. Never
remove a marker belonging to a live PID, or one whose ownership is uncertain.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

import psutil


class InferenceBusy(RuntimeError):
    pass


def process_state(pid: int) -> str:
    """Return alive/dead/unknown without sending any signal to a process."""
    if type(pid) is not int or not 1 <= pid <= 2**31 - 1:
        return "unknown"
    try:
        process = psutil.Process(pid)
        if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
            return "dead"
        return "alive"
    except psutil.NoSuchProcess:
        return "dead"
    except (psutil.AccessDenied, OSError, ValueError):
        return "unknown"


def _mutex_open(marker: Path) -> BinaryIO:
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        handle = marker.with_name(".inference.mutex").open("a+b")
    except OSError as error:
        raise InferenceBusy("Inference OS mutex cannot be opened; ownership is uncertain") from error
    try:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handle
    except OSError as error:
        handle.close()
        raise InferenceBusy("Another benchmark or agent holds the inference OS mutex") from error


def _marker_read(marker: Path) -> dict[str, Any] | None:
    try:
        with marker.open("rb") as handle:
            raw = handle.read(16_385)
    except FileNotFoundError:
        return None
    except OSError as error:
        raise InferenceBusy("Inference marker cannot be inspected; ownership is uncertain") from error
    if len(raw) > 16_384:
        raise InferenceBusy("Inference marker exceeds its inspection limit; ownership is uncertain")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise InferenceBusy("Inference marker is malformed; ownership is uncertain") from error
    if not isinstance(value, dict) or type(value.get("pid")) is not int:
        raise InferenceBusy("Inference marker has no valid PID; ownership is uncertain")
    return value


def _recover_dead_marker(marker: Path) -> None:
    """Caller must hold the OS mutex throughout inspection and recovery."""
    value = _marker_read(marker)
    if value is None:
        return
    state = process_state(value["pid"])
    if state != "dead":
        raise InferenceBusy(f"Inference marker belongs to a {state} process; no recovery is permitted")
    try:
        marker.unlink()
    except FileNotFoundError:
        # A legacy owner/manual operator may remove a marker. Acquisition still
        # uses O_EXCL, so a fresh marker can never be overwritten below.
        pass
    except OSError as error:
        raise InferenceBusy("Confirmed-dead inference marker could not be recovered") from error


def ensure_inference_available(marker_path: str | Path) -> None:
    """Fail closed if busy; recover a dead legacy/new marker under the OS mutex."""
    marker = Path(marker_path)
    if not marker.parent.exists():
        return
    handle = _mutex_open(marker)
    try:
        _recover_dead_marker(marker)
    finally:
        handle.close()


class InferenceLock:
    def __init__(self, marker_path: str | Path, *, owner: str, task_id: str | None = None) -> None:
        self.marker = Path(marker_path)
        self.owner, self.task_id = owner, task_id
        self.token = uuid4().hex
        self.handle: BinaryIO | None = None

    def __enter__(self) -> "InferenceLock":
        if self.handle is not None:
            raise InferenceBusy("Inference lock objects cannot be entered twice")
        handle = _mutex_open(self.marker)
        try:
            _recover_dead_marker(self.marker)
            value = {"pid": os.getpid(), "owner": self.owner, "task_id": self.task_id,
                     "token": self.token, "lock_protocol": "os-mutex-v1",
                     "started_at": datetime.now(timezone.utc).isoformat()}
            try:
                descriptor = os.open(str(self.marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError as error:
                raise InferenceBusy("A legacy benchmark claimed the inference marker") from error
            with os.fdopen(descriptor, "w", encoding="utf-8") as marker:
                json.dump(value, marker)
                marker.flush()
                os.fsync(marker.fileno())
            self.handle = handle
            return self
        except BaseException:
            handle.close()
            raise

    def __exit__(self, *_exception) -> None:
        try:
            current = _marker_read(self.marker)
            if current is not None and current.get("token") == self.token and current["pid"] == os.getpid():
                self.marker.unlink(missing_ok=True)
            # An unexpectedly replaced marker is deliberately left in place.
        finally:
            if self.handle is not None:
                self.handle.close()
                self.handle = None
