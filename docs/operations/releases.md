# Approved releases and recovery

The implemented path connects an exact owner approval to a durable authorization intent,
one claimed provider dispatch, provider reconciliation and bounded health checks. It is disabled
by default. No live Netlify mutation was executed here: the Netlify connection requires
reauthentication, and protected-preview acceptance remains blocked. Mocked provider/API tests
establish control flow, not a deployed preview or production release.

## Server and artifact prerequisites

Configure an existing Netlify site; these endpoints do not create sites, buy services or change
access controls. Stage reviewed **compiled static output** inside the supervisor's configured
`SITEFORGE_PREVIEW_ROOT`. A relative artifact directory is resolved there, not on the GitHub runner.
The operator must transfer the bundle and verify its provenance before planning a release.

The planner requires `index.html`, `content="noindex, nofollow"` in every HTML file, no linked or
sensitive paths, at most 1,000 files, 4 MB per file and 16 MB total. It binds relative filenames,
SHA1 upload digests, SHA256 hashes and byte sizes. Files are checked again before dispatch/upload.
The supplied exact commit SHA and artifact tree are separately bound to the approval; this is
**not a cryptographic attestation that the bundle was built from that commit**.

| Server setting | Meaning |
| --- | --- |
| `SITEFORGE_RELEASE_ENABLED` | Defaults to `false`; enables configured release orchestration. |
| `SITEFORGE_RELEASE_SITE_BINDINGS` | JSON map from internal SiteForge site UUID to exact Netlify site UUID. |
| `SITEFORGE_PREVIEW_ROOT` | Scoped directory containing the already staged reviewed bundles. |
| `SITEFORGE_RELEASE_PROTECTED_SITES` | JSON list of Netlify site UUIDs whose private access protection the operator has verified. A noindex tag is not access control. |
| `NETLIFY_AUTH_TOKEN` | Protected supervisor-side provider credential; never passed to a model or workflow client. |
| `SITEFORGE_PREVIEW_AUTHORIZATION` | Supervisor-side Basic authorization for private health probes. Anonymous checks explicitly strip credentials/cookies. |
| `SITEFORGE_RELEASE_KNOWN_COST_USD` | Required attestation of complete operation cost; missing cost blocks planning/execution. Zero must be explicitly justified, not inferred from a free-tier label. |
| `SITEFORGE_RELEASE_MAX_COST_USD` | Server cost ceiling, default zero. Execution amount/currency must exactly match the USD plan. Nonzero effects also require owner-configured daily/monthly policy budgets and any task cap. |
| `SITEFORGE_RELEASE_PRODUCTION_ENABLED` | Defaults to `false`; separate production promotion gate. |
| `SITEFORGE_RELEASE_PRODUCTION_ORIGINS` | JSON map from Netlify site UUID to independently allowlisted HTTPS production origin. |
| `SITEFORGE_RELEASE_EXCLUSIVE_PUBLISHER` | Explicit operator attestation that outside publishers will not race the checked previous published deploy. Defaults to `false`. |
| `SITEFORGE_RELEASE_RESUME_UPLOADS_ENABLED`, `SITEFORGE_RELEASE_RESUME_COST_USD` | Optional upload-recovery gate; disabled by default and requires an explicit zero incremental cost. |
| `SITEFORGE_RELEASE_ROLLBACK_ENABLED`, `SITEFORGE_RELEASE_ROLLBACK_COST_USD` | Optional automatic health recovery; defaults disabled. Requires an explicit `0` incremental cost and a previously healthy SiteForge production release. Unknown or positive rollback costs are unsupported and refused. |

These settings are trusted operator configuration. Enabling a flag does not itself prove protection,
known costs, exclusive publishing, deployment health or full production acceptance.

## Credentials and approving identity

An owner requests and decides approvals. A workflow should use a short-lived `Principal` with
`role: "release"`, explicit internal `site_ids`, only its required capabilities, and an expiry no
more than 24 hours ahead. Its `subject` must equal the owner identity that actually approved the
action. The service checks that identity before dispatch; a different generic CI actor cannot use
the approval.

