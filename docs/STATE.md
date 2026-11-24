## glTF summary correctness (Phase 2.2) — 2026-11-24

- `gltf_summary()` now keeps per-primitive material identity: each primitive
  records its index, material index/name, collision extras, mode, triangle count,
  world-space bounds and its own clip/sky classification. Node-level `clip` is
  true only when every primitive is clip/sky; mixed nodes set `mixed_clip`.
- Node transforms are composed along the scene hierarchy from TRS or explicit
  `matrix` values, with matrix column-major conversion and one application per
  node. Bounds are the transformed accessor AABB and are conservative for
  rotation and non-uniform scale; this is recorded in `bounds_mode`.
- Triangle accounting handles indexed and non-indexed primitives, defaults a
  missing mode to TRIANGLES (4), and rejects unsupported modes, invalid mesh,
  material, node-child, accessor, bufferView, buffer and POSITION references
  with controlled `ValueError` messages.
- Traversal covers only scene-reachable nodes and retains stable `node_index`
  identity for duplicate node names.
- Dust2 regression: collision bounds and 435,649 triangles are unchanged.
- Test suite: **128 discovered / 127 executed / 1 real-map test gated**.

---

## Bounds correction (Phase 2.1) — 2026-11-24

- 3DsVW bundles now store independent `bounds.collision`, `bounds.nav` and
  aggregate `bounds.scene` values. Top-level `min`/`max`/`center`/`size` remain
  aliases for scene bounds for compatibility.
- Scene bounds are the exact union of available collision and NAV bounds.
  Framing padding is applied only by the viewer, never stored in the analytical
  payload.
- Missing or empty collision/NAV representations are handled safely; a
  deterministic `[0,0,0]`–`[1,1,1]` placeholder is used only when both are
  unavailable.
- Fit, Top, Iso and the grid now use aggregate scene bounds. Legacy viewer data
  without `bounds.scene` falls back to the previous top-level bounds.
- Added synthetic tests for collision beyond NAV, NAV beyond collision,
  differing bounds, missing NAV, missing collision, aggregate center/size and
  the viewer bounds helper.
- Test suite: **120 discovered / 119 executed / 1 real-map test gated**.

---

## Engineering stabilization (Phase 1) — 2026-11-24

- Fixed SRI PHYS metadata separation: `InteractAs` is read only from
  `m_InteractAsStrings`; `PhysicsTags` is read only from
  `m_PhysicsTagStrings`. Group naming and glTF extras no longer substitute one
  field for the other.
- Made 3DsVW bundle replacement transactional. The builder writes and validates
  a sibling staging bundle, then swaps it into place; failures preserve the last
  known-good `viewer3d` directory and leave no partial bundle reported as valid.
- Made `tools/prepare_map.py --dry-run` a real preflight. It validates map,
  game paths, SRI and output planning, prints the steps, and creates no output
  directories, extracts no resources, performs no SRI conversion and starts no
  downstream generation. The application's game-mode dry-run now follows the
  same no-write behavior.
- Sanitized `auto_generate.py` analysis manifests and summaries: input paths use
  `<INPUT>/...`, outputs are bundle-relative, Python is `<PYTHON>`, sidecar URIs
  drop private/absolute components, and command metadata contains no absolute
  local paths.
- Test suite: **113 discovered / 112 executed / 1 real-map test gated**.
- SRI rebuilt locally; Dust2 PHYS summary preserves 1 part, 6 collision
  attributes and 435,649 collision triangles, with `InteractAs` and
  `PhysicsTags` as separate fields.

---

## v1.1.0 — UI redesign, 3DsVW and focused security review — 2026-11-24

- Redesigned the application shell into Overview, Process, Library, Viewer and
  Settings, with compact rectangular panels, a cyan/blue accent and local SVG
  icons. Existing intake, upload, polling, library and comparison behaviour is
  preserved.
- Added a short five-step onboarding guide, Help access, and working local
  settings for default viewer mode, 3D quality and default 3DsVW layers.
- Added **3DsVW — 3D Source Map Viewer**: a WebGL2 viewer using locally bundled
  three.js `0.160.0`, with collision, floor, wall, clip, NAV, entity, place and
  route layers; fit/top/iso/reset camera actions; selection metadata; embedded
  and separate-tab modes.
- 3DsVW visualizes SRI PHYS collision geometry plus NAV/entities/routes. It does
  not claim render-world geometry, materials or textures.
- Added `viewer3d/` data builder, vendored viewer assets and confined server
  routes. Generated bundles are normalized and bounded before serving.
- Added 3DsVW endpoint security tests, builder tests and real de_dust2/de_anubis
  integration checks.
