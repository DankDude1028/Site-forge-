"""Bounded Windows sharing-violation tolerance for an atomic file commit.

Callers finish and fsync a temporary file in the target directory first. A failed
replace leaves the previous target and the prepared temporary file intact.
"""
from __future__ import annotations

import sys
from os import PathLike, replace
from time import monotonic, sleep

_IS_WINDOWS = sys.platform == "win32"
_RETRY_SECONDS = 2.0
_SHARING_ERRORS = frozenset({5, 32, 33})


def atomic_replace(source: str | PathLike[str], target: str | PathLike[str]) -> None:
    """Replace once, retrying only Windows access/sharing/lock denial for <=2s.

    A reader or antivirus can briefly hold a Windows file without delete sharing.
    Missing files, full disks, other Windows errors and every non-Windows error
    propagate immediately. No target is deleted or truncated before the commit.
    """
    deadline = monotonic() + _RETRY_SECONDS
    delay = 0.025
    while True:
        try:
            replace(source, target)
            return
        except OSError as error:
            if not _IS_WINDOWS or getattr(error, "winerror", None) not in _SHARING_ERRORS:
                raise
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise
            sleep(min(delay, remaining))
            delay = min(delay * 2, 0.2)