Example registry **value**, with placeholders that must be supplied through protected configuration:

```json
{
  "subject": "approving-operator-example",
  "org_id": "00000000-0000-0000-0000-000000000001",
  "role": "release",
  "site_ids": ["00000000-0000-0000-0000-000000000002"],
  "capabilities": ["plan_release", "deploy_preview", "reconcile_release"],
  "expires_at": "<aware UTC timestamp within the next 24 hours>"
}
```

Install it in the supervisor's `SITEFORGE_AUTH_TOKENS` JSON map under the **lowercase SHA256 digest
of the random bearer token**, not the raw token. Preserve the other required owner/worker entries:
when this map is nonempty, the convenience owner/worker environment fallback is not added.
The registry is read at application startup. Deliver only the corresponding bearer token to the
client's protected `SITEFORGE_RELEASE_TOKEN` environment/secret. Setting that variable alone does
not register a server identity. Add `deploy_production` only for the intended production credential.

Delegated release credentials cannot approve/reject actions, change budgets/kill switch, read the
general control plane, or call the owner-only upload-resume endpoint. Their permitted release reads
and operations remain tenant/site/capability scoped. Do not use a long-lived owner token as a
substitute for this narrower workflow credential.

## Preview: plan, approve, execute, reconcile

The UUIDs and commit below are illustrative placeholders, not a runnable release authorization.
Send authenticated JSON to the supervisor over HTTPS, or loopback HTTP for local fixtures.

1. `POST /v1/releases/preview-plan` with `plan_release` scope:

   ```json
   {
     "site_id": "00000000-0000-0000-0000-000000000002",
     "commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
     "relative_directory": "reviewed-preview-bundle"
   }
   ```

   Preserve the returned `action`, `site_id`, complete `payload`, `amount` and `currency`. The payload
   includes the provider site, commit, exact file manifest/tree hash and approved upload-resume terms.

2. As owner, `POST /v1/approvals` using those five fields **unchanged**, adding
   `agent_type: "developer"`, a stable approval-request `idempotency_key`, and an appropriate
   `expires_in_seconds` (60–86,400; default 3,600). This requests an approval; it does not deploy.
   Keep its returned approval UUID and payload hash. The approval-request key and execution key
   below are distinct durable bindings.

3. The owner reviews the exact bundle, amount/site/commit and payload hash, then calls
   `POST /v1/approvals/{approval_id}/approve`:

   ```json
   {"reason": "Owner reviewed this exact protected preview bundle and cost"}
   ```

   Rejection uses the corresponding `/reject` endpoint. A delegated release credential cannot
   perform this decision. A generic authorization receipt alone is not provider-effect evidence;
   normal release execution obtains its own bound intent through the service.

4. Execute `POST /v1/releases/{approval_id}/preview` with the same five plan fields plus one stable
   execution `idempotency_key`, or use the client after the approval is recorded:

   ```text
   python -m siteforge.release_client preview --site-id <internal-site-uuid> --commit-sha <exact-sha> --directory reviewed-preview-bundle --approval-id <approval-uuid> --request-id preview-request-example-001
   ```

   The service checks the approving subject, policy/expiry/kill switch, known cost and unchanged tree;
   reserves the authorization intent; and commits its dispatch claim before contacting Netlify.
   It stores the provider deploy identity before uploading requested known file digests.

5. Inspect the deployment record and reconcile. `ready` requires provider readiness, no missing
   digests, denied anonymous access (401/403), authorized HTTP 200 and exact approved `index.html`
   SHA256. Redirects, unexpected identities and mismatched content fail the check. This bounded
   index/protection check does not replace asset, browser, accessibility or load testing.

The client reads `SITEFORGE_API_URL` and `SITEFORGE_RELEASE_TOKEN`; credentials are not CLI arguments.
It waits for `ready` for previews or `healthy` for production (120 seconds by default, at most 180),
using reconciliation calls. A nonzero exit, timeout, provider receipt or workflow artifact upload
does not by itself establish healthy hosting.