- Added English and Russian user guides and updated README, website, screenshots,
  social preview and dependency notices.
- Local 3DsVW measurements: de_dust2 435,649 collision triangles / 2,242 NAV
  areas / 164 draw calls; de_anubis 715,842 triangles / 2,633 areas / 141 draw
  calls in Edge. These are local observations, not universal benchmarks.
- Test suite: **100 discovered / 99 executed / 1 real-map test gated**.
- Release target: `v1.1.0`, normal release, Windows x64.

---

## Historical: SRI, security audit and v1.0.0-pre.1 — 2026-11-23

- Renamed the internal Source 2 component to **SRI — Source Resource Inspector**:
  `cs2mb-sri.exe`, `tools/sri.py`, `CS2MB_SRI`, `--sri`, `sri_ready`,
  `sri_version`, `sri_sha256`, source under `sri/`.
- SRI functionality is unchanged: PHYS, EntityLump, mesh/hull handling,
  bounded sphere/capsule tessellation, coordinate contract, glTF + `.bin` and
  entity text output.
- Closed the P1 security backlog: two-job limit, controlled `429` rejection,
  stale job/upload cleanup, Windows process-tree timeout and direct endpoint
  tests. Added loopback Host allow-listing, required same-origin POSTs, disabled
  `--allow-remote`, cleaned rejected uploads and redacted personal paths from
  preparation manifests.
- Added `v1.0.0-pre.1` versioning across the application, website, docs,
  package metadata and release links.
- Restored the owner's original `logo.png` byte-for-byte
  (`03f11c8167907d4b243c1e2ff64953ea33848257eae51e09dcbed4a2f4876e06`).
  Removed invented vector logo variants. Rebuilt the banners, pipeline, SRI,
  navigation, collision and security SVGs with a restrained palette. Used the
  original logo in the application, website, README, favicon and social preview.
- Captured actual current screenshots after the SRI/security changes:
  `cs2mb-main.png`, `cs2mb-map-viewer.png`, `cs2mb-map-library.png`,
  `cs2mb-setup.png`; the published website screenshot is
  `website-current.png`.
- Added a complete Windows package builder with portable Python 3.13, SRI,
  launchers, docs, `SHA256SUMS.txt` and SPDX SBOM.
- Test suite: **88 tests discovered / 87 executed / 1 real-map test gated**.
  Local engine-backed tests, endpoint security tests and process-tree tests pass.
- Current application version: `v1.0.0-pre.1`. The complete release is
  published at <https://github.com/Shtoblam/cs2mb-tool/releases/tag/v1.0.0-pre.1>.
  The old standalone `source2-v1.0.0` release and tag were removed after the
  complete package was published and verified.
- Complete package: `CS2MB-v1.0.0-pre.1-win-x64.zip`, with a release
  `SHA256SUMS.txt`. Clean extraction, 142 checksums, launcher, SRI detection,
  automatic Dust2 preparation and upload-mode generation were verified locally.
- Release: `v1.0.0-pre.1`, published as a pre-release with package, checksums
  and SPDX SBOM.

---

## Historical: internal cs2mb-source2 engine — 2026-11-23

- Added the first-party `cs2mb-source2` component under `sri/`. It links
  ValveResourceFormat `20.1.7467` in-process for binary KV3, Zstandard/LZ4,
  PHYS and EntityLump decoding and exposes `phys`, `entities`, `inspect` and
  `phys-summary` commands. It is not a renamed or wrapped Source2Viewer-CLI.
- `tools/prepare_map.py` now extracts the three map resources and calls the
  internal engine. Runtime resolution of `S2V_CLI`, `--s2v-cli`,
  `tools/bin/Source2Viewer-CLI.exe` and `resourceinfo.exe` was removed.
  `app/server.py` reports `source2_ready`/`source2_version` and requires the
  packaged engine instead of an external CLI.
- Added `tools/source2.py` with explicit-path/`CS2MB_SOURCE2` priority, argument
  arrays, timeouts and SHA-256 status. A stale override fails loudly.
- The preparation manifest now records input/output hashes plus engine path,
  version and SHA-256.
- Collision output keeps Hammer units/Source axes and omits the legacy node
  matrix. Existing `gltf_collision.py`, routing, movement, simulation and
  balance code was not changed.
- Entity output keeps the existing line-oriented text contract and all entity
  properties/connections.
- Sphere and capsule primitives are tessellated with bounded ring counts so all
  nine active-duty maps process; mesh and convex-hull geometry stays exact.
