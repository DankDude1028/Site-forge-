"""Narrow provider adapters, disconnected and read-only until operator configured.

No repository/site provisioning, merges, production publishing, spend, or outreach
method is exposed. Tests use mocked transports, never real provider credentials.
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from uuid import UUID

import httpx

from siteforge.queue import digest
from siteforge.site_factory import scoped_path


class ProviderError(RuntimeError):
    pass


class ProviderOutcomeUnknown(ProviderError):
    """An external mutation may have succeeded; reconcile instead of blind retry."""


@dataclass(frozen=True)
class ProviderReceipt:
    provider: str
    operation: str
    resource_id: str
    url: str
    request_hash: str
    state: str
    replay: bool = False


def _branch(value: str) -> str:
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,150}", value) or ".." in value
            or "//" in value or value.endswith(("/", ".", ".lock"))):
        raise ValueError("Invalid bounded branch name")
    return value


class _HTTPProvider:
    origin: str
    token_environment: str

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=20, trust_env=False, follow_redirects=False)

    def _request(self, method: str, path: str, *, mutation: bool = False, **kwargs: Any) -> Any:
        token = os.environ.get(self.token_environment)
        if not token:
            raise ProviderError("Provider credential is not configured")
        headers = {"Authorization": f"Bearer {token}", **kwargs.pop("headers", {})}
        try:
            response = self.client.request(method, self.origin + path, headers=headers,
                                           follow_redirects=False, timeout=20, **kwargs)
        except (httpx.NetworkError, httpx.TimeoutException) as error:
            if mutation:
                raise ProviderOutcomeUnknown("Provider response uncertain; reconcile before another mutation") from error
            raise ProviderError("Provider read unavailable") from error
        if response.is_redirect:
            raise ProviderError("Provider redirect refused")
        if not response.is_success:
            if mutation and response.status_code >= 500:
                raise ProviderOutcomeUnknown("Provider outcome uncertain; reconcile before another mutation")
            raise ProviderError(f"Provider rejected request ({response.status_code})")
        if response.status_code == 204:
            return None
        if len(response.content) > 2_000_000:
            raise ProviderError("Provider response exceeds limit")
        try:
            return response.json()
        except ValueError as error:
            if mutation:
                raise ProviderOutcomeUnknown("Provider mutation response malformed; reconcile first") from error
            raise ProviderError("Provider response malformed") from error

    def close(self) -> None:
        self.client.close()


class GitHubAdapter(_HTTPProvider):
    origin = "https://api.github.com"
    token_environment = "GITHUB_TOKEN"

    def __init__(self, repository: str, allowed_repositories: frozenset[str], *,
                 writes_enabled: bool = False, client: httpx.Client | None = None) -> None:
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", repository)
                or repository not in allowed_repositories):
            raise ValueError("Repository must be explicitly configured and allowlisted")
        super().__init__(client)
        self.repository, self.writes_enabled = repository, writes_enabled

    def _api(self, method: str, suffix: str = "", **kwargs: Any) -> Any:
        return self._request(method, f"/repos/{self.repository}{suffix}", headers={
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"}, **kwargs)

    def read_repository(self) -> dict[str, Any]:
        value = self._api("GET")
        if (not isinstance(value, dict) or not isinstance(value.get("full_name"), str)
                or value["full_name"].casefold() != self.repository.casefold()):
            raise ProviderError("Repository identity mismatch")
        return {key: value.get(key) for key in ("full_name", "private", "default_branch", "archived")}

    def read_branch(self, branch: str) -> dict[str, str]:
        branch = _branch(branch)
        value = self._api("GET", "/branches/" + quote(branch, safe=""))
        commit = value.get("commit", {}) if isinstance(value, dict) else {}
        sha = commit.get("sha", "") if isinstance(commit, dict) else ""
        if (not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha)
                or value.get("name") != branch):
            raise ProviderError("Malformed branch identity")
        return {"branch": branch, "sha": sha}

    def _receipt(self, value: dict[str, Any], request_hash: str, replay: bool = False) -> ProviderReceipt:
        number = value.get("number")
        expected = f"https://github.com/{self.repository}/pull/{number}"
        if (not isinstance(number, int) or isinstance(number, bool) or number < 1
                or value.get("html_url") != expected or value.get("draft") is not True):
            raise ProviderOutcomeUnknown("Draft pull request response requires reconciliation")
        return ProviderReceipt("github", "open_draft_pr", str(number), expected, request_hash, "draft", replay)

    def open_draft_pr(self, *, title: str, body: str, head: str, base: str,
                      head_sha: str, idempotency_key: str) -> ProviderReceipt:
        if not self.writes_enabled:
            raise ProviderError("Provider writes are disabled pending operator authorization")
        head, base = _branch(head), _branch(base)
        if (head == base or not title.strip() or len(title) > 200 or len(body) > 30_000
                or not 1 <= len(idempotency_key) <= 160):
            raise ValueError("Invalid bounded draft request")
        if self.read_branch(head)["sha"] != head_sha:
            raise ProviderError("Head branch moved; review the exact commit again")
        request_hash = digest({"repo": self.repository, "title": title, "body": body, "head": head,
                               "base": base, "head_sha": head_sha, "key": idempotency_key})
        marker = f"<!-- siteforge-draft:{request_hash} -->"
        existing = self._api("GET", "/pulls", params={"head": self.repository.split("/")[0] + ":" + head,
            "base": base, "state": "open", "per_page": 100})
        if not isinstance(existing, list) or len(existing) >= 100:
            raise ProviderError("Cannot safely reconcile bounded pull request query")
        for item in existing:
            if not isinstance(item, dict):
                raise ProviderError("Malformed pull request reconciliation result")
            if marker in (item.get("body") or ""):
                return self._receipt(item, request_hash, replay=True)
        if existing:
            raise ProviderError("Existing pull request has another binding; owner review required")
        result = self._api("POST", "/pulls", mutation=True, json={"title": title,
            "body": body + "\n\n" + marker, "head": head, "base": base, "draft": True,
            "maintainer_can_modify": False})
        if not isinstance(result, dict):
            raise ProviderOutcomeUnknown("Draft response requires reconciliation")
        return self._receipt(result, request_hash)


@dataclass(frozen=True)
class PreviewPlan:
    directory: Path
    site_id: str
    files: tuple[tuple[str, str, str, int], ...]  # relative path, SHA1, SHA256, bytes
    request_hash: str


class NetlifyPreviewAdapter(_HTTPProvider):
    origin = "https://api.netlify.com/api/v1"
    token_environment = "NETLIFY_AUTH_TOKEN"

    def __init__(self, site_id: str, artifact_root: Path, *, operator_authorized: bool = False,
                 cost_authorized: bool = False, protected_preview_verified: bool = False,
                 client: httpx.Client | None = None) -> None:
        UUID(site_id)
        super().__init__(client)
        self.site_id, self.root = site_id, artifact_root.resolve()
        self.enabled = operator_authorized and cost_authorized and protected_preview_verified

    def plan(self, relative_directory: str) -> PreviewPlan:
        directory = scoped_path(self.root, relative_directory)
        if not directory.is_dir():
            raise ValueError("Preview directory must be an existing scoped build output")
        files: list[tuple[str, str, str, int]] = []
        total = 0
        for current, folders, names in os.walk(directory, followlinks=False):
            for folder in folders:
                nested = Path(current) / folder
                if nested.is_symlink() or not nested.resolve().is_relative_to(directory):
                    raise ValueError("Linked preview directories are forbidden")
            if any(name in {".git", ".netlify", "node_modules", "functions"} for name in folders):
                raise ValueError("Only static build output can be uploaded")
            for name in sorted(names):
                path = Path(current) / name
                relative = path.relative_to(directory).as_posix()
                if path.is_symlink() or not path.resolve().is_relative_to(directory):
                    raise ValueError("Linked preview files are forbidden")
                if (name.startswith(".env") or name in {".git", ".netlify"}
                        or path.suffix.lower() in {".pem", ".key", ".zip"}):
                    raise ValueError("Sensitive or archive files are not allowed in preview output")
                if path.stat().st_size > 4_000_000:
                    raise ValueError("Preview file exceeds size limit")
                content = path.read_bytes()
                total += len(content)
                if len(files) >= 1000 or total > 16_000_000:
                    raise ValueError("Preview exceeds bounded static upload limit")
                if path.suffix.lower() == ".html" and b'content="noindex, nofollow"' not in content:
                    raise ValueError("Every preview HTML page requires noindex metadata")
                files.append((relative, hashlib.sha1(content).hexdigest(), hashlib.sha256(content).hexdigest(), len(content)))
        if not any(item[0] == "index.html" for item in files):
            raise ValueError("Preview requires a static index.html")
        files.sort()
        request_hash = digest({"site_id": self.site_id, "files": files, "draft": True})
        return PreviewPlan(directory, self.site_id, tuple(files), request_hash)

    def create_draft_preview(self, plan: PreviewPlan) -> ProviderReceipt:
        if not self.enabled:
            raise ProviderError("Preview disabled until operator cost authorization and site protection verification")
        # Rehash the exact bytes immediately before creating the provider effect.
        current = self.plan(plan.directory.relative_to(self.root).as_posix())
        if current != plan or plan.site_id != self.site_id:
            raise ProviderError("Preview artifact binding changed; review again")
        result = self._request("POST", f"/sites/{self.site_id}/deploys", mutation=True,
            json={"draft": True, "files": {"/" + item[0]: item[1] for item in plan.files}})
        if not isinstance(result, dict) or result.get("site_id") != self.site_id:
            raise ProviderOutcomeUnknown("Draft deploy identity requires reconciliation")
        identifier = result.get("id", "")
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-zA-Z0-9-]{1,100}", identifier):
            raise ProviderOutcomeUnknown("Invalid deploy receipt; reconcile provider state")
        required = result.get("required", [])
        if (not isinstance(required, list) or any(not isinstance(item, str) for item in required)
                or not set(required) <= {item[1] for item in plan.files}):
            raise ProviderOutcomeUnknown("Provider requested an unexpected file digest")
        for relative, sha1, sha256, _ in plan.files:
            if sha1 not in required:
                continue
            path = scoped_path(plan.directory, relative)
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != sha256:
                raise ProviderOutcomeUnknown("Preview changed during upload; reconcile existing draft")
            self._request("PUT", f"/deploys/{identifier}/files/{quote(relative, safe='/')}",
                mutation=True, content=content, headers={"Content-Type": "application/octet-stream"})
        url = result.get("deploy_ssl_url") or result.get("deploy_url") or ""
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment
                or not parsed.hostname or not parsed.hostname.endswith(".netlify.app")
                or not parsed.hostname.startswith(identifier + "--") or parsed.port not in {None, 443}
                or parsed.path not in {"", "/"}):
            raise ProviderOutcomeUnknown("Invalid draft preview URL; reconcile provider state")
        return ProviderReceipt("netlify", "create_draft_preview", identifier, url, plan.request_hash,
                               "processing_pending_health_and_protection_check")
