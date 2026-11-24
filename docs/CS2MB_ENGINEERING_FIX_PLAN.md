# CS2MB Engineering Remediation Plan

**Target repository:** `Shtoblam/cs2mb-tool`  
**Primary audit:** `docs/ENGINEERING_REVIEW_updated.md`  
**Operating rules:** `AGENTS.md`  
**Execution mode:** staged, evidence-driven, cost-conscious; no repository-wide rewrite.

## 1. Objective

Stabilize the existing CS2MB v1.1.0 pipeline first, then make 3DsVW and SRI ready for a faithful, scalable Render Geometry pipeline. Preserve the existing working behavior and analytical results unless a specific change is justified and regression-tested.

The engineering review is a findings-and-direction document, **not** an implementation schedule. Its observations must be rechecked against the current working tree before they are treated as active defects. Separate confirmed bugs from scale-up risks and unverified hypotheses.

## 2. Mandatory constraints

1. Read `AGENTS.md`, the current `docs/STATE.md` entry, and the relevant sections of `docs/ENGINEERING_REVIEW_updated.md` before editing.
2. Inspect `git status`, recent history, and the current diff. Preserve all user changes; never assume the working tree is clean.
3. Keep changes small and independently testable. Do not perform a broad rewrite or introduce new dependencies for convenience.
4. Keep the current Three.js/WebGL2 viewer foundation. Evolve the existing 3DsVW incrementally; do not replace it with an unrelated viewer.
5. Keep Render Geometry, Collision Geometry, NAV, Entity Data, and derived analysis as distinct representations. They share a documented world coordinate convention, but their actual geometry is not expected to match.
6. **Never fit Render to Collision or Collision to Render.** No ICP, mesh snapping, vertex welding across layers, automatic floor correction, or destructive geometry alignment. Preserve raw source-derived data; any future comparison/correction must be a separate derived artifact.
7. NAV remains the primary high-level routing graph. Collision supports obstruction/clearance checks; it does not replace NAV routing with generic triangle-mesh pathfinding.
8. Use Dust2 (`de_dust2`) as the first target for new extraction work. Validate multi-level maps such as Nuke, Vertigo, and Train before claiming general support.
9. Read the installed CS2 data only. Never write into the game installation, launch or inspect the game process, interact with matches, or commit proprietary game assets/extracted data.
10. Do not upgrade the pinned ValveResourceFormat (VRF) version without a demonstrated API/format need and regression evidence.
11. Do not commit, push, publish, or change remotes. The user has not authorized those actions in this task.
12. All code, comments, documentation, commit-message drafts, and agent reports/final responses must be in English. Preserve existing product localization.

## 3. Phase 0 — Preflight and evidence check

Before implementation:

- Confirm the current `HEAD` and working-tree state.
- Run the existing baseline test suite and security scan; record the actual result. The repository instructions currently document:
  - `python -m unittest discover -s tests -v`
  - `python tools/security_scan.py`
- Inspect the exact current implementations and callers for each selected finding. Relevant files include:
  - `sri/Cs2mb.Sri/Program.cs`
  - `tools/prepare_map.py`
  - `tools/auto_generate.py`
  - `viewer3d/build.py`
  - `viewer3d/assets/viewer.js`
  - `tools/nav_inspect.py`
  - relevant files under `tests/`
- Create a compact evidence table with: finding, status (`confirmed`, `already fixed`, `not reproduced`, `risk`, or `hypothesis`), affected code, regression risk, proposed test.
- Do not spend time rereading the entire repository or repeating identical searches. Read only the relevant functions and call sites.

If the baseline suite already fails, distinguish pre-existing failures from regressions. Do not silently repair unrelated failures as part of this work.

## 4. Phase 1 — Stabilize correctness and output safety

**This is the only implementation wave to execute in the current low-budget run.** Work through the four tasks below one at a time. Keep each diff focused, run its focused tests, then proceed. If a task turns out to require a larger redesign, stop and report the blocker instead of expanding scope.

### 1.1 Fix PHYS collision metadata field conflation

**Location:** `sri/Cs2mb.Sri/Program.cs`, `SummarizePhys()`.

The current `InteractAs` extraction can fall back from `m_InteractAsStrings` to `m_PhysicsTagStrings`. These are different Source 2 concepts and must never be substituted for one another.