- Current local validation: CS2 build `2000948` (2026-11-19), nine maps,
  97.34–99.54% floor agreement, Dust2 historical totals reproduced exactly
  (39 primitives, 1,306,947 exported vertices, 435,649 triangles). Entity counts
  and class distributions match the local `resourceinfo` dump for all nine maps.
- Current suite: **76 tests discovered / 75 executed / 1 skipped** (real-map
  test gated by `CS2MB_TEST_GAME` when run without a game); Python compilation
  and security scan pass. CI builds the engine and runs engine-backed tests on
  Windows.
- Current engine artifact: self-contained Windows x64, about 17.7 MB. Release
  `source2-v1.0.0` publishes `cs2mb-source2-win-x64.zip` (7,611,911 bytes) and
  `SHA256SUMS.txt`. Executable SHA-256
  `47ce196dc61e64128e2588c664ea37303592ca21ec9c324f067a0cab85edf28c`;
  archive SHA-256
  `10cd89467d259059d1bd42b1726e9c73b0d058ce069c627a401730d071a403df`.
  The application version remains `pre-alpha v1.0`; this is a component asset.
- Presentation: vector logo family, compact mark, favicon, 1280×640 social
  preview, original engine/navigation/collision/local illustrations, redesigned
  bilingual READMEs and website, and a refreshed real app screenshot.
- Remaining work: upload the social preview in GitHub repository settings
  (no public API for that field) and revalidate after a future CS2 or
  ValveResourceFormat format change.

---

## pre-alpha v1.0 repository baseline — 2026-11-23

- Fresh `cs2mb-tool` repository baseline created from the sanitized project tree.
- Application version is `pre-alpha v1.0`; historical 2.x release notes remain archived under `docs/releases/`.
- Added response-header CSP/referrer hardening for the intake UI while keeping the existing meta policy.
- Started the security-management backlog in `docs/SECURITY_BACKLOG.md`; endpoint/process/concurrency work is prioritized there.
- Current suite: **56 unit tests**; Python compilation, security scan, Markdown validation and asset checks pass.
- Repository links, setup commands and website labels now target `Shtoblam/cs2mb-tool`.
- No map-analysis algorithm, movement model, collision calculation or simulation behavior was changed.

---

## Repository documentation modernization — 2026-11-21

- Documentation-only maintenance pass: README and Russian README reorganized around project identity, current capabilities, implementation status, limitations, quick start and documentation navigation.
- Added a central [documentation index](README.md), a dedicated [setup and troubleshooting guide](SETUP.md) plus [Russian counterpart](SETUP.ru.md), and an [alpha.5 milestone note](releases/v2.1.0-alpha.5.md).
- Reconciled stale statements with the current tree: current suite is **55 unit tests**; CI workflows are tracked and documented; viewer CSP and intake-UI meta CSP are now described separately; the alpha.4 application release is distinguished from the alpha.5 branding/website milestone. The alpha.5 release range includes the logo/favicon application integration and a `/logo.png` route; it changes no map-analysis algorithms. `VERSION` remains `2.1.0-alpha.4`.
- Verified links and Markdown structure after editing. No application code, HTTP server, UI, parser, algorithm, test, dependency, workflow or runtime configuration was changed.
- Current environment observation: the installed CS2 `appmanifest` reports build `26798866`; historical measurements reference build `25966348`. The current `de_dust2.nav` SHA-256 still matches the recorded value, but no general revalidation of other map resources was performed.

---

## Website direction correction — product-site redesign — 2026-11-21

- The previous Source 2 editor-shell interpretation was not the requested direction. The two Hammer screenshots are references for the dark technical atmosphere and information hierarchy only, not a request to reproduce Hammer's application UI.
- The website is now a modern software product site: a clear product hero, product demonstration, feature storytelling, map dataset, privacy/safety explanation, setup instructions and FAQ. Navigation switches six page-like views rather than jumping down a long page.
- Visual system: charcoal / engine-grey foundation with fine neutral borders; crimson-to-burgundy details sampled from `logo.png` are used as accents for brand moments, routes and calls to action, not as the dominant background.
- Product preview: original schematic map-analysis demo with actual sample values from the nine-map table; Dust2, Mirage and Nuke selection and Routes / Geometry mode controls. It is explicitly labelled illustrative and must not be described as a live renderer.
- Motion is restrained and honours `prefers-reduced-motion`.
- Pages workflow no longer tries to create an unconfigured Pages site using `GITHUB_TOKEN`. The repository owner must first set **Settings → Pages → Build and deployment → Source → GitHub Actions**; without this one-time setting, the deployment job's `configure-pages` step returns 404. The separate build job still assembles, validates and uploads the static-site artifact successfully.
- CI actions updated for Node 24 compatibility. Pages artifact includes the English/Russian security docs, both website banners, logo and in-app tutorial screenshot.
- Website commits: `610f067` (product website redesign), `6c12b3f` (navigation polish and Actions upgrades), `70d56b1` (crimson/burgundy repository banners), `1bafd1b` (Pages build/deploy separation and published-file validation).
- No map algorithms, route estimates, collision checks, app server endpoints, generated viewer behavior or CS2 data were changed.

