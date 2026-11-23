# Changelog

## v1.0.0-pre.1 — 2026-11-23

### Source 2 processing

- Renamed the internal component to **SRI — Source Resource Inspector**
  (`cs2mb-sri.exe`, `sri/`, `tools/sri.py`, `CS2MB_SRI`, `--sri`,
  `sri_ready`, `sri_version`, `sri_sha256`).
- SRI reads compiled PHYS and EntityLump resources in-process with the pinned
  MIT ValveResourceFormat `20.1.7467` library.
- Removed Source2Viewer-CLI and `resourceinfo.exe` from the normal runtime.
- Preserved mesh/hull geometry, bounded sphere/capsule tessellation, Hammer
  units/Source axes, `InteractAs`/`SurfaceProperty`/`CollisionGroup` metadata
  and the existing glTF/entity contracts.
- Preparation manifests now record SRI path/version/hash and use relative
  provenance (`<CS2_GAME>`, `prepared/...`) instead of personal paths.

### Application

- Added a complete Windows x64 package with a portable Python 3.13 runtime,
  `Start-CS2MB.bat` and `Start-CS2MB.ps1`.
- The package includes SRI at `tools/bin/sri/cs2mb-sri.exe`; users no longer
  download a separate converter.
- Existing NAV parsing, routing, collision, movement, simulation, viewer,
  library, upload and comparison functionality is preserved.
- Version reconciled to `v1.0.0-pre.1` across the application, UI, site, docs,
  package metadata and release links.

### Security

- Added a two-job concurrency limit with controlled `429` rejection.
- Added stale job-record cleanup and upload-directory retention.
- Added Windows process-tree termination on timeout, including SRI descendants.
- Added loopback Host allow-listing and same-origin POST checks; missing Origin
  is rejected.
- Disabled remote binding; `--allow-remote` is rejected.
- Added endpoint tests for oversized uploads, malformed multipart bodies,
  traversal, invalid extensions, missing sidecars, invalid JSON, viewer
  confinement, rejected origins and job limits.
- Removed rejected upload directories.
- Added direct map-name validation to the auto-generation CLI.
- Pinned GitHub Actions to immutable commit SHAs.
- Added SPDX SBOM and release checksum generation.
- Documented remaining limitations; SRI is not code-signed.

### Visual identity and repository

- Restored the owner's original `logo.png` byte-for-byte as the canonical mark.
- Removed invented vector logo variants and the obsolete tutorial/site
  screenshots.
- Rebuilt banners, SRI/pipeline diagrams, navigation, collision and security
  illustrations with a restrained charcoal/crimson palette.
- Rebuilt the 1280×640 social preview around the original logo.
- Reorganized assets into `brand/`, `banners/`, `illustrations/` and
  `screenshots/`.
- Captured actual current screenshots of the application, map viewer, map
  library and onboarding guide.
- Updated the English and Russian READMEs, website, Pages workflow and asset
  references.
- Added a detailed release note and updated architecture, decisions, research,
  setup, state, roadmap and security documents.

### Compatibility and limits

- Windows 10/11 x64.
- Portable Python 3.13 included.
- Local CS2 is optional; automatic extraction remains read-only.
- Validated against CS2 build `2000948` (2026-11-19).
- SRI is Windows x64 only; curved primitives are tessellated approximations.
- Movement remains straight-line calibrated; no combat, utility, visibility or
  demo-tick simulation.
- Full clearance validation remains limited to Dust2 and Nuke in the recorded
  batch.


## Unreleased — Internal Source 2 engine (2026-11-23)

### Processing

- Added the first-party `cs2mb-source2` component under `source2/`, linking
  ValveResourceFormat `20.1.7467` in-process for PHYS and EntityLump decoding.
- Removed runtime resolution of `S2V_CLI`, `--s2v-cli`,
  `tools/bin/Source2Viewer-CLI.exe` and `resourceinfo.exe` from
  `tools/prepare_map.py` and `app/server.py`.
- Added `tools/source2.py` with explicit-path/`CS2MB_SOURCE2` priority, argument
  arrays, timeouts and SHA-256 status.
- Preparation manifests now record input/output hashes and engine
  path/version/hash.
- PHYS output preserves Hammer units/Source axes and existing glTF/entity
  contracts; sphere/capsule primitives are tessellated with bounded ring counts.
- No movement, routing, collision-analysis or balance algorithms were changed.

### Verification

- Added wrapper, dependency-removal and synthetic malformed/truncated/oversized
  resource tests; suite is now 76 tests discovered (75 executed, 1 real-map test
  gated).
- Validated all nine active-duty maps against CS2 build `2000948`: floor
  agreement 97.34–99.54%; Dust2 historical totals reproduced exactly.
- CI now builds the engine on Windows and runs engine-backed tests.

### Presentation and docs

- Setup now installs the internal engine; Source2Viewer-CLI and resourceinfo
  instructions were removed from the normal workflow.
- Architecture, decisions, research, validation, state, roadmap, security and
  changelog documents were updated.
- README, website, logo and social-preview presentation work follows in the
  same unreleased change set.

## pre-alpha v1.0 — 2026-11-23

