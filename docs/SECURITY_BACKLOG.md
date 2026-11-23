# Security management backlog

**Status:** active
**Scope:** local application server, upload/path handling, process execution,
SRI, viewer security and documentation.

This backlog tracks security work larger than a documentation correction. No
item here authorizes a change to game files or game processes.

## Completed in `v1.1.0`

- Added 3DsVW confined asset and job-bundle routes with regex map/job IDs,
  resolved-path confinement and 404 handling for traversal/invalid paths.
- Added glTF normalization and limits: external buffer rejection, buffer length
  check, texture/image stripping, node/accessor and triangle caps.
- Added viewer-specific endpoint tests and builder tests.
- Added a strict 3DsVW CSP with no inline scripts and same-origin connections.
- Kept loopback-only binding, Host/Origin checks, upload limits, job limits and
  process-tree timeouts unchanged.
- Added settings persistence without accounts or external services.

## Completed in `v1.0.0-pre.1`

- Added the internal **SRI** component with explicit path resolution, argument
  arrays, timeouts and SHA-256 provenance.
- Removed the Source2Viewer-CLI and `resourceinfo.exe` runtime paths.
- Added a maximum of two simultaneous jobs with controlled `429` rejection.
- Added stale job-record cleanup and upload-directory retention.
- Added Windows process-tree termination on timeout, including descendants.
- Added endpoint-level tests for Host, Origin, oversized uploads, malformed
  multipart data, traversal, extensions, missing sidecars, invalid JSON and
  viewer confinement.
- Added a loopback Host allow-list and same-origin POST checks; missing Origin
  is rejected.
- Disabled remote binding (`--allow-remote` is rejected).
- Added map-name validation to the direct auto-generation CLI.
- Removed rejected upload directories and added upload retention cleanup.
- Redacted personal absolute paths from preparation manifests.
- Pinned third-party GitHub Actions to immutable commit SHAs.
- Added SBOM and release checksum generation.

## Open work

| Priority | Item | Current behavior | Acceptance criteria |
|---|---|---|---|
| P2 | Viewer HTML hardening review | Viewer HTML is generated locally and served with a restrictive CSP, but the generator is not a browser sandbox. | Add a generated-content injection review with adversarial entity/callout strings and a documented policy. |
| P3 | Full endpoint fuzzing | Targeted endpoint tests exist; continuous malformed-request fuzzing is not automated. | Bounded fuzz run in CI with a documented corpus and no unbounded resource use. |
| P3 | Code signing | SRI is hash-verified but not code-signed. | Sign the release executable if a suitable certificate and release policy exist. |
| P3 | Cross-platform SRI | SRI is Windows x64 only. | Define and test a supported Linux/macOS build if required. |

## Working rules

- Keep the server loopback-only; remote binding stays disabled.
- Keep all game-resource access read-only.
- Do not add remote telemetry or external services to fix a local security issue.
- Add a focused failing test before changing parser, path, upload, process or
  server behavior.
- Re-run `python -m unittest discover -s tests`, `python tools/security_scan.py`
  and the Markdown/asset checks after changes.
- Record any remaining limitation in `docs/SECURITY.md` and `docs/STATE.md`.
- Do not describe the application as perfectly secure; these controls reduce
  risk but are not a security certification.
