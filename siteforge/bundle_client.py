"""Transfer static build bytes for review. This command never deploys a site.

Builds execute separately without the transfer credential. The authenticated
uploader supplies provenance claims; this is not independent build attestation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

from .bundles import BundleManifest
from .release_client import ReleaseClient


def collect_manifest(directory: Path, *, site_id: str, commit_sha: str, mode: str,
                     canonical_origin: str, preview_deployment_id: str | None = None,
                     source_preview_tree_sha256: str | None = None) -> BundleManifest:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Static build directory must be a real directory")
    directory = directory.resolve()
    files: list[dict] = []
    total = 0
    for current, folders, names in os.walk(directory, followlinks=False):
        for folder in folders:
            path = Path(current) / folder
            if path.is_symlink() or path.is_junction() or not path.resolve().is_relative_to(directory):
                raise ValueError("Linked build directories are forbidden")
        for name in sorted(names):
            path = Path(current) / name
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(directory):
                raise ValueError("Linked or nonregular build files are forbidden")
            length = path.stat().st_size
            total += length
            if length > 4_000_000 or total > 16_000_000 or len(files) >= 1000:
                raise ValueError("Static build exceeds the bounded transfer limits")
            with path.open("rb") as handle:
                content = handle.read(4_000_001)
            if len(content) != length:
                raise ValueError("Build bytes changed while collecting provenance")
            files.append({"path": path.relative_to(directory).as_posix(),
                          "sha256": hashlib.sha256(content).hexdigest(), "bytes": length})
    return BundleManifest.model_validate({
        "version": 1, "site_id": str(UUID(site_id)), "commit_sha": commit_sha,
        "mode": mode, "canonical_origin": canonical_origin,
        "preview_deployment_id": preview_deployment_id,
        "source_preview_tree_sha256": source_preview_tree_sha256,
        "files": sorted(files, key=lambda item: item["path"]),
    })


class BundleClient(ReleaseClient):
    def upload(self, directory: Path, manifest: BundleManifest) -> dict:
        result = self._post("/v1/bundles", manifest.model_dump(mode="json"))
        bundle_id = result.get("bundle_id")
        if (not isinstance(bundle_id, str) or len(bundle_id) != 64
                or any(letter not in "0123456789abcdef" for letter in bundle_id)):
            raise RuntimeError("Malformed supervisor bundle identity")
        if result.get("status") != "sealed":
            directory = directory.resolve()
            for item in manifest.files:
                path = directory / item.path
                if path.is_symlink() or not path.resolve().is_relative_to(directory):
                    raise ValueError("Build path changed before transfer")
                with path.open("rb") as handle:
                    content = handle.read(4_000_001)
                if len(content) != item.bytes or hashlib.sha256(content).hexdigest() != item.sha256:
                    raise ValueError("Build bytes changed before transfer")
                response = self.client.put(f"/v1/bundles/{bundle_id}/files",
                    params={"path": item.path}, content=content,
                    headers={"Content-Type": "application/octet-stream"})
                if not response.is_success:
                    raise RuntimeError(f"Supervisor bundle transfer failed ({response.status_code})")
            result = self._post(f"/v1/bundles/{bundle_id}/finalize", {})
        if (result.get("bundle_id") != bundle_id or result.get("status") != "sealed"
                or result.get("relative_directory") != f"b/{bundle_id}/files"):
            raise RuntimeError("Supervisor did not confirm the exact sealed bundle")
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--site-id", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--mode", choices=["preview", "production"], required=True)
    parser.add_argument("--canonical-origin", required=True)
    parser.add_argument("--preview-deployment-id")
    parser.add_argument("--source-preview-tree-sha256")
    args = parser.parse_args()
    manifest = collect_manifest(args.directory, site_id=args.site_id, commit_sha=args.commit_sha,
        mode=args.mode, canonical_origin=args.canonical_origin,
        preview_deployment_id=args.preview_deployment_id,
        source_preview_tree_sha256=args.source_preview_tree_sha256)
    client = BundleClient(os.environ.get("SITEFORGE_API_URL", ""),
                          os.environ.get("SITEFORGE_RELEASE_TOKEN", ""))
    try:
        print(json.dumps(client.upload(args.directory, manifest), default=str))
    finally:
        client.close()


if __name__ == "__main__":
    main()