### Fresh repository baseline

- Created the clean `cs2mb-tool` repository baseline.
- Updated the application, UI, website, documentation and configuration version labels to `pre-alpha v1.0`.
- Updated repository links and setup commands to `Shtoblam/cs2mb-tool`.
- Added CSP and referrer response headers for the intake UI while retaining the matching meta policies.
- Added the initial security-management backlog and completed the UI response-header regression test.
- No map-analysis algorithms or application behavior were intentionally changed.

## Unreleased — Repository documentation modernization (2026-11-21)

### Documentation and repository presentation

- Reorganized the English and Russian README files around project identity,
  implementation status, limitations, quick start and documentation navigation.
- Added a central `docs/README.md` index, dedicated setup guides
  (`docs/SETUP.md`, `docs/SETUP.ru.md`) and an alpha.5 project-milestone
  release note covering the website redesign and application branding
  integration.
- Updated the contributing guide, release summary and security notes for the
  current repository layout and CI workflows.
- Reconciled stale test counts, release-version wording, GitHub Actions claims,
  CSP wording and movement-measurement provenance.
- Clarified that `v2.1.0-alpha.5` covers the website/product redesign plus a
  small logo/favicon application integration, while `VERSION` remains
  `2.1.0-alpha.4` and map-analysis algorithms are unchanged.
- Marked historical project and research documents with provenance notes instead
  of rewriting their original findings.

### Scope

- Documentation and repository presentation only.
- No application logic, server, UI, parsers, algorithms, tests, dependencies,
  workflows or runtime configuration were changed.

## Unreleased — Product website redesign (2026-11-21)

### Website
- Replaced the previous editor-shell interpretation with a modern software product website. The Hammer screenshots now inform the restrained dark technical atmosphere only; the site is not styled as a Source 2 editor.
- Applied crimson and burgundy accents sampled from the project logo to CTA surfaces, route visualizations and key details while retaining charcoal as the dominant background.
- Reorganized navigation into six page-like views: Overview, Features, Maps, Safety, Setup and FAQ. Switching views does not jump to an anchor lower on the page.
- Added an original product-preview composition with interactive map selection and Routes / Geometry modes. The preview is explicitly labelled schematic and is not a live map renderer.
- Added a clearer product introduction, workflow explanation, feature story, nine-map sample table, privacy summary, setup guide and in-app tutorial screenshot.
- Added restrained page and hover transitions with a reduced-motion fallback.

### GitHub Pages and CI
- Removed `enablement: true` from `actions/configure-pages`: creating a Pages site requires a PAT or GitHub App with administration permissions; the default `GITHUB_TOKEN` cannot create it.
- Updated the workflows to Node 24-compatible action releases.
- Expanded the Pages artifact to include both security documents and the in-app tutorial screenshot.

### Verification and limitations
- HTML tag nesting, duplicate IDs, JavaScript syntax, CSS structure, page navigation, accessibility states and local site assets were checked.
- Latest Python CI completed successfully: **55 tests passed**, module compilation passed and the repository hygiene scan passed.
- The latest Pages workflow successfully assembled, validated and uploaded the static-site artifact. Deployment is blocked only at the separate `Configure Pages` step because the Pages site is not yet enabled.
- Enable it once in **Settings → Pages → Build and deployment → Source → GitHub Actions**, then rerun the Pages workflow.
- No map-analysis algorithms, local server behavior, generated map viewers or CS2 data were changed.

This is a website presentation update, not a new application runtime release.

---

# Changelog

## 2.1.0-alpha.4 — 2026-11-20

Compact maintenance update for the local app and map viewer.

### Changed

- reorganized map intake into collapsible CS2-auto and file-upload modes;
- reduced visual density, improved spacing, responsive layout and control states;
- moved the generated viewer to a dedicated open-in-new-tab action; inline preview is now optional;
- collapsed the processing log by default and clarified that route-time figures are preliminary.

### Fixed and hardened

- updated the in-app setup guide for the public repository and current release;
- escaped the library viewer URL before inserting it into HTML;
- reject non-object and empty JSON request bodies with a controlled 400 response;
- serve generated viewers with a restrictive same-origin Content Security Policy and no-referrer policy.

### Verification

- Python compilation passed; all 53 unit tests passed; repository hygiene scan reported no obvious personal paths or secret-like values.

## 2.1.0-alpha.3 — 2026-10-20

Installation/onboarding release. Runtime map pipeline unchanged from alpha.2.

### Added

- full Windows install & launch tutorial in README (EN/RU);
- separate Source2Viewer-CLI setup section:
  - official 20.1 release link;
  - `cli-windows-x64.zip` asset;
  - all three files and `tools\bin` destination;
  - `S2V_CLI` / `config/paths.local.json` alternatives;
  - verification commands and tested SHA-256 hashes;
- rewritten in-app first-run tutorial with Python/project/CLI/launch steps;
- troubleshooting and stop/remove sections;
- refreshed tutorial screenshot.

### Changed

- intake lead and **? Установка** button now point to full setup;
- `docs/GETTING_FILES` includes CLI placement and verification.

### Verification