Required change:

- Read `m_InteractAsStrings` only for `InteractAs`.
- Read `m_PhysicsTagStrings` only for `PhysicsTags`.
- Represent a missing/unavailable property as an empty or missing value, not as another metadata field.
- Keep collision group and surface-property handling unchanged.

Acceptance tests:

- A fixture with both fields populated returns each field independently.
- A fixture with only physics tags does not populate `InteractAs`.
- A missing field is handled safely without failing the whole PHYS summary.
- Existing PHYS summary/output compatibility is preserved apart from correcting the mislabeled value.

### 1.2 Make 3DsVW output replacement transactional

**Location:** `viewer3d/build.py`, `build_viewer3d()`.

The current builder removes an existing `viewer3d` directory before the replacement has been completely written and validated. A later failure can destroy the last known-good viewer.

Required change:

- Build into a fresh temporary staging directory located under the same parent/filesystem as the final target.
- Write all expected files there and validate that the manifest/payload, glTF, binary sidecar, and internal references are complete and consistent.
- Only after successful validation, replace the old target with the staged bundle.
- Preserve the old valid output if writing, copying, or validation fails. Implement rollback for replacement failures, including Windows filesystem semantics.
- Clean temporary/backup directories safely. Never delete the only valid output as part of error handling.

Acceptance tests:

- Successful build replaces the target and leaves a complete bundle.
- Forced failure before replacement leaves the prior target byte-for-byte intact.
- Failure during the replacement/swap path restores the prior target where the platform permits; otherwise fail safely without deleting the backup.
- No temporary partial bundle is reported as successful.

### 1.3 Make `prepare_map.py --dry-run` a real dry run

**Location:** `tools/prepare_map.py` and related CLI/UI documentation or forwarding code.

The current `--dry-run` path still creates directories and performs extraction/SRI conversion before forwarding the flag to `auto_generate.py`. This is not a dry run.

Required change:

- Make dry-run a preflight/planning path: validate the requested inputs and print the steps, expected outputs, and tools that would be invoked.
- Do not create output directories, extract resources, invoke SRI, copy files, or start downstream generation in dry-run mode.
- Keep normal execution behavior unchanged.
- Ensure the CLI, UI labels/help, and documentation describe the same semantics. Do not retain a misleading `dry-run` label for a mode that writes files.

Acceptance tests:

- With dry-run enabled, assert that no output directory/file is created or modified.
- Assert that extraction/conversion subprocesses are not called.
- Confirm that invalid/missing input is still reported clearly during preflight.
- Confirm that normal mode still reaches the existing pipeline.

### 1.4 Remove private absolute paths from shareable manifests

**Location:** `tools/auto_generate.py` and manifest tests.

The current generated analysis manifest records resolved absolute paths for input files and glTF sidecars. Shared artifacts must not expose a Windows username, home directory, or local Steam/CS2 installation path.

Required change:

- Replace absolute local paths with stable bundle-relative paths or documented placeholders such as `<INPUT>/...` and `<CS2_GAME>/...`.
- Preserve source identity, hashes, file sizes, and the provenance needed for reproducibility.
- Apply one consistent policy to every path field in the generated manifest. Do not sanitize only the top-level input path while leaving sidecars or nested metadata exposed.
- Do not remove useful path structure when it can be represented safely relative to the bundle or source root.

Acceptance tests:

- Generate a manifest from temporary paths containing a simulated username and assert that no private absolute path appears anywhere in the serialized output.
- Verify that hashes, sizes, relative resource names, and provenance fields remain present.
- Cover path separators and normalization without assuming that every machine uses Windows.

### Phase 1 completion gate

Run focused tests for all four changes, then:

- `python -m unittest discover -s tests -v`
- `python tools/security_scan.py`
- Build SRI with the repository's existing .NET project/build instructions if `Program.cs` changed.
- Run a Dust2 smoke/regression check only if the required local game data and tools are already available and the run is bounded. Do not download tools, upgrade dependencies, or add game assets to the repository.

Review the final diff for unrelated changes, private paths, secrets, generated artifacts, and proprietary game data. Update `docs/STATE.md` and the relevant engineering documentation only for behavior that actually changed. Do not rewrite the full engineering review as a sprint log.

At the end of this run, stop. Do not begin the later phases automatically.