## Stable identity and uncertain outcomes

Before repeating an attempted execution, reuse its **same** execution key:

```text
POST /v1/releases/lookup
```

```json
{"idempotency_key": "preview-request-example-001"}
```

`found: false` means no matching local authorization intent was recorded. `found: true` returns the
bound deployment, or `intent_only: true` with a receipt ID if authorization exists without its
dispatch row. The latter is an orphan intent: preserve it and investigate; the client refuses to
turn it into another effect automatically. Never invent a new key merely to bypass uncertainty.

A replayed deployment is reconciled, not dispatched again. The claim intentionally favors avoiding
duplicate external effects over availability, including a crash between claim and provider request.
Netlify's bounded correlation lookup examines at most three pages of 100 deploys; absence there
does not prove that no effect occurred.

`POST /v1/releases/{deployment_id}/reconcile` with an empty JSON body, or
`python -m siteforge.release_client reconcile --deployment-id <deployment-uuid>`, performs only
**external reads**. It may update local audit/deployment/budget state. It never creates another draft,
reuploads files or retries a promotion. Preserve `unknown`, `processing`, `health_failed` and failed
records rather than interpreting them as permission to redrive a mutation.

Authorization is a reserved intent; a provider deploy receipt identifies an observed mutation;
health is a separate result. Reconciliation can settle the server-attested mutation cost before
health succeeds. `cost_reconciled` explicitly does **not** mean a verified provider invoice, complete
recurring hosting costs or realized economics. Reconcile actual provider costs separately.

## Explicit bounded upload recovery

Only the original approving **owner** may call
`POST /v1/releases/{deployment_id}/resume-preview` with an empty JSON body. This is an external
mutation, separate from read-only reconciliation. It requires all of the following:

- Server recovery enabled, server-attested zero incremental cost, and those exact recovery terms
  present in the original approved payload.
- Same approving subject, unexpired original approval, permitted receipt state and inactive kill switch.
- Exact known unpublished provider draft and correlation identity, with only known required digests.
- Unchanged approved file manifest, SHA256 hashes and sizes.

At most two durable recovery attempts are permitted, with a 120-second fenced claim and at most
ten same-hash file PUTs per attempt. Checks run before each new PUT. An expired/fenced attempt may
finish its already in-flight identical PUT but cannot start another. Recovery never creates a new
deploy or retries production promotion. Unknown cost, changed bytes, missing identity or exhausted
attempts require operator review rather than widening the existing approval.

## Production promotion and current limits

With the separate production gates configured, request `POST /v1/releases/promotion-plan`:

```json
{"preview_deployment_id": "00000000-0000-0000-0000-000000000003"}
```

The plan requires a reconciled protected `ready` **production candidate**, not the ordinary noindex
preview. First transfer/finalize a separate `production` bundle using the authenticated
[bundle workflow](bundles.md). Its manifest binds the same site/commit, the reviewed normal preview
deployment and source tree, and the exact indexable production tree. Every HTML canonical,
index/follow metadata, robots allow policy and sitemap must match the independently configured
production origin. Bundle uploader and organization are server-authenticated; the commit remains
an authenticated uploader claim, not independent proof of a GitHub build.

Planning that production candidate requires the linked normal preview to remain ready/private,
with the same site/commit and source-tree hash. The candidate itself is deployed as a protected
draft, retaining indexable production bytes behind access control. Promotion rejects legacy
noindex previews and revalidates both bundle provenance and the source-preview linkage. The plan
binds internal/provider identities, both trees, manifest, commit, amount and **previous published
deploy ID**. Request and obtain a new owner
approval for the returned `deploy_production` action, then execute
`POST /v1/releases/{approval_id}/production` with the exact plan and a stable execution key, or:

```text
python -m siteforge.release_client promote --preview-id <preview-deployment-uuid> --approval-id <production-approval-uuid> --commit-sha <exact-sha> --request-id production-request-example-001
```

