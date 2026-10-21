"""Bounded compiled-byte transfer. No builds, shell commands, or provider effects.

The authenticated uploader/commit are claims, not independent source attestation.
The operator-owned root must not be writable by untrusted local OS principals.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID
from xml.etree import ElementTree

from filelock import FileLock
from pydantic import Field, field_validator, model_validator

from .atomic_files import atomic_replace
from .contracts import StrictModel
from .queue import digest

MAX_FILE_BYTES = 4_000_000
MAX_TOTAL_BYTES = 16_000_000
MAX_FILES = 1000
MAX_STAGING = 16
MAX_SEALED = 128
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
_EXTENSIONS = frozenset({".html", ".css", ".js", ".mjs", ".json", ".xml", ".txt", ".svg",
    ".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".ico", ".woff", ".woff2", ".ttf"})
_RESERVED = re.compile(r"(?:con|prn|aux|nul|com[0-9]|lpt[0-9])(?:\..*)?\Z", re.I)
_CREDENTIAL = re.compile(rb"-----BEGIN (?:[A-Z ]*PRIVATE KEY|OPENSSH PRIVATE KEY)-----|"
    rb"(?:AKIA|ASIA)[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|"
    rb'"(?:private_key|client_secret|netlify_auth_token|github_token|access_token)"\s*:', re.I)


def canonical_origin(value: str) -> str:
    """Accept a canonical HTTPS origin, never credentials, subpaths, or placeholders."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise ValueError("Invalid canonical HTTPS origin") from error
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or port not in {None, 443} or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", parsed.hostname)
            or any(not part or part.startswith("-") or part.endswith("-") for part in parsed.hostname.split("."))
            or parsed.hostname in {"localhost", "127.0.0.1"}):
        raise ValueError("Canonical must be a bounded public HTTPS origin")
    return f"https://{parsed.hostname}"


def _relative(value: str) -> str:
    parts = value.split("/")
    if (not value or len(value) > 140 or len(parts) > 8 or any(
            not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,79}", part)
            or part.endswith(".") or _RESERVED.fullmatch(part) for part in parts)
            or Path(value).suffix.lower() not in _EXTENSIONS
            or any(part.casefold() in {"credentials", "secrets", "node_modules", "functions"} for part in parts)):
        raise ValueError("Only bounded portable static output paths are accepted")
    return value


class BundleFile(StrictModel):
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bytes: int = Field(strict=True, ge=0, le=MAX_FILE_BYTES)

    @field_validator("path")
    @classmethod
    def static_path(cls, value: str) -> str:
        return _relative(value)


class BundleManifest(StrictModel):
    version: Literal[1] = 1
    site_id: UUID
    commit_sha: str = Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
    mode: Literal["preview", "production"]
    canonical_origin: str = Field(max_length=250)
    preview_deployment_id: UUID | None = None
    source_preview_tree_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    files: list[BundleFile] = Field(min_length=1, max_length=MAX_FILES)

    @field_validator("canonical_origin")
    @classmethod
    def origin(cls, value: str) -> str:
        return canonical_origin(value)

    @model_validator(mode="after")
    def bindings(self) -> BundleManifest:
        if self.mode == "production":
            if not self.preview_deployment_id or not self.source_preview_tree_sha256:
                raise ValueError("Production requires the reviewed source preview deployment and tree")
            hostname = urlsplit(self.canonical_origin).hostname or ""
            if hostname.endswith((".invalid", ".test", ".example")) or hostname == "example.com":
                raise ValueError("Production requires a configured real canonical origin")
        elif self.preview_deployment_id is not None or self.source_preview_tree_sha256 is not None:
            raise ValueError("Preview must not claim a reviewed source preview")
        names = [item.path.casefold() for item in self.files]
        if len(names) != len(set(names)) or sum(item.bytes for item in self.files) > MAX_TOTAL_BYTES:
            raise ValueError("Duplicate paths or total bundle byte limit exceeded")
        for path in names:
            if any(path.startswith(other + "/") for other in names if other != path):
                raise ValueError("A file cannot also be a directory")
        if not {"index.html", "robots.txt", "sitemap.xml"} <= set(names):
            raise ValueError("Compiled output requires index.html, robots.txt, and sitemap.xml")
        self.files.sort(key=lambda item: item.path)
        return self


