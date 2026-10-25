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

from .atomic_files import atomic_replace
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
    with temporary.open("wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    atomic_replace(temporary, path)
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
    critical = ("site-config.mjs", "astro.config.mjs", "src/pages/index.astro",
                "src/pages/privacy.astro", "src/pages/robots.txt.ts", "src/pages/sitemap.xml.ts",
                "src/components/Calculator.astro")
    critical_sources: dict[str, str] = {}
    trusted_configuration = True
    listed = {item["path"] for item in manifest.get("files", [])}
    for relative in critical:
        source = scoped_path(root, f"{slug}/source/{relative}")
        expected = TEMPLATE_ROOT / relative
        if relative not in listed or not source.is_file() or source.read_bytes() != expected.read_bytes():
            trusted_configuration = False
        critical_sources[relative] = source.read_text(encoding="utf-8") if source.is_file() else ""
    page = critical_sources["src/pages/index.astro"]
    calculator = critical_sources["src/components/Calculator.astro"]
    configuration = critical_sources["site-config.mjs"]
    # This is a trusted-source inspection, never evidence that Astro ran. Runtime
    # build environment and the final compiled bytes have separate validation.
    preview_default = ("const mode = environment.SITEFORGE_BUILD_MODE || 'preview';" in configuration
                       and "'index, follow' : 'noindex, nofollow'" in configuration)
    crawl_route = critical_sources["src/pages/robots.txt.ts"]
    checks = {
        "trusted_build_configuration": trusted_configuration,
        "preview_default_configuration": preview_default,
        "preview_noindex": trusted_configuration and preview_default and 'name="robots" content={config.robots}' in page,
        "preview_crawl_route": trusted_configuration and "config.mode === 'production'" in crawl_route
                               and "User-agent: *\\nDisallow: /\\n" in crawl_route,
        "language": 'lang="en"' in page,
        # The calculator contract lives in a locked component the page must render.
        "accessible_form": ("<Calculator />" in page and '<label for="quantity"' in calculator
                            and 'aria-live="polite"' in calculator),
        "metadata": 'name="description"' in page and "<title>" in page,
        "no_secret_input": 'type="password"' not in page + calculator,
        "local_only_calculator": "No inputs leave your browser" in page,
        "production_disabled": manifest.get("production_authorized") is False,
        "reference_math": plan_labels(250, 2, 5, 500, 1)["rolls_to_order"] == 1,
    }
    failures.extend(name for name, passed in checks.items() if not passed)
    return {"schema_version": 1, "mode": "fixture", "site_slug": slug,
            "static_checks": checks, "failures": failures, "static_passed": not failures,
            "astro_build": "pending_separate_executable_check",
            "browser_accessibility": "pending_separate_browser_check", "production_authorized": False}