---

## Website redesign — Hammer-inspired workspace — 2026-11-21

- Rebuilt the GitHub Pages website into a dense Source 2 Hammer-inspired editor workspace rather than a long-form landing page. This is a website/front-end presentation change; it does not claim to be Valve's Hammer code and does not add map-editing operations.
- Desktop composition now follows the supplied references: native-style title bar and menu, compact ribbon toolbar, document tabs, vertical tool rail, left Tool Properties, central viewport, lower asset browser, right Outliner / project-history / Selection Sets / Object Properties, and a bottom status bar.
- The central preview now includes an original inline SVG map-scene illustration. View controls switch Perspective / Top / Wireframe and independently toggle grid, route and label layers. This is a front-end illustration of the analysis domain, not an actual generated CS2 map viewer.
- Navigation is available through document tabs, ribbon buttons, the left tool panel and the right project tree. Switching sections replaces the active view without scrolling the whole page.
- Added a searchable command palette (Ctrl+K), Ctrl+1…6 section shortcuts, arrow-key navigation across tab strips, a filter for the project tree, resizable left/right panels, collapsible side panels and bottom asset dock, plus a wide-view layout preset.
- Added bottom browser tabs for project assets, tested map data, route examples, documentation and project summary. Added right-side Outliner / History tabs; the History view is explicitly a project milestone summary, not a functional undo stack.
- Language selection and active section/dock/view/panel settings are saved locally where browser storage is available. Responsive fallbacks retain page navigation on narrow screens.
- Preserved the existing project descriptions, preliminary-result warnings, nine-map test table, install guidance, safety information, FAQ, RU/EN translations and local documentation links. No map-analysis algorithms, app server, generated viewer or CS2 data were changed.
- Verification performed on the committed source: HTML tag nesting balanced; JavaScript syntax parsed successfully; CSS brace balance passed; all six page panels and their navigation bindings present; viewport, layer, panel, dock, right-inspector and command-palette controls present; all checked text links and SVG assets resolve in the repository.
- Live GitHub Pages rendering could not be checked from this environment because the Pages URL was inaccessible through the available browser/DNS route. A visual browser check after deployment remains outstanding.
- Website commits: `280e68b` (workspace rebuild), `cf1e805` (workspace control polish), `51eb15f` (inspector tabs), `67a9086` (HTML structure fix). This is not a new app release; app version remains `2.1.0-alpha.4`.

---

## Website UI maintenance — 2026-11-21

- The GitHub Pages landing site was redesigned as a Hammer-inspired desktop workspace shell.
- The former long anchor-navigation page is now organized into six independently switched views: Overview, Features, Maps, Safety, Setup and FAQ. Navigation is available through the document tab strip, left workspace panel and compact icon rail; switching views does not scroll the whole document.
- The workspace includes a title bar, application menu, command strip, central scrollable viewport, project inspector and status bar. Styling uses compact dark-grey editor panels, thin borders and restrained amber selection accents based on the supplied Hammer references.
- Existing project copy, map sample values, alpha-scope warnings, documentation/download destinations and Russian/English translations were preserved in the page content.
- `site.js` now switches the active view, synchronizes selected/ARIA states, supports left/right keyboard navigation in the tab strip, and remembers the selected view and language in local storage.
- Commit: `02115f54ffc601b3d91cc5f11c008cd36f32a24e` (`Redesign project website as Hammer-inspired workspace`).
- Post-push static verification confirmed all six page panels, navigation bindings, language switch and balanced CSS braces. The published GitHub Pages URL could not be rendered from this environment because DNS resolution failed; live visual verification remains outstanding.

---

# STATE — текущее состояние проекта

## Maintenance update — 2026-11-20

- App version: `2.1.0-alpha.4`.
- The local intake UI now separates automatic CS2 preparation and file upload into collapsible panels; advanced paths remain secondary.
- The generated map viewer opens in a dedicated tab/window by default. Inline preview is opt-in and lazy-loaded.
- Processing logs are collapsed by default; the route-time limitation is visible in the app.
- Viewer responses now carry a restrictive same-origin CSP; malformed/non-object JSON API bodies are rejected with a controlled `400` response.
- A focused maintenance review and automated checks are recorded in the alpha.4 release notes. Route, movement, collision and balance algorithms were not changed.