def _linked(path: Path) -> bool:
    return path.is_symlink() or path.is_junction() or bool(
        getattr(path.lstat(), "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024))


def _root(path: Path) -> Path:
    path = path.absolute()
    if path.exists() and _linked(path):
        raise ValueError("Bundle root cannot be a link or reparse point")
    return path.resolve()


def _safe(root: Path, relative: str) -> Path:
    path = root / relative
    if len(str(path)) > 240:
        raise ValueError("Bundle path exceeds the portable Windows absolute path limit")
    if not path.is_relative_to(root):
        raise ValueError("Bundle path escapes its root")
    current = root
    for part in path.relative_to(root).parts:
        if part in {"..", "."}:
            raise ValueError("Invalid bundle path")
        current = current / part
        if os.path.lexists(current):
            if _linked(current):
                raise ValueError("Bundle links and reparse points are forbidden")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > 300_000:
        raise ValueError("Missing or oversized bundle metadata")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("Invalid bundle metadata")
    return value


def _identity(org_id: str, uploader: str) -> dict[str, str]:
    UUID(org_id)
    if not isinstance(uploader, str) or not 1 <= len(uploader) <= 100 or any(ord(c) < 32 for c in uploader):
        raise ValueError("Invalid authenticated uploader identity")
    return {"org_id": str(UUID(org_id)), "uploader": uploader,
            "assurance": "authenticated uploader claims; not independent GitHub attestation"}


class _Head(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.robots: list[str] = []
        self.canonicals: list[str] = []
        self.in_head = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "head":
            self.in_head = True
        if not self.in_head:
            return
        values = dict(attrs)
        if tag == "meta" and (values.get("name") or "").casefold() == "robots":
            self.robots.append((values.get("content") or "").casefold().replace(" ", ""))
        if tag == "link" and (values.get("rel") or "").casefold() == "canonical":
            self.canonicals.append(values.get("href") or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self.in_head = False


def _seo(manifest: BundleManifest, contents: dict[str, bytes]) -> None:
    urls: set[str] = set()
    for name, content in contents.items():
        if not name.endswith(".html"):
            continue
        head = _Head()
        head.feed(content.decode("utf-8", errors="strict"))
        route = "/" if name == "index.html" else "/" + name.removesuffix("index.html")
        expected = manifest.canonical_origin + route
        if head.canonicals != [expected]:
            raise ValueError("Every HTML page requires exactly its canonical URL")
        wanted = "index,follow" if manifest.mode == "production" else "noindex,nofollow"
        if head.robots != [wanted]:
            raise ValueError("Compiled HTML robots metadata differs from the bundle mode")
        urls.add(expected)
    robots = contents["robots.txt"].decode("utf-8").replace("\r\n", "\n").strip()
    expected_robots = (f"User-agent: *\nAllow: /\nSitemap: {manifest.canonical_origin}/sitemap.xml"
        if manifest.mode == "production" else "User-agent: *\nDisallow: /")
    if robots != expected_robots:
        raise ValueError("Compiled robots.txt differs from the bundle mode")
    xml = contents["sitemap.xml"]
    if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
        raise ValueError("Sitemap entities are forbidden")
    document = ElementTree.fromstring(xml)
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    locations = [node.text for node in document.findall(f"{namespace}url/{namespace}loc")]
    if document.tag != namespace + "urlset" or len(locations) != len(urls) or set(locations) != urls:
        raise ValueError("Sitemap must list exactly the canonical compiled HTML pages")


def _verify(root: Path, directory: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    manifest = BundleManifest.model_validate(metadata["manifest"])
    provenance = metadata["provenance"]
    if provenance != _identity(provenance["org_id"], provenance["uploader"]):
        raise ValueError("Invalid uploader provenance")
    identifier = digest({"manifest": manifest.model_dump(mode="json"), "provenance": provenance})
    if metadata.get("manifest_sha256") != identifier:
        raise ValueError("Bundle manifest binding changed")
    files_root = _safe(root, directory.relative_to(root).as_posix() + "/files")
    expected = {item.path: item for item in manifest.files}
    actual: set[str] = set()
    contents: dict[str, bytes] = {}
    tree: list[tuple[str, str, str, int]] = []
    for current, folders, files in os.walk(files_root, followlinks=False):
        for name in [*folders, *files]:
            path = _safe(root, (Path(current) / name).relative_to(root).as_posix())
            if _linked(path):
                raise ValueError("Linked bundle output is forbidden")
        for name in files:
            path = Path(current) / name
            relative = path.relative_to(files_root).as_posix()
            item = expected.get(relative)
            attributes = path.stat()
            if (item is None or attributes.st_size != item.bytes or not stat.S_ISREG(attributes.st_mode)
                    or attributes.st_nlink != 1):
                raise ValueError("Bundle output contains unexpected or incomplete bytes")
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != item.sha256 or _CREDENTIAL.search(content):
                raise ValueError("Bundle content digest differs or contains a credential pattern")
            actual.add(relative)
            contents[relative] = content
            tree.append((relative, hashlib.sha1(content).hexdigest(), item.sha256, len(content)))
    if actual != set(expected):
        raise ValueError("Bundle uploads are incomplete")
    _seo(manifest, contents)
    tree.sort()
    tree_hash = digest(tuple(tree))
    if metadata.get("tree_sha256") not in {None, tree_hash}:
        raise ValueError("Published bundle tree binding changed")
    return {**manifest.model_dump(mode="json"), **provenance, "bundle_id": identifier,
            "manifest_sha256": identifier, "tree_sha256": tree_hash,
            "relative_directory": f"b/{identifier}/files", "files": [list(item) for item in tree],
            "status": "sealed", "sealed": True}


def inspect_bundle(root: Path, relative_directory: str) -> dict[str, Any]:
    """Revalidate finalized immutable bytes and authenticated claims; no provider reads."""
    if not isinstance(relative_directory, str) or not re.fullmatch(r"b/[0-9a-f]{64}/files", relative_directory):
        raise ValueError("Release requires an exact finalized bundle directory")
    root = _root(root)
    directory = _safe(root, relative_directory.removesuffix("/files"))
    metadata = _read_json(_safe(root, directory.relative_to(root).as_posix() + "/manifest.json"))
    result = _verify(root, directory, metadata)
    if result["relative_directory"] != relative_directory or metadata.get("sealed") is not True:
        raise ValueError("Bundle is not finalized with its exact identity")
    return result


class BundleStore:
    """Filesystem authority beneath the authenticated, site-scoped API boundary."""
    def __init__(self, root: Path, *, enabled: bool = False,
                 allowed_origins: dict[str, str] | None = None) -> None:
        self.root, self.enabled = _root(root), enabled
        self.allowed_origins = {str(UUID(key)): canonical_origin(value)
                                for key, value in (allowed_origins or {}).items()}

    def _ready(self) -> None:
        if not self.enabled:
            raise ValueError("Bundle transfer is disabled")
        self.root.mkdir(parents=True, exist_ok=True)
        for name in (".u", ".l", "b"):
            _safe(self.root, name).mkdir(exist_ok=True)

    def _lock(self, identifier: str) -> FileLock:
        if not _HASH.fullmatch(identifier):
            raise ValueError("Invalid bundle identity")
        # Fixed 256 lock stripes bound metadata disk use even for rejected IDs.
        # The complete SHA256 remains the directory/manifest/security identity.
        return FileLock(str(_safe(self.root, f".l/{identifier[:2]}.lock")), timeout=0)

    def _location(self, identifier: str) -> Path:
        if not _HASH.fullmatch(identifier):
            raise ValueError("Invalid bundle identity")
        sealed = _safe(self.root, f"b/{identifier}")
        return sealed if sealed.exists() else _safe(self.root, f".u/{identifier}")

    def _metadata(self, identifier: str, org_id: str, uploader: str) -> tuple[Path, dict[str, Any]]:
        directory = self._location(identifier)
        metadata = _read_json(_safe(self.root, directory.relative_to(self.root).as_posix() + "/manifest.json"))
        if metadata.get("provenance") != _identity(org_id, uploader) or metadata.get("manifest_sha256") != identifier:
            raise ValueError("Bundle belongs to another authenticated uploader or organization")
        return directory, metadata

    @staticmethod
    def _write(path: Path, content: bytes) -> None:
        with path.open("xb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

    def _count(self, name: str, maximum: int) -> int:
        count = 0
        with os.scandir(_safe(self.root, name)) as entries:
            for entry in entries:
                if _linked(Path(entry.path)) or not entry.is_dir(follow_symlinks=False):
                    raise ValueError("Bundle registry contains unexpected entries")
                count += 1
                if count >= maximum:
                    return count
        return count

    def begin(self, manifest: BundleManifest, *, org_id: str, uploader: str) -> dict[str, Any]:
        self._ready()
        manifest = BundleManifest.model_validate(manifest)
        if manifest.mode == "production" and self.allowed_origins.get(str(manifest.site_id)) != manifest.canonical_origin:
            raise ValueError("Production canonical origin is not independently server allowlisted")
        provenance = _identity(org_id, uploader)
        identifier = digest({"manifest": manifest.model_dump(mode="json"), "provenance": provenance})
        with FileLock(str(_safe(self.root, ".l/registry.lock")), timeout=0), self._lock(identifier):
            directory = self._location(identifier)
            if directory.exists():
                return self.describe(identifier, org_id=org_id, uploader=uploader)
            if self._count(".u", MAX_STAGING) >= MAX_STAGING or self._count("b", MAX_SEALED) >= MAX_SEALED:
                raise ValueError("Bundle registry capacity reached; operator retention review required")
            for item in manifest.files:
                _safe(self.root, f".u/{identifier}/files/{item.path}")
                _safe(self.root, f"b/{identifier}/files/{item.path}")
            directory.mkdir()
            _safe(self.root, f".u/{identifier}/files").mkdir()
            metadata = {"manifest": manifest.model_dump(mode="json"), "provenance": provenance,
                        "manifest_sha256": identifier, "sealed": False}
            self._write(directory / "manifest.json", (json.dumps(metadata, sort_keys=True) + "\n").encode())
        return self.describe(identifier, org_id=org_id, uploader=uploader)

    def describe(self, bundle_id: str, *, org_id: str, uploader: str) -> dict[str, Any]:
        self._ready()
        directory, metadata = self._metadata(bundle_id, org_id, uploader)
        manifest = BundleManifest.model_validate(metadata["manifest"])
        sealed = directory.parent == self.root / "b"
        verified: dict[str, Any] = {}
        if sealed:
            verified = inspect_bundle(self.root, f"b/{bundle_id}/files")
        return {**manifest.model_dump(mode="json"), **metadata["provenance"], **verified, "manifest": metadata["manifest"],
                "bundle_id": bundle_id, "manifest_sha256": bundle_id, "sealed": sealed,
                "status": "sealed" if sealed else "staging",
                "relative_directory": f"b/{bundle_id}/files" if sealed else None}

    def upload(self, bundle_id: str, path: str, content: bytes, *, org_id: str, uploader: str) -> dict[str, Any]:
        self._ready()
        _relative(path)
        if not isinstance(content, bytes) or len(content) > MAX_FILE_BYTES:
            raise ValueError("Upload must be bounded binary bytes")
        with self._lock(bundle_id):
            directory, metadata = self._metadata(bundle_id, org_id, uploader)
            manifest = BundleManifest.model_validate(metadata["manifest"])
            item = next((item for item in manifest.files if item.path == path), None)
            if item is None or len(content) != item.bytes or hashlib.sha256(content).hexdigest() != item.sha256:
                raise ValueError("Upload differs from the exact manifest path, bytes, or SHA256")
            if _CREDENTIAL.search(content):
                raise ValueError("Compiled output contains a credential pattern")
            target = _safe(self.root, directory.relative_to(self.root).as_posix() + "/files/" + path)
            if target.exists():
                if target.read_bytes() != content:
                    raise ValueError("Immutable uploaded bytes changed")
                return {"bundle_id": bundle_id, "path": path, "sha256": item.sha256, "bytes": item.bytes}
            if directory.parent == self.root / "b":
                raise ValueError("Finalized bundle is immutable")
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = _safe(self.root, directory.relative_to(self.root).as_posix() + "/upload.tmp")
            if temporary.exists():
                temporary.unlink()  # abandoned bounded upload from an interrupted write, never approved bytes
            try:
                self._write(temporary, content)
                atomic_replace(temporary, target)
            finally:
                if temporary.exists():
                    temporary.unlink()
        return {"bundle_id": bundle_id, "path": path, "sha256": item.sha256, "bytes": item.bytes}

    def finalize(self, bundle_id: str, *, org_id: str, uploader: str) -> dict[str, Any]:
        self._ready()
        with FileLock(str(_safe(self.root, ".l/registry.lock")), timeout=0), self._lock(bundle_id):
            directory, metadata = self._metadata(bundle_id, org_id, uploader)
            if directory.parent == self.root / "b":
                return inspect_bundle(self.root, f"b/{bundle_id}/files")
            if self._count("b", MAX_SEALED) >= MAX_SEALED:
                raise ValueError("Sealed bundle capacity reached; operator retention review required")
            result = _verify(self.root, directory, metadata)
            metadata.update(sealed=True, tree_sha256=result["tree_sha256"])
            temporary = _safe(self.root, directory.relative_to(self.root).as_posix() + "/manifest.tmp")
            if temporary.exists():
                temporary.unlink()
            self._write(temporary, (json.dumps(metadata, sort_keys=True) + "\n").encode())
            atomic_replace(temporary, directory / "manifest.json")
            atomic_replace(directory, _safe(self.root, f"b/{bundle_id}"))
            return inspect_bundle(self.root, result["relative_directory"])
