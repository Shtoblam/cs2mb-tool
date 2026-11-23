# Security management backlog

**Status:** active  
**Scope:** local application server, upload/path handling, process execution, viewer security and documentation.

This backlog tracks security work that is larger than a documentation correction. It is intentionally separate from map-analysis research. No item here authorizes a change to game files or game processes.

## Completed in the pre-alpha v1.0 baseline

- Added restrictive CSP, `Referrer-Policy: no-referrer` and `Cross-Origin-Resource-Policy: same-origin` response headers to the intake UI.
- Kept the matching UI CSP/referrer meta policies.
- Added a regression test for the UI response-header constants.
- Clarified the security documentation so response headers and meta policies are not conflated.

## Open work, highest priority first

| Priority | Item | Current behavior | Acceptance criteria |
|---|---|---|---|
| P1 | Bounded job execution | `app/server.py` starts jobs without a concurrency cap and keeps job records in memory for the server lifetime. | A documented limit, controlled rejection/queue behavior, cleanup of old job state, tests for the limit and clean shutdown. |
| P1 | Process-tree timeout | The 900 s timeout kills the Python child process, but Windows descendants such as `resourceinfo.exe` or Source2Viewer-CLI may survive. | Timeout terminates the full process tree on Windows; equivalent behavior is defined for other platforms; testable without a real game install. |
| P2 | Endpoint-level security tests | Tests cover helper functions and selected routes, but not oversized uploads, malformed multipart bodies, traversal attempts, viewer confinement or timeout behavior. | Runtime tests for each boundary, including negative cases and bounded resource use. |
| P2 | Host-header and CSRF hardening | POSTs have an Origin check, but no Host allow-list and no CSRF token; requests without an Origin header remain possible. | Explicit loopback Host policy, documented local-client behavior, and tests for allowed/denied cases. |
| P2 | Remote-binding warning/controls | `--allow-remote` permits a non-loopback bind without authentication. | Strong warning, minimal allow-list, or an explicit authentication gate before remote exposure. |
| P3 | Direct CLI map-name validation | `tools/auto_generate.py` accepts arbitrary `--map` values. | Validate map names consistently with the server and test rejection of traversal/invalid names. |
| P3 | Upload-directory lifecycle | Validation failures can leave upload directories behind; there is no retention policy. | Cleanup on rejected jobs and a documented retention policy for completed uploads. |

## Working rules

- Keep the server loopback-only by default.
- Keep all game-resource access read-only.
- Do not add remote telemetry or external services to fix a local security issue.
- Add a focused failing test before changing parser, path, upload, process or server behavior.
- Re-run `python -m unittest discover -s tests`, `python tools/security_scan.py` and the Markdown checks after changes.
- Record any remaining limitation in `docs/SECURITY.md` and `docs/STATE.md`.