**Дата:** 2026-10-20 (исторический срез; актуальные записи — в начале файла)
**Активный этап:** Release 2.1.0-alpha.4 local; Release 2.2 (LOS/detection)
запланирован следующим. Динамический combat/strength — позже.
**Полноценная реализация:** карта/маршруты/сравнение — есть; combat — нет.

## 1. Фактическое окружение

- Проект: `<PROJECT_ROOT>`
- Игра: `<CS2_GAME>`
- CS2 (исторические измерения): ClientVersion `2000933`, buildid `25966348`,
  patch `1.41.9.1`.
- CS2 (наблюдение при maintenance-проверке 2026-11-21): appmanifest buildid
  `26798866`. Совпадение `de_dust2.nav` SHA-256 проверено; остальные ресурсы
  карт не перепроверялись.
- Python: 3.13.3
- Git: 2.55.0
- Источник истины: установленная CS2, только чтение.

## 2. Что подтверждено

### Данные

- `game/csgo/maps/de_dust2.vpk` — self-contained VPK, 632 записи.
- `maps/de_dust2.nav` — v36, 2242 areas, 6275 edges, 0 ladders.
- `default_ents.vents_c` — 15 T + 15 CT spawns, 43 callouts, 2 bombsite,
  2 buyzone.
- `world_physics.vmdl_c` — PHYS block, 21 843 224 байта (PHYS 21 840 687).
- VRF collision export — 39 primitives, 435 649 triangles; после фильтра
  sky/grenadeclip — 433 063.
- `scripts/weapons.vdata_c` — `m_flMaxSpeed` оружия.
- `cfg/gamemode_competitive.cfg` — freeze 15, round 1.92 min,
  `mp_randomspawn 0`.

### Проверки

- Все 28 nav-файлов из map VPK прочитаны; `bytes_consumed == file_size`.
- Все 15 T и 15 CT spawn origins лежат внутри nav-полигонов в XY.
- Edge semantics: `edge_id` относится к destination area (медиана reciprocal
  midpoint 0).
- Dust2: 12 SCC, largest 2186, 175 one-way, 14 CrouchHeight, 1 zero-area.
- z-aware spawn check: 128 spawns (Dust2 30, Nuke 40, Vertigo 30, Train 28),
  all mapped, 0 ambiguous; 7 Dust2 CT и 2 Nuke CT имеют 2 bands.
- Wall test: 6091 connections, 2 blocked (0.033%), both same playerclip
  passage `1241 <-> 1246`; требует ручной проверки.
- Clearance point-sample: 8812 area samples, 21 low ceiling, 1 narrow;
  6275 connections, 14 low ceiling, 0 narrow; median gap 199.87.
- Swept-capsule probe: 6091 connections, 516 wall flags (384 intersections,
  132 near), 55 low ceilings, 614 floor mismatches; heuristic, не pass/fail.
- Floor anomaly review: 1351/1352 — CrouchHeight без floor на -26; 1354 —
  частично; 613 — tiny 18 u²; 1104/1727/1778 — slope/nav-plane.
- Route vertical profile: CT→A median имеет 6 vertical transitions,
  +272/-49 units, 4 jump-up candidates, `J+3.0 s` (high+budget ≈13.0);
  `AK 6.5–10.0 s` не включает box jumps; UI badges `↑6`/`J+3.0`.
- 5-man rush envelope: `simulation/scenario.py` перебирает `C(15,5)=3003`
  наборов спавнов; CT→A median 6.5 s (P10 6.0, P90 6.6), T→A median 23.1 s
  (P10 22.6, P90 24.1). Это time-only, не split/combat.
- 5v5 split: quotas 2 A / 2 B / 1 Mid, 30 назначений на команду,
  optimal/random/softmax policies. CT→A low med: opt 6.0, rand 6.3,
  soft 6.3; T→A: 22.7 / 23.3 / 23.1. Softmax τ=5 s — proxy, не human.
- Jump budget: CT→A 4 up-candidates, `J+3.0 s`; `high + budget ≈13.0 s`;
  T B `J+1.5`, CT B `J+0.8`. Это budget, не измеренное время.
- Release 2.1.0-alpha.3 (local, historical): auto extraction from installed CS2,
  time-only verdict и compare; scope в `docs/RELEASE.md`, security в
  `docs/SECURITY.md`.
- VAC/CS2 audit (2026-10-20): no game process, memory access, injection or
  network; green light for local alpha testing; `docs/SECURITY.md`.
- Git audit: current tracked tree clean, no keys/tokens/game assets; old
  commit objects still contain historical path examples; no history rewrite.
  `config/paths.local.json` and `tools/bin/*.exe` ignored.