The adapter promotes only that new, unpublished ready draft after checking the previous published
identity and protection again. Production reconciliation verifies the published deploy
identity and exact index bytes at the independently configured production HTTPS origin.

## Preauthorized automatic health rollback

Rollback is disabled by default. With its separate server flag and explicitly known zero
incremental cost configured, the production plan additionally contains an immutable `rollback`
object. It names the current candidate, exact previous provider and internal production release,
site, approving identity, previous/candidate commits and trees, historical provider title and
previous verified index SHA256. The owner reviews these terms as part of the **same production
approval**. The approval amount includes the normal operation cost plus the explicit zero rollback
increment; existing daily/monthly/task budget reservation rules still apply. Positive/unknown
rollback costs are refused rather than estimated or charged as if an unused reserve were spent.

The previous target must be a durable, previously healthy SiteForge production release that is
currently published and whose index bytes still verify. A first launch, missing historical record,
ambiguous history or unrelated provider deploy cannot claim rollback coverage; planning with
rollback enabled refuses those cases. This is not a general restore-to-any-deploy feature.

`POST /v1/releases/{deployment_id}/guard-production` is an explicit mutation entry point. It requires
the original approving identity and owner scope or the site-scoped `guard_production` capability.
The release client/workflow invokes it automatically after an observed production `health_failed`
result when the approved rollback terms are present; immediate health failure during execution
uses the same guard. The guard rechecks health before acting, refuses publisher drift/unknown state,
and commits a durable rollback claim before its one provider restore request. The adapter rechecks
the exact candidate and historical target and the current publication immediately before dispatch.

The kill switch remains effective for new publications, spending and upload recovery. Its single
emergency exception permits only this already-approved zero-cost rollback to the bound previous
target. It cannot select another target, bypass the approving identity/expiry, change configuration,
or create another authorization. An expired approval still blocks a new rollback claim.

After a claim, process crashes, uncertain responses, repeated guards, lookup and reconciliation
perform provider reads only; they never repeat the restore. A crash before the request can therefore
remain `rollback_unknown` and require operator investigation. `rolled_back` means the exact previous
publication and its index health were observed. `rollback_health_failed` means that target published
but its health did not verify. Neither status means the new candidate succeeded; the production
workflow exits unsuccessfully after rollback and preserves its evidence. There is no live-provider
acceptance claim from mocked transport tests. Full production acceptance and operational gates
remain pending.

## GitHub workflow wiring

The manually dispatched [staging workflow](../../.github/workflows/staging.yml) requires repository
variable `SITEFORGE_PREVIEWS_ENABLED=true`, the `protected-preview` environment, `SITEFORGE_API_URL`
and protected secret `SITEFORGE_RELEASE_TOKEN`. Inputs are exact `ref`, internal `site_id`, staged
`directory`, exact `approval_id` and stable `request_id`. It checks out the ref but **does not build,
transfer or attest a bundle**: the reviewed compiled bundle must already exist in the supervisor root.

The manually dispatched [production workflow](../../.github/workflows/production.yml) separately
requires repository variable `SITEFORGE_PRODUCTION_ENABLED=true`, the `production` environment,
the API URL and a properly scoped short-lived release secret. Include `guard_production` only when
that credential is intended to perform the exact preauthorized health recovery. Inputs bind `commit_sha`,
`approval_id`, `preview_id` and stable `request_id`. It promotes the recorded preview rather than
deploying checkout contents. Repository workflow variables are distinct from supervisor
`SITEFORGE_RELEASE_*` configuration; both layers must be deliberately configured.

Both workflows attempt to upload produced client JSON even after failure; a missing/empty artifact
requires durable lookup and does not establish absence of an effect. Configure environment
protection, required checks and credential issuance/rotation before
enabling them. No workflow was dispatched and no live provider effect was performed for this
documentation. Existing adapter notes are narrower historical scope; the current implementation is
in [release.py](../../siteforge/release.py), [providers.py](../../siteforge/providers.py),
[release_client.py](../../siteforge/release_client.py) and [API routes](../../siteforge/api.py).