## 5. Phase 2 — 3DsVW and glTF correctness

Do this as a separate, reviewable implementation wave after Phase 1 is stable.

1. **Separate bounds by representation.** Keep Collision Bounds and NAV Bounds independently. Compute aggregate Scene Bounds as their union (and later include Render/Entity bounds). Keep the existing top-level viewer bounds compatible where possible, but make Fit View use aggregate scene bounds. Add a schema/version change if the payload contract changes.
2. **Correct primitive/material metadata.** `gltf_summary()` must not let the last material encountered overwrite the metadata for an entire node. Preserve per-primitive material identity and counts.
3. **Correct triangle accounting.** Explicitly validate glTF primitive mode. Handle indexed and non-indexed triangle lists correctly. Reject unsupported modes with a clear error rather than silently reporting incorrect counts.
4. **Correct transforms and bounds.** Compose parent and node transforms (matrix or TRS) for world-space bounds exactly once. Keep source geometry/local coordinates intact in the glTF asset if the viewer consumes the hierarchy itself. Tests must catch both missing and double-applied transforms.
5. **Preserve stable identity.** Node names are not unique. Use stable source/node/mesh/primitive identifiers; preserve the distinction between resource, instance, mesh, primitive, and material.
6. **Validate dependencies and extensions.** Reject unsupported required extensions and unsafe/missing external buffer references clearly. Resolve paths safely and keep all referenced assets inside the accepted input/bundle root.
7. **Support multiple assets/buffers deliberately.** Do not simply remove the current size caps. Design bounded per-asset/per-chunk limits and an explicit bundle contract before broadening the importer. Keep the current single-buffer PHYS path working throughout migration.
8. **Viewer lifecycle.** Suspend the animation-frame loop while the document is hidden and resume on `visibilitychange`. Ensure map/layer changes release old geometry/material resources. Add measurable progress for long loading stages where feasible.

Add synthetic fixtures for nested transforms, multiple materials/primitives, shared meshes, duplicate node names, indexed/non-indexed geometry, unsupported primitive modes, multiple buffers/chunks, unsafe URIs, missing sidecars, mismatched lengths, and geometry outside NAV bounds. Preserve the existing PHYS analysis results.

## 6. Phase 3 — NAV correctness and route semantics

1. **Ladders must participate explicitly in routing.** NAV ladders are currently parsed but are not included in area-connection Dijkstra search or the 3DsVW payload. Model ladder transitions as explicit directed transitions with endpoint/area relationships and direction constraints. Do not disguise a ladder as an ordinary flat area connection.
2. **Display and inspect ladders.** Add a distinct NAV-ladder layer/marker in 3DsVW. Make source/destination areas and direction inspectable.
3. **Do not invent traversal time.** A ladder transition may contribute a documented geometric/search cost if justified, but any ladder movement-time estimate must be labeled as an assumption until measured in-game. Keep route distance, movement estimate, and measured time distinct.
4. **Make point-to-area fallback Z-aware.** The current XY-centroid fallback can silently resolve a point to the wrong floor. Rank candidates using polygon containment plus vertical separation/plane height; return an explicit ambiguous/unmapped result when confidence is insufficient. Preserve candidate area IDs and diagnostics.
5. **Preserve graph semantics.** Test directed and one-way links, disconnected components, multiple floors, ladder direction, and routes that traverse ladders. Never rewrite the source NAV data to hide ambiguity.

## 7. Phase 4 — SRI resource discovery before geometry export

Treat this as a substantial, separate project milestone. Do not attempt the complete Source 2 world extractor in one pass.

### 4.1 First deliver a map-specific resource inventory

- Investigate actual current Dust2 resources using the pinned VRF version and installed CS2 layout.
- Identify the compiled map/world entry point, referenced world nodes, static models/props, and the real dependency chain.
- Investigate how the installed game's search paths and VPK layouts resolve referenced resources. `gameinfo.gi` must be used only after its actual search-path semantics are understood.
- Follow only the dependency graph required for the selected map. Do not dump every entry in every game archive.
- Report resource path/type, source package/loose-file origin, dependency parent, decode/export status, and omission/failure reason.
- Detect missing references and unsupported resource types explicitly. Never silently skip required geometry or substitute an unrelated resource.
- Keep game files read-only and all outputs outside the game directory.