- Auto-generation CLI: `tools/auto_generate.py` прогнан на Dust2 (4 команды,
  152 s), выдал viewer + floor/connection/clearance JSON + summary +
  manifest с размерами/SHA-256 и glTF `.bin` sidecar; `--dry-run` проверен.
- Browser upload/drop: small dry-run + ~48 MB real upload проверены; job
  skip_clearance 19.3 s; viewer в iframe; library summary:
  areas/edges/floor/wall/clearance/CT→A/T→A low.
- Alpha multi-map batch: Dust2, Nuke, Train, Vertigo, Mirage, Inferno,
  Ancient, Anubis, Overpass; все viewers открыты без console errors.
  Full clearance: Dust2 + Nuke; остальные — skip clearance.
- Nuke full: floor 99.27%, wall 0/7334, low 18, narrow 0,
  connection low 11 / narrow 1.
- Auto extraction from installed CS2: `tools/prepare_map.py` → nav/entities/
  collision → viewer; Mirage test 16.1 s. Map title/map-name fixed (no Dust II).
- Balance verdict: all tested maps CT-favored by time-only route metric
  (+5.2…+14.0 s); library shows verdict and Compare selected.
- 3 вертикальные аномалии: `215->244` (+87), `1032->1015` (+88),
  `834->748` (−181, non-reciprocal).
- Weapon max speeds: knife 250, AK 215, M4A1 225, AWP 200/100, SSG08 230.
- Movement convars: accel 5.5, friction 5.2, stopspeed 80, maxspeed 320,
  air accel 12, gravity 800, jump impulse 301.993, ladder scale 0.78.
- Measured steady state: AK 215, knife 250, AWP 200, AK walk 111.8,
  AK crouch 73.1.
- `7-Zip 23.01` не открывает Source 2 VPK — проверено.

### Эксперимент Dust2

Расстояния (Hammer units, не время), spawn → area centroid:

| Сторона | Цель | min | median | max |
|---|---|---:|---:|---:|
| T | Mid | 2140.3 | 2402.3 | 2818.4 |
| T | A | 4673.8 | 4935.8 | 5351.9 |
| T | B | 3841.8 | 4184.9 | 4674.2 |
| CT | Mid | 1769.3 | 2009.6 | 2208.8 |
| CT | A | 1126.1 | 1362.1 | 1460.5 |
| CT | B | 2189.9 | 2430.2 | 2629.3 |

Подробности: `docs/MAP_DATA.md`.

## 3. Что работает

- `tools/vpk_read.py` — list/extract VPK v1/v2, CRC32, chunks.
- `tools/nav_inspect.py` — nav v30–36, areas, connections, ladders,
  generation params, diagnostics, line-graph routes, SVG.
- `tools/nav_experiment.py` — entity dump → spawns/callouts → nav → distance
  matrix + SVG.
- `tools/nav_census.py` — все map VPK → nav census.
- `tools/phys_dump_inspect.py` — PHYS text dump → hull bounds/attributes.
- `prototype/dust2_viewer.py` — self-contained HTML/SVG UI для Dust2.
- `tools/gltf_collision.py` — VRF physics glTF loader + 2D triangle index.
- `tools/collision_floor_test.py` — nav floor vs collision floor test.
- `tools/gltf_collision_probe.py` — axis-convention probe.
- `tools/collision_connection_check.py` — wall test на nav-переходах.
- `tools/collision_clearance_check.py` — point-sample capsule clearance.
- `tools/collision_sweep_check.py` — swept-capsule probe по nav-переходам.
- `movement/source.py` — calibrated straight-line movement model.
- `movement/route.py` — route vertical/turn profile; no jump-time invention.
- `simulation/scenario.py` — 5-man rush и split policies.
- `tools/auto_generate.py` — user-files → checks → viewer → summary/manifest.
- `tools/prepare_map.py` — installed CS2 → nav/entities/collision.
- `tools/security_scan.py` — personal-path/secret-like scan.
- `simulation/balance.py` — time-only verdict.
- `app/server.py` — local Generate app; `app/index.html` — UI.
- `config/movement_profile.json` — measured movement profile.
- `tests/` — 56 unit tests passing on current `main`; the suite covers
  model/parser, movement/route, rush/split, balance, app UI contract and selected
  server-security helpers. See the current maintenance entry at the top of this
  file for the verification command and result.

### UI prototype

- Выход: `artifacts/dust2_viewer.html` (1 468 614 bytes, ignored).
- Auto-pipeline output: `artifacts/auto_test/` (viewer, reports, manifest;
  ignored), проверен end-to-end.