49 tests — OK; security scan clean; tutorial has no duplicate IDs; app/viewer
external resource requests: 0.

## 2.1.0-alpha.2 — 2026-10-20

Final alpha tester build: safety audit, visual refresh and bilingual safety
documentation. Runtime map pipeline is unchanged from alpha.1.

### Added

- VAC/CS2 safety section on the main README (EN/RU), with green-light scope;
- full anti-cheat audit in `docs/SECURITY.md` / `.ru.md`;
- Git/repository audit notes, including history limitations;
- `safety.svg` / `safety.ru.svg` and `pipeline.svg` / `pipeline.ru.svg`;
- refreshed first-run tutorial screenshot;
- app UI note: `no game process` and read-only CS2 access.

### Changed

- banners updated to alpha 2.1;
- release links/badges updated to alpha.2;
- `tools/security_scan.py` no longer contains a hard-coded personal-name
  detector; it relies on generic path/key patterns.

### Verification

49 tests — OK; security scan clean; no secret-key patterns in Git history;
current tracked tree has no game assets or personal paths; 9 maps exercised
with zero viewer console errors.

## 2.1.0-alpha.1 — 2026-10-19

### Added

- **Prepare + Generate from installed CS2**: nav/entity/collision extraction
  inside the app via `tools/prepare_map.py`;
- **time-only balance verdict** in library: balanced / CT advantage / T
  advantage, with seconds and targets;
- **Compare selected** map comparison panel;
- bilingual repository: English main README + Russian `README.ru.md`;
- English/Russian banners and extraction/security docs;
- local path config template (`config/paths.example.json`), optional
  `tools/bin/Source2Viewer-CLI.exe`;
- `tools/security_scan.py` scans tracked and untracked files;
- tests for balance and UTF-16 entity dumps.

### Fixed

- all generated maps no longer show **Dust II** as the title/map label;
- UTF-16 entity dumps from PowerShell now produce routes;
- maps without `Middle` (Nuke/Train/Vertigo/Overpass) no longer crash split;
- library id collision (`section#library` vs `div#library`);
- persisted `/viewer/<job>` links work after server restart;
- map job IDs allow alpha/beta names while rejecting traversal;
- glTF sidecar traversal and arbitrary path API access blocked.

### Changed

- app version 2.1;
- server description/topics and GitHub release assets;
- README rewritten for GitHub with banner, badges, screenshots and full
  file-acquisition guide;
- map library includes verdict and comparison controls.

### Tests

49 tests: 40 model/parser + 4 balance + 5 security.

## 2.0.0-alpha.1 — 2026-10-19

### Added

- browser upload/drop для `.nav`, entity `.txt`, physics `.gltf` и `.bin`;
- локальное Generate-приложение с job API и viewer в iframe;
- first-run onboarding/tutorial с командами извлечения ресурсов;
- all spawn→target routes с анимацией появления (Dust2 — 90, другие карты — по числу спавнов/целей);
- map library/compare: areas, edges, floor %, wall flags, clearance,
  CT→A/T→A median low;
- `summary.json` в auto-generation pipeline;
- `docs/RELEASE.md`, `docs/SECURITY.md`, `docs/SIMULATION.md`;
- placeholders/examples для пользовательских файлов;
- security scan и security-тесты;
- `--dry-run` для auto pipeline;
- manifest с SHA-256 и glTF `.bin` sidecar.

### Changed

- app UI переработан: stepper, drop zone, file chips, search/filter,
  responsive layout, copy-кнопки;
- version labels переведены на 2.0;
- path API ограничен `inputs/` и `artifacts/uploads/`;
- server default bind — `127.0.0.1`; remote bind только через `--allow-remote`.

### Fixed

- устранён возможный рекурсивный клик по drop zone;
- добавлена проверка `.gltf` sidecar `.bin` до запуска job;
- добавлен job timeout;
- закрыт path traversal/произвольное чтение через path API;
- добавлен CSRF-origin guard;
- ограничены upload size/file count/extensions;
- исправлена выдача ошибок при отсутствии `.bin`;
- исправлено копирование команд (без служебного `copy`);
- убраны персональные пути/имена из tracked-файлов.

### Security

- приложение не запускает CS2/Steam, не читает память игры и не
  взаимодействует с anti-cheat;
- внешние процессы запускаются без shell;
- uploads и outputs остаются локальными;
- нет телеметрии и API-ключей;
- `tools/security_scan.py` проверяет персональные пути и secret-like значения.

### Tests

40 model/parser tests + 5 server-security tests = **45 tests**.

Alpha batch opened nine official maps successfully: Dust2, Nuke, Train,
Vertigo, Mirage, Inferno, Ancient, Anubis, Overpass. Dust2 and Nuke were also
run with full clearance.

### Known limitations

- detection/encounter и dynamic combat не входят в 2.0;
- route cards требуют стандартные `BombsiteA/B/Middle` callouts;
- нужны уже извлечённые файлы; автоматическое VPK/VRF extraction — следующий слой;
- routes — spawn→target, без alternatives; число зависит от карты;
- AK range/`J+` — model estimates, не demo-calibrated.