The first acceptance result is a traceable Dust2 inventory/dependency report, not a render mesh. Verify it against actual files and VRF behavior. Do not infer that the map VPK itself is already a ready-to-render geometric scene; it contains compiled resources that must be correctly resolved and decoded.

### 4.2 Then implement geometry-only Render extraction

Once the inventory proves the dependency chain:

- Export useful structural world geometry and referenced static model/prop geometry.
- Geometry-only by default: positions, indices, required attributes, transforms, bounds, stable IDs, hierarchy, and lightweight material metadata. No original game textures, texture repacking/conversion, or CDN dependencies.
- Exclude decals only when they can be reliably identified without dropping useful structural geometry. Otherwise preserve them and document the limitation.
- Apply source/world transforms exactly once and record coordinate conversion/provenance.
- Preserve the validated PHYS exporter and current output contract. Render Geometry must be a separate representation, not a replacement for Collision Geometry.
- Preserve entity information and relationships even when the current UI does not display every field.

Do not upgrade VRF merely because a newer version exists. First document the exact API/format requirement and validate current PHYS/EntityLump behavior against the real-map regression corpus.

## 8. Phase 5 — Versioned map bundle and measured viewer scale-up

The map bundle should hold independent, versioned representations and source provenance. At minimum, plan for:

- map identity and CS2 build/version when available;
- sanitized relative source paths, source hashes/sizes, VRF/SRI versions, and extraction settings;
- coordinate convention (Hammer units, Source X/Y/Z-up), source/world transforms, and conversions;
- dependency records and explicit warnings/omissions/unsupported resources;
- independent Render, Collision, NAV, and Entity asset references, bounds, counts, and schema versions;
- separate canonical source-derived assets and display-optimized derivatives;
- per-asset hashes/sizes and an aggregate Scene Bounds value.

Do not assume one map equals one glTF file, one binary sidecar, one mesh, or one in-memory scene. Do not overwrite the only canonical export when rebuilding display assets.

Before adopting chunking, streaming, workers, instancing, LOD, or other optimizations, benchmark real Dust2 data. Record extraction time, peak memory, resource/object/material/vertex/triangle counts, canonical/display sizes, viewer download/load/initialization time, draw calls, frame rate, camera responsiveness, and memory where measurable. Implement only the optimizations justified by measurements. Then validate multi-level maps, especially Nuke, Vertigo, and Train.

The final viewer should expose independently switchable Render, Collision Solid, Collision Clips/Special Volumes, NAV Areas, NAV Connections, NAV Ladders, Entities/Spawns/Places, Routes, and diagnostic overlays. Layer visibility must not mutate source data or analytical results. The inspector should identify the originating layer and stable source object.

## 9. Recommended implementation order after the current run

| Priority | Workstream | Reason |
|---|---|---|
| P0 | Phase 1.1–1.4 stabilization | Prevent metadata corruption, loss of previous output, misleading dry-run behavior, and local-path disclosure |
| P1 | Phase 2 bounds/glTF correctness | Required before broad Render Geometry ingestion; prevents misleading 3D scenes and statistics |
| P1 | Phase 3 ladders and Z-aware NAV resolution | Fixes route coverage and multi-floor ambiguity in the existing analytical model |
| P2 | Phase 4.1 SRI inventory/dependency proof | De-risks the difficult Source 2 extraction work before implementing a large exporter |
| P2 | Phase 4.2 Render Geometry extraction + Phase 5 bundle | Adds the new visual representation without corrupting existing PHYS/NAV behavior |
| P3 | Measured viewer scalability improvements | Add only after real map export/load benchmarks demonstrate the bottleneck |

## 10. Final reporting requirements

All reports must be in English and must distinguish facts from assumptions. At the end of each phase, report only:

- **Implemented:** exact changes and affected files.
- **Verified:** exact commands/tests run and their observed outcomes.
- **Not verified:** anything not tested, unavailable, or still uncertain.
- **Compatibility:** whether the existing PHYS, NAV, route, 2D viewer, upload/drop, map library, and local-server workflows were preserved.
- **Security/privacy:** path handling, generated files, game-data handling, and relevant risks reviewed.
- **Next recommended task:** one concrete, bounded task.

Do not claim a full-map export, correct world geometry, ladder routing, multi-buffer support, or performance improvement unless it was actually implemented and verified against real data.
