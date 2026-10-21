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
from typing import Any, Callable
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
    mode: str = "preview"


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

    def plan(self, relative_directory: str, *, mode: str = "preview") -> PreviewPlan:
        if mode not in {"preview", "production"}:
            raise ValueError("Unsupported release artifact mode")
        provenance = None
        if mode == "production":
            from .bundles import inspect_bundle
            provenance = inspect_bundle(self.root, relative_directory)
            origin = getattr(self, "production_origin", None)
            if (provenance["mode"] != "production" or not isinstance(origin, str)
                    or provenance["canonical_origin"] != origin.rstrip("/")):
                raise ValueError("Production candidate needs finalized bytes and the configured canonical origin")
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
                if mode == "preview" and path.suffix.lower() == ".html" and b'content="noindex, nofollow"' not in content:
                    raise ValueError("Every preview HTML page requires noindex metadata")
                files.append((relative, hashlib.sha1(content).hexdigest(), hashlib.sha256(content).hexdigest(), len(content)))
        if not any(item[0] == "index.html" for item in files):
            raise ValueError("Preview requires a static index.html")
        files.sort()
        if provenance is not None and digest(tuple(files)) != provenance["tree_sha256"]:
            raise ValueError("Production candidate bytes differ from finalized provenance")
        request_hash = digest({"site_id": self.site_id, "files": files, "draft": True, "mode": mode})
        return PreviewPlan(directory, self.site_id, tuple(files), request_hash, mode)

    def create_draft_preview(self, plan: PreviewPlan, *, correlation_id: str | None = None,
                             on_created: Callable[[ProviderReceipt], None] | None = None) -> ProviderReceipt:
        if not self.enabled:
            raise ProviderError("Preview disabled until operator cost authorization and site protection verification")
        # Rehash the exact bytes immediately before creating the provider effect.
        current = self.plan(plan.directory.relative_to(self.root).as_posix(), mode=plan.mode)
        if current != plan or plan.site_id != self.site_id:
            raise ProviderError("Preview artifact binding changed; review again")
        if correlation_id is not None and not re.fullmatch(r"siteforge:[a-zA-Z0-9:-]{1,180}", correlation_id):
            raise ValueError("Invalid release correlation marker")
        options = {"params": {"title": correlation_id}} if correlation_id else {}
        result = self._request("POST", f"/sites/{self.site_id}/deploys", mutation=True, **options,
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
        url = result.get("deploy_ssl_url") or result.get("deploy_url") or ""
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment
                or not parsed.hostname or not parsed.hostname.endswith(".netlify.app")
                or not parsed.hostname.startswith(identifier + "--") or parsed.port not in {None, 443}
                or parsed.path not in {"", "/"}):
            raise ProviderOutcomeUnknown("Invalid draft preview URL; reconcile provider state")
        if on_created is not None:
            # Persist identity before PUTs. A crash later requires reads/reconciliation,
            # never another create. Callback failures deliberately stop uploading.
            on_created(ProviderReceipt("netlify", "create_draft_preview", identifier, url,
                                       plan.request_hash, "created_pending_upload"))
        for relative, sha1, sha256, _ in plan.files:
            if sha1 not in required:
                continue
            path = scoped_path(plan.directory, relative)
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != sha256:
                raise ProviderOutcomeUnknown("Preview changed during upload; reconcile existing draft")
            self._request("PUT", f"/deploys/{identifier}/files/{quote(relative, safe='/')}",
                mutation=True, content=content, headers={"Content-Type": "application/octet-stream"})
        return ProviderReceipt("netlify", "create_draft_preview", identifier, url, plan.request_hash,
                               "processing_pending_health_and_protection_check")


