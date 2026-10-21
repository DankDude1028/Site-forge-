"""Owner-operated release client; credentials stay in environment, never CLI args."""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from decimal import Decimal
from urllib.parse import urlparse
from uuid import UUID

import httpx


class ReleaseClient:
    def __init__(self, origin: str, token: str, *, transport: httpx.BaseTransport | None = None):
        url = urlparse(origin)
        if (url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}
                or not url.hostname or (url.scheme != "https" and not (
                    url.scheme == "http" and url.hostname in {"127.0.0.1", "localhost", "::1"}))) :
            raise ValueError("Supervisor origin must use HTTPS, or loopback HTTP")
        if not token:
            raise ValueError("Owner release credential is required")
        self.client = httpx.Client(base_url=origin.rstrip("/"), timeout=60, trust_env=False,
            follow_redirects=False, transport=transport,
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})

    def close(self) -> None:
        self.client.close()

    def _post(self, path: str, value: dict) -> dict:
        response = self.client.post(path, content=json.dumps(value, default=str))
        if not response.is_success:
            # Do not expose server/provider bodies, credential redirects or URLs.
            raise RuntimeError(f"Supervisor release request failed ({response.status_code}); inspect its durable record")
        result = response.json(parse_float=Decimal)
        if not isinstance(result, dict):
            raise RuntimeError("Malformed supervisor release result")
        return result

    def promote(self, preview_id: str, approval_id: str, commit_sha: str, idempotency_key: str) -> dict:
        preview_id, approval_id = str(UUID(preview_id)), str(UUID(approval_id))
        if not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", commit_sha):
            raise ValueError("Exact reviewed commit SHA required")
        if not 1 <= len(idempotency_key) <= 160:
            raise ValueError("Stable release request ID required")
        previous = self._post("/v1/releases/lookup", {"idempotency_key": idempotency_key})
        if previous.get("found") is True:
            recorded = previous.get("deployment")
            if not isinstance(recorded, dict):
                raise RuntimeError("A durable authorization exists without a dispatch record; operator reconciliation required")
            if (recorded.get("commit_sha") != commit_sha or recorded.get("approval_id") != approval_id
                    or recorded.get("environment") != "production"
                    or recorded.get("data", {}).get("execution", {}).get("idempotency_key") != idempotency_key
                    or recorded.get("data", {}).get("execution", {}).get("payload", {}).get("preview_deployment_id") != preview_id):
                raise RuntimeError("Stable release request is bound to a different approved action")
            return self.reconcile(str(recorded["id"]))
        if previous.get("found") is not False:
            raise RuntimeError("Malformed supervisor release lookup")
        plan = self._post("/v1/releases/promotion-plan", {"preview_deployment_id": preview_id})
        if (plan.get("action") != "deploy_production" or not isinstance(plan.get("payload"), dict)
                or plan["payload"].get("commit_sha") != commit_sha):
            raise RuntimeError("Ready preview does not bind the exact reviewed commit")
        execution = {key: plan[key] for key in ("action", "site_id", "payload", "amount", "currency")}
        execution["idempotency_key"] = idempotency_key
        return self._post(f"/v1/releases/{approval_id}/production", execution)

    def reconcile(self, deployment_id: str) -> dict:
        return self._post(f"/v1/releases/{UUID(deployment_id)}/reconcile", {})

    def guard_production(self, deployment_id: str) -> dict:
        return self._post(f"/v1/releases/{UUID(deployment_id)}/guard-production", {})

    def preview(self, site_id: str, commit_sha: str, directory: str, approval_id: str, idempotency_key: str) -> dict:
        site_id, approval_id = str(UUID(site_id)), str(UUID(approval_id))
        if not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", commit_sha) or not 1 <= len(idempotency_key) <= 160:
            raise ValueError("Exact reviewed commit and stable release request ID required")
        previous = self._post("/v1/releases/lookup", {"idempotency_key": idempotency_key})
        if previous.get("found") is True:
            recorded = previous.get("deployment")
            if not isinstance(recorded, dict):
                raise RuntimeError("A durable authorization exists without a dispatch record; operator reconciliation required")
            original = recorded.get("data", {}).get("execution", {})
            if (recorded.get("commit_sha") != commit_sha or recorded.get("approval_id") != approval_id
                    or recorded.get("site_id") != site_id or recorded.get("environment") != "preview"
                    or original.get("payload", {}).get("artifact_directory") != directory
                    or original.get("idempotency_key") != idempotency_key):
                raise RuntimeError("Stable preview request is bound to a different approved action")
            return self.reconcile(str(recorded["id"]))
        if previous.get("found") is not False:
            raise RuntimeError("Malformed supervisor release lookup")
        plan = self._post("/v1/releases/preview-plan", {"site_id":site_id, "commit_sha":commit_sha,
                                                       "relative_directory":directory})
        execution = {key:plan[key] for key in ("action", "site_id", "payload", "amount", "currency")}
        execution["idempotency_key"] = idempotency_key
        return self._post(f"/v1/releases/{approval_id}/preview", execution)

    def wait_for_status(self, result: dict, seconds: int, expected_status: str = "healthy") -> dict:
        if not 0 <= seconds <= 180:
            raise ValueError("Health wait must be between zero and 180 seconds")
        deadline = time.monotonic() + seconds
        def guarded(value: dict) -> dict:
            rollback = value.get("data", {}).get("execution", {}).get("payload", {}).get("rollback", {})
            if expected_status == "healthy" and value.get("status") == "health_failed" and rollback.get("enabled") is True:
                return self.guard_production(str(value["id"]))
            return value
        result = guarded(result)
        terminal = {expected_status, "failed", "health_failed", "rolled_back", "rollback_health_failed"}
        while result.get("status") not in terminal and time.monotonic() < deadline:
            time.sleep(min(2, max(0, deadline - time.monotonic())))
            result = guarded(self.reconcile(str(result["id"])))
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    promote = commands.add_parser("promote")
    promote.add_argument("--preview-id", required=True)
    promote.add_argument("--approval-id", required=True)
    promote.add_argument("--commit-sha", required=True)
    promote.add_argument("--request-id", required=True)
    promote.add_argument("--wait-seconds", type=int, default=120)
    preview = commands.add_parser("preview")
    preview.add_argument("--site-id", required=True)
    preview.add_argument("--commit-sha", required=True)
    preview.add_argument("--directory", required=True)
    preview.add_argument("--approval-id", required=True)
    preview.add_argument("--request-id", required=True)
    preview.add_argument("--wait-seconds", type=int, default=120)
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("--deployment-id", required=True)
    args = parser.parse_args()
    client = ReleaseClient(os.environ.get("SITEFORGE_API_URL", ""),
                           os.environ.get("SITEFORGE_RELEASE_TOKEN", ""))
    try:
        if args.command == "promote":
            result = client.promote(args.preview_id, args.approval_id, args.commit_sha, args.request_id)
        elif args.command == "preview":
            result = client.preview(args.site_id, args.commit_sha, args.directory, args.approval_id, args.request_id)
        else:
            result = client.reconcile(args.deployment_id)
        expected = "ready" if args.command == "preview" else "healthy"
        if args.command in {"preview", "promote"}:
            try:
                result = client.wait_for_status(result, args.wait_seconds, expected)
            except (httpx.HTTPError, RuntimeError):
                print(json.dumps(result, default=str))
                raise SystemExit("Health reconciliation unavailable; inspect the recorded deployment before another mutation") from None
        print(json.dumps(result, default=str))
        if args.command in {"preview", "promote"} and result.get("status") != expected:
            raise SystemExit("Release is not confirmed healthy; reconcile this deployment before any further mutation")
    finally:
        client.close()


if __name__ == "__main__":
    main()
