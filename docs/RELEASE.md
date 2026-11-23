# RELEASE pre-alpha v1.0 — fresh repository baseline

**Application version:** `pre-alpha v1.0`

This is the initial clean baseline of the `cs2mb-tool` repository. It preserves
the documented analysis scope of the 2.x work while resetting the repository
identity and current version.

## Included

- read-only CS2 map intake, NAV parsing, entities and collision diagnostics;
- local viewer, route/profile output and map library;
- time-only rush/split scenarios and route-time comparison;
- local loopback server with upload/path controls and job timeout;
- bilingual documentation and setup guides;
- current `VERSION` value: `pre-alpha v1.0`.

## Limits

- no detection/encounter timing, combat, utility or win-rate prediction;
- route-time output is a preliminary heuristic, not a match-balance verdict;
- movement remains straight-line calibrated and is not demo-tick validated;
- historical 2.x release notes under `docs/releases/` remain historical records.

## Verification

Current verification covers 56 unit tests, Python compilation, the repository
hygiene scan, Markdown link/anchor/fence validation and asset integrity checks.
See [STATE.md](STATE.md).

## Historical release notes

The previous 2.x release notes are retained as historical project records:
[releases/](releases/).

## Russian version

[RELEASE.ru.md](RELEASE.ru.md).
