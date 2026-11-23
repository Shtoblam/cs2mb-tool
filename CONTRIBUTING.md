# Contributing

This is an alpha research project. Keep changes small, reproducible and
evidence-based. The project values correctness, traceability and honest
uncertainty more than feature count.

## Before you start

- Read [AGENTS.md](AGENTS.md) if you are an AI coding agent.
- Read [docs/STATE.md](docs/STATE.md) for the current project state.
- Read [docs/README.md](docs/README.md) for the documentation map.
- Check [docs/ROADMAP.md](docs/ROADMAP.md) before starting larger work.

## Scope

Accepted for the current alpha line:

- map intake, viewer, navigation and collision diagnostics;
- movement-model calibration and validation;
- local server security, performance and reliability fixes;
- documentation, extraction guides and reproducible examples;
- tests that catch regressions or invalid assumptions.

Deferred:

- combat, win-rate prediction and dynamic side strength;
- detection/encounter timing (Release 2.2);
- full 3D visualization;
- broad refactors or new dependencies without a demonstrated need.

## Repository layout

```text
app/          local server and web intake UI
tools/        read-only research tools and generation pipeline
movement/     measured movement and route-time models
simulation/   time-only rush/split scenarios and balance heuristic
prototype/    generated viewer template and builder
tests/        synthetic unit and security-contract tests
docs/         research, architecture, validation, security and releases
inputs/       local map inputs (ignored except README)
config/       runtime configuration and movement profile
```

## Checks

Run the checks relevant to your change. The standard project checks are:

```powershell
py -3.13 -m unittest discover -s tests -v
py -3.13 tools\security_scan.py
py -3.13 -m compileall -q app tools movement simulation prototype
```

For parser, path, upload, process or server changes, add focused adversarial tests
and review the security implications manually. A passing scanner is not a
security proof. Do not change tests merely to make an implementation pass; update
expected results only for an intentional, documented behavior change.

## Safety rules

Do not commit:

- VPK, `.nav`, physics glTF/`.bin`, demos or extracted map assets;
- `.env`, tokens, API keys, passwords or personal paths;
- generated `artifacts/`, uploads or large derived data;
- downloaded executables such as Source2Viewer-CLI or the built
  `cs2mb-sri` engine binary; publish the engine as a hash-verified release
  asset instead.

Do not modify the CS2/Steam installation, interact with game processes or memory,
automate gameplay, or connect to game servers/anti-cheat for this project.

## Documentation

- Keep user-facing claims labeled as measured, tested, inferred, heuristic or
  planned.
- Do not interchange navigation distance, travel time and competitive balance.
- Update the relevant document and [docs/STATE.md](docs/STATE.md) when behavior,
  measurements, assumptions or release scope change.
- Keep English and Russian documentation technically equivalent where both
  versions exist.

## SRI changes

When changing `sri/` or `tools/sri.py`:

- build the self-contained engine with `sri/build.ps1`;
- run the Python suite with `CS2MB_SRI` set to the built executable;
- keep the synthetic malformed/truncated/oversized resource tests passing;
- re-run the nine-map integration validation when SRI physics/entity decoding
  changes;
- update `sri/THIRD_PARTY_NOTICES.md` when a dependency changes.

## Pull requests

Describe:

1. what changed and why;
2. the exact checks run and their observed outcomes;
3. security implications;
4. limitations or remaining uncertainty;
5. any follow-up work.

Do not include generated game resources, private environment paths or unrelated
changes.

## Code style

- Python 3.13, standard library first.
- Subprocesses use argument lists, never `shell=True`.
- New parsing, path, upload or routing behavior needs a focused test.
- User-visible claims must state whether they are measured, inferred, heuristic
  or planned.

## Security reports

Read [docs/SECURITY.md](docs/SECURITY.md). Report vulnerabilities through
GitHub private security advisories, not public exploit issues. Include the
affected version or commit, a minimal reproduction, whether the game was
running, and whether the issue is local-only or requires an origin-guard bypass.