- `app/server.py` проверен end-to-end: `/` UI, `/api/upload`, `/api/discover`,
  `/api/library`; реальный job со `skip_clearance` — 19.3 s, viewer
  в iframe (90 all-routes), manifest; dry-run также проверен.
- App UI переработан: onboarding/tutorial с командами извлечения файлов,
  drop zone, file chips/remove, stepper, library search/filter, copy-кнопки;
  `app/index.html` 43 890 bytes.
- 2242 nav polygons, 6 representative routes, 90 spawn→target routes,
  30 spawns, 7 targets.
- 29 470 белых collision-сегментов стен; слой `Стены` включается/выключается.
- `Все маршруты` — 90 polyline с последовательной анимацией появления.
- Переключатели routes/layers, zoom/pan, hover по nav area.
- Diagnostics: `Stacked XY samples: 7/561 (max 2 bands)`.
- Collision floor check: 98.77% ≤16 u, median |Δz| 3.78, P95 9.61,
  missing 0.
- Route cards показывают `AK a–b s`: нижняя — непрерывный ground run,
  верхняя — stop at every nav crossing. T Mid 11.3–16.7, T A 23.1–34.2,
  T B 19.6–29.7, CT Mid 9.5–15.0, CT A 6.5–10.0, CT B 11.5–17.5.
  Прыжки/повороты/двери не учтены.
- Route cards показывают badges `↑N` и `J+...`; CT→A имеет `↑6`, `J+3.0`,
  `+272/-49`; J — отдельный jump budget (0.755 s × up-candidates), не входит
  в AK range.
- Details table: median distance + median AK range по всем 15 спавнам стороны;
  вторая таблица — 5-man rush envelope; третья — 5v5 split policy comparison
  (optimal/random/softmax). Это time-only, не human/combat.
- UI переработан в Source 2-style shell: topbar, quick start, route cards,
  validation card, details; wall flags 2/6091 и low/narrow clearance
  отображаются.
- Белые линии стен строятся из base-edge near-vertical collision-треугольников;
  clip/sky исключены. 29 470 сегментов при `min_length=12`.
- Проверено в браузере: DOM counts, toggles (включая `Стены`), zoom/fit,
  details, отсутствие console warnings.
- Скриншот проверен визуально: карта Dust2, маршруты T/CT → Mid/A/B,
  белые collision-стены, route badges `↑N`, sidebar с
  distances/diagnostics/collision check.

## 4. Что не сделано / не проверено

- Source2Viewer CLI 20.1 скачан в temp, не установлен system-wide.
- Collision floor test выполнен: 98.77% ≤16 u; 6 проблемных areas разобраны;
  остаются 108 samples >16, из них часть — slope/nav-plane.
- Wall test, point-sample clearance и swept-capsule probe реализованы;
  LOS — нет. 516 sweep flags — кандидаты на triage, не доказанные ошибки.
- PHYS text dump: 166 МБ, 10 143 hull records; bounds/attributes извлечены;
  полные треугольники уже получены через VRF glTF.
- Модель движения реализована для прямой (`movement/source.py`); в маршруты
  интегрирован диапазон `AK a–b s`, но прыжки/повороты/лестницы не входят.
- Измерения движения — одиночные прогоны, нужна повторная серия по demo ticks.
- Полного 5v5 combat нет; есть time-only 5-man rush и optimal split
  envelope.
- Нет независимого сравнения с Awpy/VRF на всех картах.
- Нет проверки `world_physics` на static props/dynamic doors.
- Нет 3D-визуализации; есть 2.5D/z-aware слой. 3D отложена.
- UI пока статический HTML; сервер/десктопная оболочка не нужны для MVP.

## 5. Git

- Локальный репозиторий: `main`.
- Ключевые коммиты:
  - `3524b01` — исследование и документация;
  - `df51a26` — `AGENTS.md` + `docs/STATE.md`;
  - `b438dc6` — Dust2 UI-прототип, synthetic tests, PHYS hull inspection;
  - `de58337` — collision floor test + z-aware multi-level поддержка;
  - `140918a` — измерение движения и movement model;
  - `a5e53c9` — wall test + Source 2-style UI;
  - `cf2aa65` — point-sample capsule clearance;
  - `8a5e778` — белый слой стен + roadmap ручных спавнов;
  - `bece3d4` — swept-capsule probe + floor anomaly review;
  - `ff842c6` — route vertical profile + CT→A box-jump badge;
  - `ffaa352` — AK time range + 5-man rush envelope;
  - `60c8a54` — 5v5 split envelope с optimal assignment;
  - `7f365ab` — split policies, jump budget и auto pipeline;
  - `0be0a5f` — Generate-приложение и 90 анимированных маршрутов;
  - `7414917` — V1 hardening: upload validation, library routes, release docs;
  - `635ed3e` — UI overhaul + onboarding tutorial;
  - `ef30bba` — Release 2.0: security hardening, docs и examples;
  - `1818efa` — Release 2.0.0-alpha.1 + multi-map docs;
  - `3d314d4` — README linked to GitHub alpha release;
  - `4200e96` — Release 2.1 alpha: auto extraction, verdict, compare,
    bilingual docs;
  - `41199c3` — VAC/CS2 safety audit, visual refresh, alpha.2 docs;
  - `c6162d2` — full install and Source2Viewer-CLI onboarding (alpha.3).