class NetlifyReleaseAdapter(NetlifyPreviewAdapter):
    """Fixed-site reads, private health and gated promotion of a new ready draft.

    API contracts reviewed 2026-10-21: https://open-api.netlify.com/
    createSiteDeploy title, getSiteDeploy, listSiteDeploys, restoreSiteDeploy.
    This is never an older-deploy rollback: only an unpublished ready draft may
    be promoted. Fixing a bad published release requires a new reviewed preview.
    """
    def __init__(self, site_id: str, artifact_root: Path, *, preview_authorization: str | None = None,
                 production_enabled: bool = False, production_origin: str | None = None,
                 rollback_enabled: bool = False,
                 exclusive_publisher_verified: bool = False, health_client: httpx.Client | None = None,
                 **kwargs: Any) -> None:
        super().__init__(site_id, artifact_root, **kwargs)
        if preview_authorization is not None and not re.fullmatch(r"Basic [A-Za-z0-9+/=]+", preview_authorization):
            raise ValueError("Preview authorization must be a server-configured Basic credential")
        if production_origin is not None:
            parsed = urlparse(production_origin)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.port not in {None, 443} or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
                raise ValueError("Production origin must be an explicitly configured HTTPS origin")
        self.preview_authorization = preview_authorization
        self.production_enabled, self.production_origin = production_enabled, production_origin
        self.rollback_enabled = rollback_enabled
        self.exclusive_publisher_verified = exclusive_publisher_verified
        self.health_client = health_client or httpx.Client(timeout=20, trust_env=False, follow_redirects=False)

    @staticmethod
    def _identifier(value: Any) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,100}", value):
            raise ProviderError("Invalid bounded deploy identity")
        return value

    def _deploy(self, value: Any, identifier: str | None = None) -> dict[str, Any]:
        if not isinstance(value, dict) or value.get("site_id") != self.site_id:
            raise ProviderError("Provider deploy site identity mismatch")
        actual = self._identifier(value.get("id"))
        if identifier is not None and actual != identifier:
            raise ProviderError("Provider deploy identity mismatch")
        for field in ("state", "title", "commit_ref", "deploy_ssl_url", "published_at"):
            if value.get(field) is not None and not isinstance(value[field], str):
                raise ProviderError("Provider deploy metadata malformed")
        required = value.get("required", [])
        if not isinstance(required, list) or len(required) > 1000 or any(type(item) is not str for item in required):
            raise ProviderError("Provider required digests malformed")
        return {key: value.get(key) for key in ("id", "site_id", "state", "title", "commit_ref",
                "deploy_ssl_url", "published_at", "draft")} | {"required": required}

    def read_deploy(self, identifier: str) -> dict[str, Any]:
        identifier = self._identifier(identifier)
        return self._deploy(self._request("GET", f"/sites/{self.site_id}/deploys/{identifier}"), identifier)

    def read_site(self) -> dict[str, Any]:
        value = self._request("GET", f"/sites/{self.site_id}")
        if (not isinstance(value, dict) or value.get("id") != self.site_id
                or not isinstance(value.get("name"), str)
                or not re.fullmatch(r"[a-z0-9-]{1,100}", value["name"])):
            raise ProviderError("Provider site identity mismatch")
        # Never return password, tokens or the provider's unfiltered site object.
        return {key: value.get(key) for key in ("id", "name", "ssl_url")}

    def current_published_id(self) -> str | None:
        values = self._request("GET", f"/sites/{self.site_id}/deploys",
                               params={"latest-published": "true", "per_page": 1})
        if not isinstance(values, list) or len(values) > 1:
            raise ProviderError("Published deploy lookup ambiguous")
        if not values:
            return None
        published = self._deploy(values[0])
        if published["draft"] is not False or not published["published_at"] or published["state"] != "ready":
            raise ProviderError("Published deploy identity was not confirmed")
        return published["id"]

    def find_draft(self, correlation_id: str) -> dict[str, Any] | None:
        matches = []
        for page in range(1, 4):
            values = self._request("GET", f"/sites/{self.site_id}/deploys", params={"per_page": 100, "page": page})
            if not isinstance(values, list) or len(values) > 100:
                raise ProviderError("Deploy reconciliation listing malformed")
            for item in values:
                deploy = self._deploy(item)
                if deploy["title"] == correlation_id:
                    matches.append(deploy)
            if len(values) < 100:
                break
        if len(matches) > 1:
            raise ProviderError("Release correlation matched multiple provider effects")
        return matches[0] if matches else None

    def _probe(self, url: str, *, authorized: bool = False) -> tuple[int, bytes]:
        # Separate client from API credentials; explicitly strip client defaults
        # and cookies for the anonymous access-control test.
        request = self.health_client.build_request("GET", url, timeout=20)
        request.headers.pop("Authorization", None)
        request.headers.pop("Cookie", None)
        if authorized:
            if self.preview_authorization is None:
                raise ProviderError("Protected preview access credential is not configured")
            request.headers["Authorization"] = self.preview_authorization
        try:
            response = self.health_client.send(request, stream=True, follow_redirects=False, auth=None)
            try:
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 4_000_000:
                        raise ProviderError("Health response exceeds bounded limit")
                return response.status_code, bytes(data)
            finally:
                response.close()
        except httpx.HTTPError as error:
            raise ProviderError("Bounded health read unavailable") from error

    def verify_preview(self, deploy: dict[str, Any], index_sha256: str) -> dict[str, Any]:
        site = self.read_site()
        url = deploy.get("deploy_ssl_url")
        if url not in {f"https://{deploy['id']}--{site['name']}.netlify.app",
                       f"https://{deploy['id']}--{site['name']}.netlify.app/"}:
            raise ProviderError("Preview URL is outside the configured provider site")
        anonymous, _ = self._probe(url)
        if anonymous not in {401, 403}:
            raise ProviderError("Preview protection not observed; anonymous content or redirect refused")
        status, content = self._probe(url, authorized=True)
        if status != 200 or hashlib.sha256(content).hexdigest() != index_sha256:
            raise ProviderError("Preview index health/content binding failed")
        return {"protection_observed": True, "anonymous_status": anonymous, "authenticated_status": status,
                "index_sha256": index_sha256, "scope": "Exact index bytes and denied anonymous access"}

    def verify_production(self, index_sha256: str) -> dict[str, Any]:
        site = self.read_site()
        if (not self.production_origin or not isinstance(site["ssl_url"], str)
                or site["ssl_url"].rstrip("/") != self.production_origin.rstrip("/")):
            raise ProviderError("Production health origin is not independently allowlisted")
        status, content = self._probe(self.production_origin)
        if status != 200 or hashlib.sha256(content).hexdigest() != index_sha256:
            raise ProviderError("Production index health/content binding failed")
        return {"status": 200, "index_sha256": index_sha256, "scope": "Exact approved index bytes at configured origin"}

    def resume_draft_upload(self, plan: PreviewPlan, identifier: str, required: list[str], *,
                            before_upload: Callable[[], None]) -> int:
        """Explicit same-hash PUT recovery only; never creates another deploy.

        Netlify's documented digest upload binds each file path to its SHA1 in
        the original deploy. The supervisor additionally verifies SHA256/size
        and supplies a durable, zero-incremental-cost attempt/fence guard.
        """
        if not self.enabled or plan.site_id != self.site_id or len(required) > 1000:
            raise ProviderError("Draft upload recovery disabled or out of scope")
        if not set(required) <= {item[1] for item in plan.files}:
            raise ProviderError("Unknown required digest cannot be uploaded")
        deploy = self.read_deploy(identifier)
        if deploy["draft"] is not True or deploy["published_at"]:
            raise ProviderError("Upload recovery cannot alter a published or foreign deploy")
        if not set(deploy["required"]) <= {item[1] for item in plan.files}:
            raise ProviderError("Provider recovery digest is outside the approved tree")
        required = [item for item in required if item in deploy["required"]]
        current = self.plan(plan.directory.relative_to(self.root).as_posix(), mode=plan.mode)
        if current != plan:
            raise ProviderError("Recovery artifact changed")
        uploaded = 0
        for relative, sha1, sha256, size in plan.files:
            if sha1 not in required:
                continue
            if uploaded == 10:
                break
            content = scoped_path(plan.directory, relative).read_bytes()
            if len(content) != size or hashlib.sha256(content).hexdigest() != sha256:
                raise ProviderError("Recovery bytes no longer match approved digest")
            before_upload()
            self._request("PUT", f"/deploys/{self._identifier(identifier)}/files/{quote(relative, safe='/')}",
                mutation=True, content=content, headers={"Content-Type": "application/octet-stream"})
            uploaded += 1
        return uploaded

    def promote_ready_preview(self, identifier: str, previous_published_id: str | None,
                              request_hash: str) -> ProviderReceipt:
        if (not self.enabled or not self.production_enabled or not self.exclusive_publisher_verified
                or not self.production_origin):
            raise ProviderError("Production promotion disabled by server configuration")
        deploy = self.read_deploy(identifier)
        if (deploy["state"] != "ready" or deploy["draft"] is not True or deploy["published_at"]
                or deploy["required"] or self.current_published_id() != previous_published_id):
            raise ProviderError("Only a new ready draft with the exact previous published identity may be promoted")
        # Documented restoreSiteDeploy endpoint used only to promote an unpublished
        # ready draft. There is no general restore/rollback method.
        result = self._request("POST", f"/sites/{self.site_id}/deploys/{identifier}/restore", mutation=True)
        try:
            self._deploy(result, identifier)
        except ProviderError as error:
            raise ProviderOutcomeUnknown("Promotion response uncertain; read published identity before any new action") from error
        return ProviderReceipt("netlify", "promote_ready_preview", identifier,
                               self.production_origin or "", request_hash, "publication_pending_reconciliation")

    def rollback_to_previous(self, candidate_id: str, previous_id: str, *, candidate_title: str,
                             previous_title: str, request_hash: str,
                             before_restore: Callable[[], None]) -> ProviderReceipt:
        """One preauthorized historical target, never an arbitrary restore API."""
        if (not self.enabled or not self.rollback_enabled or not self.exclusive_publisher_verified
                or not self.production_origin or candidate_id == previous_id):
            raise ProviderError("Exact historical rollback is disabled or invalid")
        candidate, previous = self.read_deploy(candidate_id), self.read_deploy(previous_id)
        if (candidate["title"] != candidate_title or previous["title"] != previous_title
                or any(deploy["draft"] is not False or not deploy["published_at"]
                       or deploy["state"] != "ready" or deploy["required"] for deploy in (candidate, previous))):
            raise ProviderError("Rollback publications do not match the approved history")
        before_restore()
        if self.current_published_id() != candidate_id:
            raise ProviderError("Concurrent publisher drift blocks historical rollback")
        result = self._request("POST", f"/sites/{self.site_id}/deploys/{self._identifier(previous_id)}/restore",
                               mutation=True)
        try:
            self._deploy(result, previous_id)
        except ProviderError as error:
            raise ProviderOutcomeUnknown("Rollback response uncertain; read publication before another action") from error
        return ProviderReceipt("netlify", "rollback_to_previous", previous_id,
            self.production_origin, request_hash, "rollback_pending_reconciliation")

    def close(self) -> None:
        super().close()
        self.health_client.close()
