"""A bounded factory for an original-value, non-public Astro utility preview.

Templates are trusted repository files. Model output never becomes a filename,
command, dependency, or executable site source in this factory.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

SLUG = re.compile(r"[a-z0-9][a-z0-9-]{1,62}\Z")
TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "packages" / "site-templates" / "label-roll-planner"
IGNORED = {"node_modules", "dist", ".astro", ".git", "test-results", "playwright-report", "coverage"}


def scoped_path(root: Path, relative: str) -> Path:
    """Resolve paths and existing links before writing anything to the sandbox."""
    root = root.resolve()
    candidate = (root / relative).resolve()
    if candidate == root or not candidate.is_relative_to(root):
        raise ValueError("Artifact path escapes its configured sandbox")
    return candidate


def site_path(root: Path, slug: str) -> Path:
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        raise ValueError("Invalid site slug")
    return scoped_path(root, slug)


def write_artifact(root: Path, relative: str, data: dict[str, Any]) -> dict[str, Any]:
    path = scoped_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()
    temporary = scoped_path(root, relative + ".tmp")
    # Recheck after mkdir to avoid writing through a preexisting outside link.
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes its configured sandbox")
    temporary.write_bytes(content)
    os.replace(temporary, path)
    return {"kind": "json", "uri": path.relative_to(root.resolve()).as_posix(),
            "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}


def read_artifact(root: Path, relative: str) -> dict[str, Any]:
    path = scoped_path(root, relative)
    if path.stat().st_size > 1_000_000:
        raise ValueError("Artifact exceeds the read limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Artifact must be an object")
    return value


def plan_labels(quantity: int, labels_per_item: int, waste_percent: float,
                labels_per_roll: int, rolls_on_hand: int = 0) -> dict[str, int]:
    """Independent server-side reference math, rounded up at both boundaries."""
    import math

    integers = (quantity, labels_per_item, labels_per_roll, rolls_on_hand)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in integers):
        raise ValueError("Counts must be integers")
    if not (1 <= quantity <= 1_000_000 and 1 <= labels_per_item <= 100):
        raise ValueError("Quantity or labels per item is outside the supported range")
    if not (1 <= labels_per_roll <= 1_000_000 and 0 <= rolls_on_hand <= 1_000_000):
        raise ValueError("Roll count is outside the supported range")
    if isinstance(waste_percent, bool) or not math.isfinite(waste_percent) or not 0 <= waste_percent <= 100:
        raise ValueError("Waste must be finite and between 0 and 100 percent")
    base = quantity * labels_per_item
    needed = math.ceil(base * (100 + waste_percent) / 100)
    required = math.ceil(needed / labels_per_roll)
    return {"base_labels": base, "labels_needed": needed, "rolls_required": required,
            "rolls_to_order": max(0, required - rolls_on_hand),
            "labels_left": required * labels_per_roll - needed}


def create_preview(root: Path, slug: str) -> dict[str, Any]:
    destination = site_path(root, slug) / "source"
    destination.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for directory, folders, filenames in os.walk(TEMPLATE_ROOT, topdown=True, followlinks=False):
        folders[:] = sorted(name for name in folders if name not in IGNORED)
        for name in folders:
            path = Path(directory) / name
            if path.is_symlink() or not path.resolve().is_relative_to(TEMPLATE_ROOT.resolve()):
                raise ValueError("Linked template directories are forbidden")
        for name in sorted(filenames):
            if name.startswith(".env"):
                continue
            source = Path(directory) / name
            relative = source.relative_to(TEMPLATE_ROOT)
            if source.is_symlink():
                raise ValueError("Linked template files are forbidden")
            target = scoped_path(root, f"{slug}/source/{relative.as_posix()}")
            target.parent.mkdir(parents=True, exist_ok=True)
            content = source.read_bytes()
            target.write_bytes(content)
            manifest.append({"path": relative.as_posix(), "sha256": hashlib.sha256(content).hexdigest(),
                             "bytes": len(content)})
    if not manifest:
        raise ValueError("Trusted site template is missing")
    return write_artifact(root, f"{slug}/build/manifest.json", {
        "schema_version": 1, "mode": "fixture", "site_slug": slug,
        "template": "label-roll-planner", "source": f"{slug}/source", "files": manifest,
        "production_authorized": False, "published": False, "build_status": "source_generated",
        "validation_commands": ["npm ci", "npm run typecheck", "npm test", "npm run build"],
    })


def inspect_preview(root: Path, slug: str) -> dict[str, Any]:
    """Static integrity and policy QA; browser/build evidence is separately required."""
    site_path(root, slug)
    manifest = read_artifact(root, f"{slug}/build/manifest.json")
    failures: list[str] = []
    for item in manifest.get("files", []):
        path = scoped_path(root, f"{slug}/source/{item['path']}")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            failures.append(f"Artifact integrity failed: {item['path']}")
    page = scoped_path(root, f"{slug}/source/src/pages/index.astro").read_text(encoding="utf-8")
    checks = {
        "preview_noindex": 'name="robots" content="noindex, nofollow"' in page,
        "language": 'lang="en"' in page,
        "accessible_form": '<label for="quantity"' in page and 'aria-live="polite"' in page,
        "metadata": 'name="description"' in page and "<title>" in page,
        "no_secret_input": 'type="password"' not in page,
        "local_only_calculator": "No inputs leave your browser" in page,
        "production_disabled": manifest.get("production_authorized") is False,
        "reference_math": plan_labels(250, 2, 5, 500, 1)["rolls_to_order"] == 1,
    }
    failures.extend(name for name, passed in checks.items() if not passed)
    return {"schema_version": 1, "mode": "fixture", "site_slug": slug,
            "static_checks": checks, "failures": failures, "static_passed": not failures,
            "astro_build": "pending_separate_executable_check",
            "browser_accessibility": "pending_separate_browser_check", "production_authorized": False}
