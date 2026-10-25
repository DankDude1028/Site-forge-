# Compiled bundle transfer and build modes

Bundle transfer is disabled by default. It transfers bounded compiled static bytes into the configured supervisor artifact root; it never executes a build, installs dependencies, provisions a site, contacts a provider, or publishes a deployment. The API separately requires an authenticated owner or a short-lived release token scoped to the exact site and `upload_bundle`, tenant membership, configured site bindings, and an inactive kill switch.

The build environment contains no provider or supervisor credentials. Build the trusted template with `SITEFORGE_BUILD_MODE=preview` (the default) or `production`, and `SITEFORGE_SITE_URL` set to a canonical HTTPS origin. Output remains `dist/`. Production rejects a missing origin, credentials, subpaths, queries, fragments, loopback, IP literals, and placeholder domains. Production also requires the public privacy-page details `SITEFORGE_HOST_NAME`, `SITEFORGE_HOST_PRIVACY_URL` (HTTPS) and `SITEFORGE_CONTACT_EMAIL`, which the bundle workflow takes as the `host_name`, `host_privacy_url` and `contact_email` inputs. Previews show "added before launch" placeholders instead of invented details. A build does not authorize a deployment.

| Mode | HTML robots | robots.txt | Canonical and sitemap |
| --- | --- | --- | --- |
| Preview | `noindex, nofollow` on every page | `Disallow: /` | Exact preview origin |
| Production candidate | `index, follow` on every page | `Allow: /` and exact sitemap URL | Explicit configured HTTPS origin |

Indexing metadata is not access protection. The production candidate remains a protected provider draft until a separate exact release approval promotes its verified bytes. It must link to an already reviewed ready preview for the same site and commit. The release service checks that linkage against its durable deployment records; the filesystem helper alone cannot establish that the supplied preview ID is reviewed or ready.

## Manifest and provenance

`BundleManifest` version 1 contains the internal site UUID, exact lowercase Git commit SHA, mode, canonical origin, files (`path`, full SHA256, exact byte count), and, for production, `preview_deployment_id` and `source_preview_tree_sha256`. File entries are normalized into sorted order. Production's canonical origin must additionally match the server's independent per-site allowlist.

`BundleStore.begin(manifest, org_id=..., uploader=...)` binds the normalized manifest to the authenticated principal's organization and subject. A full SHA256 over that canonical manifest plus provenance is both `bundle_id` and `manifest_sha256`; changing identity, commit, source-preview linkage, mode, or bytes produces another identity. The principal values come from server authentication, never from model output or a caller's manifest fields. The commit/uploader binding is an **authenticated uploader claim, not independent GitHub attestation**. The helper does not independently prove that a workflow built the claimed commit.

The API sends each binary file through `upload(bundle_id, path, content, org_id=..., uploader=...)`. The exact path, length, SHA256, and original principal must match. Replaying identical uploads is safe. `describe(...)` returns metadata without file bytes and reports `staging` or `sealed`. `finalize(...)` verifies every byte, rejects extra or missing files, validates compiled HTML/robots/sitemap, and atomically publishes `b/<full SHA256>/files` under the configured artifact root. The returned `relative_directory` is the release-plan input. Publication interrupted before the directory rename remains staging; finalize can resume without rebuilding or uploading new bytes.

The immutable sibling `b/<SHA256>/manifest.json` records provenance and derived file-tree SHA256. It is outside `files/` and is not deployed. `inspect_bundle(root, relative_directory)` independently revalidates this metadata and the complete compiled tree before release planning. The derived tree digest uses the existing release tuple contract `(path, SHA1, SHA256, bytes)`, sorted by path; SHA1 is solely the provider's required file-transfer identifier, while approvals and bundle integrity use SHA256.

## Bounds and operating limits

Each bundle permits at most 1,000 files, 4,000,000 bytes per file, and 16,000,000 bytes total. There are at most 16 staging and 128 sealed bundles per root. Global registry locking serializes capacity decisions; 256 fixed lock stripes bound lock metadata even for rejected requests. A busy lock fails promptly so a client can retry its identical request. Sealed replay rehashes the complete tree. No approved bytes are automatically deleted to make capacity.

Portable ASCII paths reject traversal, absolute paths, backslashes, case-fold collisions, Windows reserved filenames, dotfiles, sensitive directories, archives, source maps, private keys, common credential patterns, and host-executable extensions. Only static web extensions are accepted. JavaScript and fonts remain passive bytes during transfer; no host command is exposed. Symlinks, Windows junctions/reparse points, and linked output files are rejected. Credential-pattern checks are a bounded additional check, not proof that arbitrary output contains no secret; CI must isolate credentials from builds and retain secret scanning.

Absolute artifact paths are limited to 240 characters before publication to accommodate Windows systems without long-path support. Choose a shorter operator-controlled `SITEFORGE_PREVIEW_ROOT` if a valid asset path would exceed that limit; the helper fails before creating bundle files. The root is trusted local storage and must not be writable by unrelated OS principals. File-lock coordination covers cooperative server processes; it is not an OS sandbox against a malicious local account replacing filesystem entries between checks.

Operator retention requires reviewing staged failures and approved/deployed references before removing anything. There is currently no automatic garbage collector or cryptographic GitHub OIDC artifact attestation. Tokens, provider authorization, and secrets must never be placed in manifests or compiled output. No live deployment or production acceptance is implied by a sealed bundle.

## Local verification

The focused bundle/factory/agent/API run passed 79 tests, with one Windows symlink-privilege skip; the real Windows junction rejection test passed. TypeScript, Python type checks, lint, and whitespace validation passed. Eight Node tests include actual Astro compilation of both modes and inspection of each generated HTML, robots, and sitemap file. Playwright passed four desktop/mobile calculator, crawl-metadata, and axe accessibility checks for each mode (eight browser checks total). A real compiled preview (five files, 15,438 bytes at verification time) was transferred and finalized in an isolated temporary root without executing its contents. These are local implementation checks, not provider protection, production health, GitHub attestation, or live publishing evidence.