- Текущая история: `git log`; state-only коммиты не перечисляются.
- `origin`: `https://github.com/Shtoblam/cs2mb-tool.git`.
- `main` отслеживает `origin/main`; последние коммиты отправлены успешно.
- Секреты/токены не использовались и не сохранялись.
- Рабочее дерево должно быть чистым после финального обновления STATE.

## 6. Активная задача

1. [done] Collision loader, floor test, z-aware nav lookup, UI collision
   panel и документация закоммичены и отправлены.
2. [done] Movement convars и steady-state скорости измерены; модель
   `movement/source.py` и профиль добавлены.
3. [done] Wall test: 6091 connections, 2 playerclip flags.
4. [done] Capsule clearance point-sample: 21 low ceiling, 1 narrow area;
   14 low-ceiling connections.
5. [done] UI переработан в Source 2-style shell с quick start,
   route cards и validation card.
6. [done] Разобрать 6 проблемных nav areas (`1351`, `1352`, `613`, `1104`,
   `1727`, `1778`); swept-capsule probe выполнен.
7. [next] Добавить LOS и triage 516 sweep flags; движение по маршруту.
8. [partial] Интегрировать movement model в маршруты: `AK a–b s`, vertical
   profile, badges `↑N`; jump budget `J+...` добавлен, но turn/landing
   калибровка ещё не сделана.
9. [done] 5-man rush envelope: exact C(15,5), UI table.
10. [done] 5v5 split: 2 A / 2 B / 1 Mid, 30 assignments,
    optimal/random/softmax policies; UI comparison table.
11. [done] Auto-generation CLI: user inputs → checks → viewer → manifest.
12. [done] Release 2.1 app: auto extraction from installed CS2,
    upload/drop fallback, verdict, compare selected, bilingual docs.
13. [next] Release 2.2: detection/encounter times; затем Release 2.3 combat.
14. [done] Release 2.1 hardening: auto extraction, balance verdict,
    compare selected, bilingual docs, security docs/tests.
15. [research] Release 3.0: свои Entity/PHYS-парсеры вместо внешних
    Source2Viewer/resourceinfo; format census + golden tests, не блокирует
    2.2/2.3.

## 7. Следующий конкретный шаг

1. Повторить movement-замеры по demo ticks (не одиночные `cl_showpos`).
2. Добавить LOS и triage 516 sweep flags (особенно non-clip props и
   low ceilings); point-sample и swept probe уже есть.
3. Интегрировать `J+` jump budget в split-сценарии и откалибровать
   jump/landing по демкам; сейчас `AK a–b s` не включает прыжки.
4. Калибровать random/softmax policy по демкам; затем turn/combat.
5. Release 2.2: detection/encounter times (LOS, encounter windows); затем
   Release 2.3 combat.
6. Release 3.0 research: internal Entity/PHYS parser, format census и
   golden-сравнение с текущими resourceinfo/Source2Viewer; только потом
   opt-in замена.
7. 3D — позже; текущий 2.5D слой достаточен.

## 8. Блокеры

- Manual spawn override: backlog, низкий приоритет; добавить после
  стабилизации nav/entities/UI.
- Movement: базовые параметры измерены; jump budget `J+` есть, но landing/
  turn time не откалиброваны; нужна повторная серия по demo ticks.
- 3D-визуализация: отложена по приоритету; текущий 2.5D слой работает.
- Полная проверка collision: остаются LOS, triage 516 sweep flags и
  разбор narrow area 1246; floor anomalies классифицированы.
- 5v5 split time-only с optimal/random/softmax есть; калибровка policy по
  демкам, blocking и combat не начаты.
- Auto-generation: upload/drop, Generate, 90 routes, animation и map library
  есть; detection/encounter и combat не начаты.
- GitHub push: работает; локальная ветка отслеживает `origin/main`.
- Git history содержит старые примеры персональных путей; текущее дерево
  clean. Очистка истории требует отдельного согласованного rewrite.
