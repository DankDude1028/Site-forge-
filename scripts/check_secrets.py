"""Conservative committed-file scanner; credentials are never printed."""
from __future__ import annotations
import re
import subprocess
from pathlib import Path

PATTERNS = [
    re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'(?:ghp_|github_pat_)[A-Za-z0-9_]{30,}'),
    re.compile(rb'sk_(?:live|test)_[A-Za-z0-9]{20,}'),
    re.compile(rb'AKIA[0-9A-Z]{16}'),
]


def main() -> None:
    paths = subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
    hits = []
    for name in filter(None, paths):
        file = Path(name)
        if file.is_file() and file.stat().st_size < 20_000_000:
            raw = file.read_bytes()
            if any(pattern.search(raw) for pattern in PATTERNS):
                hits.append(name)
    if hits:
        raise SystemExit('Possible credentials in committed files: ' + ', '.join(hits))
    print('Committed-file secret pattern scan passed (not a full secret detector).')


if __name__ == '__main__':
    main()
