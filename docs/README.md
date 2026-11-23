# Documentation index

This is the navigation entry point for CS2 Map Balance documentation. Documents
are grouped by purpose and marked as **current**, **reference**, or **historical**.
Most deep technical notes are in Russian and are preserved in their original
language; the public entry points are bilingual.

Start with the [project README](../README.md) or the
[Russian README](../README.ru.md) for the product overview.

## Current state and guides

| Document | Status | Contents |
|---|---|---|
| [STATE.md](STATE.md) | Current | Evolving project state, verified results, active priorities and known gaps |
| [SETUP.md](SETUP.md) / [SETUP.ru.md](SETUP.ru.md) | Current | Installation, map generation, Source2Viewer-CLI and troubleshooting |
| [GETTING_FILES.md](GETTING_FILES.md) / [GETTING_FILES.ru.md](GETTING_FILES.ru.md) | Current | Manual extraction of `.nav`, entities and physics glTF |
| [RELEASE.md](RELEASE.md) / [RELEASE.ru.md](RELEASE.ru.md) | Current | Application release summary and verification scope |
| [SECURITY.md](SECURITY.md) / [SECURITY.ru.md](SECURITY.ru.md) | Current | Threat model, controls, CS2/anti-cheat boundaries and residual risks |
| [SECURITY_BACKLOG.md](SECURITY_BACKLOG.md) | Current | Prioritized security-management work and acceptance criteria |

## Architecture and methodology

| Document | Status | Contents |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Reference | Data flow, module boundaries, bundle formats and implementation status |
| [PROJECT.md](PROJECT.md) | Historical brief | Original goals, definitions, data layers and early open decisions |
| [DECISIONS.md](DECISIONS.md) | Reference | Architecture decision records (ADRs), including superseded decisions |
| [VALIDATION.md](VALIDATION.md) | Reference | Independent validation levels for data, nav, collision, movement and balance |

## Research and measurements

| Document | Status | Contents |
|---|---|---|
| [RESEARCH.md](RESEARCH.md) | Historical research | Source 2 tooling, VPK/NAV formats, entity and physics sources, provenance |
| [MAP_DATA.md](MAP_DATA.md) | Historical measurements | Dust2 data census, nav/entity/collision experiments and anomaly notes |
| [MOVEMENT.md](MOVEMENT.md) | Historical measurements | Measured convars and speeds, movement model, jump values and limits |
| [SIMULATION.md](SIMULATION.md) | Reference | Time-only rush/split envelopes and the route-time balance heuristic |
| [FINAL_REPORT.md](FINAL_REPORT.md) | Historical report | Early feasibility study and initial implementation plan |

Historical measurements remain valuable evidence, but they describe the game
build and conditions recorded in each document. They are not automatically a
validation of the current CS2 build.

## Roadmap, releases and risks

| Document | Status | Contents |
|---|---|---|
| [ROADMAP.md](ROADMAP.md) | Current | Staged plan, acceptance criteria, dependencies and deferred work |
| [RISKS.md](RISKS.md) | Reference | Technical, methodological, legal and scope risks |
| [releases/pre-alpha-v1.0.md](releases/pre-alpha-v1.0.md) / [RU](releases/pre-alpha-v1.0.ru.md) | Current | Clean `cs2mb-tool` baseline |
| [releases/](releases/) | Historical | Earlier 2.x release notes, retained as project history |
| [CHANGELOG.md](../CHANGELOG.md) | Current | Chronological change log |

### Release naming note

- The application version in [`VERSION`](../VERSION) is `pre-alpha v1.0`.
- The `cs2mb-tool` repository is a fresh baseline. Earlier 2.x release notes are
  kept under [`releases/`](releases/) as historical project records.
- The current baseline note is [pre-alpha v1.0](releases/pre-alpha-v1.0.md).
- `docs/releases/v2.1.0-alpha.md` contains the alpha.1 notes; the file name is
  kept for link stability.
- `docs/releases/v2.0.0-alpha.md` contains the 2.0.0-alpha.1 notes for the same
  reason.

## Repository-level documents

| Document | Contents |
|---|---|
| [README.md](../README.md) / [README.ru.md](../README.ru.md) | Public project overview and quick start |
| [AGENTS.md](../AGENTS.md) | Operating contract for AI coding agents |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Contribution scope, safety rules and checks |
| [CHANGELOG.md](../CHANGELOG.md) | Change history |
| [LICENSE](../LICENSE) | MIT license |

## Published-site note

The GitHub Pages workflow is enabled for this repository. It publishes the
READMEs, security documents, website assets and selected images, but not the
complete `docs/` tree. Links in this index are repository links and
resolve on GitHub; some will not resolve on the published Pages copy of the README.
The workflow is intentionally outside this documentation-maintenance scope.

## Documentation conventions

- **Measured** values are tied to a named game build, map, date and method.
- **Tested** claims are reproduced by a named test or command.
- **Inferred** conclusions follow from stated evidence.
- **Heuristic** estimates are explicit models, not measurements.
- **Planned** work is not described as implemented.
- Route distance, travel time, estimated travel time, movement measurements and
  competitive balance are distinct terms and are not used interchangeably.

When updating documentation, keep links stable where possible and update the
relevant [STATE.md](STATE.md) entry when behavior, measurements, assumptions or
release scope changes.
