# CS2MB Engineering Review
## Current implementation findings and desired technical direction

**Review baseline:** `main` at commit `4bd4068514439199888c03a59a9503980990e60f` (`v1.1.0`)  
**Review date:** 2026-11-24  
**Repository:** https://github.com/Shtoblam/cs2mb-tool

---

## 1. Purpose and how to use this document

This document consolidates an independent engineering review of the current CS2MB repository and the agreed direction for its map-data architecture. It records concrete implementation findings, limitations that will become important as the project grows, and desired technical properties.

**This is not an implementation schedule, a prioritized sprint plan, or permission to perform a repository-wide rewrite in one pass.** The owner and the coding agent will review and divide the material into manageable tasks separately.

Before changing code:

1. Verify every finding against the current working tree. This review is based on the commit listed above; code may have changed since then.
2. Distinguish confirmed current behavior from a scalability risk, a design recommendation, or a hypothesis that still needs a technical experiment.
3. Identify dependencies, compatibility risks, affected contracts, tests, and whether a proposed change would alter existing analytical results.
4. Preserve the working v1.1.0 behavior unless a specific change is agreed and regression-tested.

Do not silently reinterpret uncertain observations as proven bugs. Do not claim that a feature is implemented merely because it is described here as a desired direction.

## 2. Core architectural rule: keep map representations independent

CS2MB should treat one map as several independent, complementary representations. These representations describe the same game world, but they are not interchangeable and are not expected to have identical geometry.

### 2.1 The representations

- **Render Geometry** — the visual world geometry exported from Source 2 map/world resources: floors, walls, structural pieces, static map objects and other useful visible geometry. Its primary purpose is visual context and spatial inspection.
- **Collision Geometry** — the physical/collision geometry decoded from PHYS resources. It may contain simplified surfaces, collision-only volumes, player clips, NPC clips, grenade clips, special collision groups and other physical semantics. Its purpose is collision and movement analysis.
- **NAV Geometry and Graph** — navigation areas, directed connections, ladders and other NAV topology. It is the basis for navigation-graph routing, not a complete description of what a human player can physically traverse.
- **Entity Data** — entity origins, angles, classes, target names, places, spawn points, bombsite-related entities and other useful map metadata.
- **Analysis and simulation data** — derived measurements, route results, movement estimates and balance-oriented calculations. These must retain provenance and must not be confused with raw map data.

Each representation must remain identifiable in storage, APIs, viewer layers, diagnostics and reports.

### 2.2 Shared coordinates, not geometric fitting

Render, Collision, NAV and Entities must be expressed in the same authoritative map/world coordinate system so they can be displayed together.

The current CS2MB analytical convention is:

- Hammer units;
- Source axes: X, Y, Z-up;
- coordinates in the map's world space.

Apply source-defined coordinate conversions and object/world transforms correctly and exactly once. Preserve each source's own transform information and record any conversion in the bundle manifest.

**Do not force Render Geometry and Collision Geometry to become a 1:1 geometric match.** Specifically, do not:

- run ICP or another geometry-registration procedure to pull one mesh onto the other;
- scale, rotate, translate or deform one representation merely to minimize visual differences;
- snap vertices, weld surfaces across representations or "repair" one source using the other;
- automatically move collision floors to render floors;
- overwrite the original exported geometry with a corrected or fitted version.

The common map origin and coordinate convention are shared. The actual source geometry is not modified to make the representations coincide.

Differences are expected and often useful. Collision can be simplified, can omit decorative geometry, can include invisible blocking volumes, and can use surfaces that do not visually coincide with the rendered surface. Render exports can also omit or approximate some game features. These differences must remain observable.

A future comparison feature may measure and visualize discrepancies, but it must report them rather than silently correct them. Any future correction experiment must produce a separate, explicitly derived artifact while preserving both original sources.

### 2.3 Separate source data from display and analysis derivatives

Keep a clear distinction between:

1. **Canonical source-derived geometry** — the faithful output of the relevant extractor, with source metadata and transforms preserved.
2. **Display geometry** — an optimized representation for interactive rendering. It may use chunks, LODs, merged draw groups or other display-only optimizations.
3. **Analysis geometry** — data structures suitable for collision queries, spatial indexing, ray tests or other calculations.

Display optimization must not silently change canonical geometry. Decimation or aggressive simplification must not be used as the authoritative source for walkability, collision validation or other analysis that depends on the original collision surface.

Small Z offsets used only to avoid z-fighting in the viewer (for example, raising NAV overlays or route lines slightly above a surface) are presentation offsets. Keep them in the rendering layer only. Data coordinates, route calculations, inspectors and exported analysis must retain their original values.

## 3. SRI — expand the Source Resource Inspector into a richer map-data engine

SRI is a first-party component and should be developed further as a central Source 2 resource inspection, decoding and extraction component. The goal is not merely to add one command that exports a render mesh. The goal is to make SRI capable of discovering, inspecting and extracting substantially more useful information from CS2 map resources while retaining controlled scope, reliable output and traceability.

### 3.1 Current SRI scope

At the review baseline, `sri/Cs2mb.Sri/Program.cs` exposes:

- `inspect`;
- `phys-summary`;
- `phys`;
- `entities`.

It links the pinned ValveResourceFormat library (`20.1.7467`) in-process. Current automatic preparation in `tools/prepare_map.py` extracts a small, fixed set of resources from the map VPK: NAV, the default entity lump and the world physics resource. It then asks SRI to decode PHYS and EntityLump data.

This is a useful and validated foundation, but it is not yet a full map-resource extraction pipeline. Do not describe it as one.

### 3.2 Broader information SRI should be able to inspect and extract

Investigate and, where supported by the available Source 2 data and VRF APIs, extend SRI to discover and expose the useful map data needed by CS2MB, including:

- map/world resource inventory and resource types;
- the compiled map/world entry point and its referenced world nodes or equivalent structures;
- dependency relationships between map resources and referenced resources;
- static world geometry and referenced static model/prop geometry needed to represent the map usefully;
- per-object and hierarchical transforms, including the correct composed world transform;
- geometry bounds, mesh/primitive counts and stable resource/object identifiers;
- entity data and relevant properties/connections beyond only the currently selected spawn/place fields;
- PHYS shapes and all relevant collision metadata, preserving distinctions between collision attributes, `InteractAs`, physics tags, surface properties and collision groups;
- map resource version information and other metadata useful for provenance and compatibility checks;
- material metadata (names, identifiers and relevant flags) where available, without requiring texture extraction.

The exact Source 2 resource types and dependency path must be discovered from real current CS2 files and VRF behavior. Do not assume that one file, one VPK entry or one resource type contains the entire map. Do not blindly dump every entry in every game archive. Build a traceable map-specific inventory and follow the actual dependency chain required to construct the desired map representation.

### 3.3 Resource discovery and dependency resolution

The current preparation path checks that `gameinfo.gi` exists, but does not use it to resolve general resource search paths. A fuller extractor must investigate the actual game search paths and dependency locations.

The map's main VPK may not contain every referenced model, world node or other resource. The extractor should be able to resolve the correct referenced resources from the relevant game VPKs and loose files, using the installed game layout and search-path rules as appropriate.

Requirements:

- Support the actual VPK layouts encountered in the installed CS2 build, including the map VPK and referenced resource packages.
- Resolve paths safely and deterministically; handle case differences where the format/filesystem requires it.
- Record where each resource came from and why it was selected.
- Detect missing references and unsupported resource types and report them explicitly.
- Avoid silently skipping required geometry or substituting an unrelated resource.
- Keep game files read-only. All generated files must be written outside the game installation.
- Do not add game assets or extracted map geometry to Git.

A resource inventory/report should make it possible to understand what SRI found, what it exported, what it intentionally omitted and what it could not decode.

### 3.4 Geometry-only export by default

Original game textures and decals are not required for the initial Render Geometry viewer.

Default output should therefore be geometry-focused:

- positions, indices and required geometry attributes;
- object/resource identifiers and hierarchy;
- world transforms and bounds;
- lightweight material identity/metadata where useful;
- no original texture images;
- no texture conversion or repacking;
- no decal geometry when it can be reliably identified and excluded without removing useful structural geometry.

Use neutral or simple viewer materials based on metadata/categories. If decals cannot be reliably separated at extraction time, document that limitation and investigate a safe downstream filtering method. Do not silently delete geometry merely because it looks decorative.

Texture compression is not a substitute for omitting textures. Do not spend time producing reduced-resolution game textures for the first geometry-only milestone. Geometry size, object count, index layout, chunking and browser memory are likely to be important independently of texture storage. Revisit optional texture support only if a demonstrated later use case justifies it.

### 3.5 Preserve the validated PHYS and EntityLump contracts

Do not casually replace the existing PHYS decoder or change its output semantics while adding other resource types.

The current PHYS path has real-map validation and existing downstream consumers. Preserve:

- Hammer-unit coordinates and Source axes;
- bind-pose handling;
- collision attributes and surface properties;
- collision group and interaction metadata;
- bounded sphere/capsule tessellation;
- current glTF + binary sidecar compatibility until a versioned replacement is ready.

Review the metadata helper in `SummarizePhys()`: the current `SafeArray(attribute, "m_InteractAsStrings", "m_PhysicsTagStrings")` fallback can place physics-tag strings into the `InteractAs` field when the first property is unavailable. These are distinct concepts and must not be conflated. Read each property from its own source and represent missing values as missing/empty, not as a different field.

Entity extraction should preserve all useful fields and relationships, even if the current viewer displays only a subset. Avoid lossy parsing that prevents future analysis.

### 3.6 VRF versioning and robustness

The pinned ValveResourceFormat version is a deliberate dependency boundary. Do not upgrade it just because a newer version exists. First inspect the relevant API and format changes, then validate all existing PHYS and EntityLump behavior against the real-map regression corpus before changing the pin.

SRI should provide:

- deterministic output for identical input and tool versions;
- controlled error messages for malformed, truncated, unsupported or inconsistent resources;
- explicit limits for input size, decoded object counts and geometry output;
- cancellation/timeout behavior that does not leave partial output presented as complete;
- clear format/version metadata;
- tests for malformed input and real-map integration;
- an output manifest with source hashes and SRI/VRF versions.

Large exports must be designed with memory use in mind. The present PHYS writer accumulates grouped vertices/indices and then writes a binary stream. That is acceptable for the current validated scope, but a substantially larger world export may require chunked or streaming output to avoid large duplicate in-memory copies. Measure before choosing a replacement design.

## 4. Map bundle and data contracts

The project should have a versioned, reproducible map-data bundle that can hold multiple independent representations of one map.

The exact schema can be designed during implementation, but it should support at least:

- map name and map identity;
- CS2 build/client version where available;
- source VPK/resource paths in a sanitized relative form;
- source resource hashes and sizes;
- SRI version, VRF version and relevant extractor settings;
- coordinate convention, units, world origin and explicit source conversion matrices;
- source-resource dependency records;
- Render, Collision, NAV and Entity asset references;
- bounds and counts for each representation independently;
- output asset hashes, sizes and schema versions;
- explicit warnings, omitted resources and unsupported features.

Do not use a single set of bounds to represent every layer. Keep Render Bounds, Collision Bounds, NAV Bounds and aggregate Scene Bounds separate. The viewer's Fit View should use the aggregate scene bounds; layer-specific framing can use the corresponding individual bounds.

A future bundle may contain multiple glTF/GLB assets or spatial chunks rather than one giant scene file. The contract should not assume that the entire map always fits into one glTF JSON file and one binary sidecar.

Raw/prepared source-derived data and optimized viewer data must remain distinguishable. A viewer rebuild should not overwrite or destroy the only copy of canonical extracted data.

## 5. 3DsVW — prepare the viewer for independent Render and Collision layers

3DsVW currently visualizes SRI PHYS collision geometry with NAV, entities, places and route overlays. That is a useful v1.1.0 feature, but the current importer and rendering pipeline are too specialized to PHYS output to be treated as a general Source 2 world-geometry viewer without further work.

### 5.1 glTF ingestion limitations in the current builder

Review these concrete behaviors in `viewer3d/build.py`:

- `build_viewer3d()` currently requires exactly one binary buffer. A richer world export may require multiple assets, buffers or chunks.
- `gltf_summary()` reads material names while iterating primitives, but stores a single `material_name` for the node. With multiple primitives/materials, the last material can determine the node's summary/classification. Process metadata per primitive/material, not as one last-seen name for the entire node.
- Bounds are derived from accessor-local `min`/`max` values. Those values do not by themselves account for node transforms or parent hierarchy. Bounds must be computed in the correct world space after composing transforms.
- Triangle counts and processing currently assume triangle-list geometry. Inspect and explicitly validate supported glTF primitive modes and index/non-indexed cases; reject unsupported modes with a clear error rather than silently miscounting them.
- Node names are not guaranteed to be unique. Do not use names alone as stable object identifiers or metadata keys.
- glTF extensions and external dependencies need explicit support/validation. If an extension or dependency is not supported, report it clearly and fail safely; never silently reinterpret the data.

The current SRI PHYS output is deliberately simple and has a known coordinate contract. Do not infer from that one exporter that all world exports have the same structure.

### 5.2 Transform handling must be explicit

The project architecture documents that `tools/gltf_collision.py` ignores glTF node matrices because current SRI PHYS positions are already written in the coordinate system expected by the existing analysis loader.

That is a specific compatibility decision for the current PHYS contract, not a safe general glTF policy.

A general geometry importer must either:

- correctly compose node translation/rotation/scale and parent transforms into world coordinates exactly once; or
- preserve the hierarchy and matrices and ensure every downstream consumer applies them correctly.

Do not have one importer apply transforms while another silently ignores them. Tests must catch both missing and double-applied transforms.

Keep the existing PHYS contract stable during migration. Any generalized loader must prove that the existing collision analysis results remain unchanged.

### 5.3 Multi-material and object metadata

Render worlds can contain many objects and materials. Preserve the distinction between:

- source resource/object identity;
- node/instance identity;
- mesh identity;
- primitive identity;
- material identity;
- material name or surface category.

One node can contain multiple primitives and one material can be reused by multiple objects. Grouping/merging for draw-call efficiency must not erase the ability to inspect the original object and its source metadata.

### 5.4 Performance and memory

The current collision loading path in `viewer3d/assets/viewer.js` performs expensive CPU-side processing:

- traverses the loaded glTF scene;
- clones geometry;
- applies world matrices;
- for classification, may convert indexed geometry to non-indexed geometry;
- iterates triangle-by-triangle and builds separate JavaScript arrays for floor, wall and other surfaces;
- creates additional BufferGeometry and pickable objects.

This is manageable for the current Collision dataset, but a full render world can be much larger in node count, vertex count and memory footprint.

The existing viewer also switches to a less detailed classification path when collision geometry exceeds a triangle threshold. That fallback is useful as a safety measure, but its behavior and layer semantics must be explicit; a large dataset must not silently appear correctly classified when it is not.

The viewer should evolve toward a scalable rendering pipeline with appropriate combinations of:

- spatial chunking;
- lazy/on-demand chunk loading and disposal;
- indexed geometry preservation where possible;
- shared geometry/material reuse and instancing for repeated assets;
- spatial/material grouping that preserves object identity;
- frustum culling at useful spatial granularity;
- display-only LOD for distant geometry;
- bounded work per frame or worker-based preprocessing where appropriate;
- explicit memory and geometry limits with useful user-facing errors.

Do not implement every optimization speculatively. Measure actual Dust2 data first. Record export size, load time, peak process memory, browser memory where measurable, triangle/vertex counts, object count, draw calls, frame rate and responsiveness during camera movement. Include the viewer's embedded and separate-tab modes.

The current builder limits include a small glTF JSON size cap, a binary sidecar cap and a total collision-triangle cap. These should not simply be removed or raised arbitrarily. Replace one-file assumptions with explicit, safe per-asset/per-chunk limits and predictable failure behavior as the bundle architecture evolves.

### 5.5 Bounds, display layers and identity

The current `build_payload()` replaces collision-derived bounds with NAV-derived bounds whenever NAV corners exist. That is not suitable for a world containing render objects outside the NAV footprint or high/low structures beyond NAV limits.

Keep independent bounds per representation and calculate aggregate scene bounds as their union.

3DsVW should expose independently controllable layers for at least:

- Render;
- Collision solid geometry;
- Collision clip/special volumes;
- NAV areas;
- NAV connections;
- NAV ladders;
- entities/spawns/places;
- routes;
- future analysis/debug overlays.

Keep Render visibility and Collision visibility independent. Support simultaneous overlay without modifying either dataset. The object inspector should make the source layer and source identity clear.

NAV/routes/entities are currently raised by small display-only offsets in places to reduce z-fighting. Keep such offsets strictly in rendering and do not alter the underlying data or analysis coordinates.

### 5.6 Viewer lifecycle and UI responsiveness

The current `tick()` loop in `viewer3d/assets/viewer.js` schedules another `requestAnimationFrame()` even when `document.hidden` is true. It skips rendering while hidden, but the animation-frame loop continues to be scheduled. Prefer suspending the loop while hidden and restarting on `visibilitychange`.

Large geometry processing must not freeze the UI for a long period without feedback. Show progress for download, parsing, chunk preparation and rendering where those stages are measurable. Errors should identify the failing stage. Ensure memory is released when changing maps or unloading layers.

The current quality control primarily changes renderer pixel ratio. Do not imply that it controls geometry complexity or LOD unless those features are actually implemented.

### 5.7 Long-term direction and implementation flexibility

The intended direction is to evolve the existing 3DsVW into a general-purpose, multi-representation CS2 map viewer, not to replace it with an unrelated viewer or to perform a complete rewrite by default.

Preserve the existing Three.js/WebGL2 foundation and working viewer capabilities wherever they remain suitable. The current PHYS-based Collision viewer is a useful, validated starting point. New capabilities should be integrated incrementally behind clear data contracts, while retaining the existing PHYS behavior and compatibility requirements described above.

The viewer should ultimately provide one coherent scene in which Render Geometry, Collision Geometry, NAV, Entities and analysis overlays can be inspected together, while each representation remains independently identifiable, independently controllable and faithful to its source. A user should be able to compare layers visually without the viewer modifying, fitting or conflating their underlying data.

The viewer architecture should not assume that a complete map is one mesh, one glTF file, one binary buffer or one in-memory scene. It should be capable of growing toward multi-asset and spatially chunked map bundles, with scalable loading, rendering, inspection and disposal. The specific combination of chunking, streaming, instancing, LOD, workers and other optimizations should be selected based on measurements from real maps rather than adopted as a checklist without evidence.

Keep the responsibilities separated:

- SRI discovers, resolves, decodes and exports source-derived map resources.
- The map bundle stores versioned, traceable representations and their metadata.
- The viewer loads and presents those representations, manages display-only optimizations and exposes inspection tools.
- Analysis systems consume the appropriate canonical data and must not depend on lossy display-only geometry.

Do not move extraction or analytical responsibilities into the viewer merely because it is convenient for rendering. Likewise, do not make the viewer responsible for correcting disagreements between Render, Collision and NAV data. It may expose comparisons, diagnostics and visual overlays, but source-derived representations must remain unchanged.

This section describes the desired long-term properties of 3DsVW. It does not prescribe a single implementation sequence, require all capabilities to be delivered together, or authorize a repository-wide rewrite. Work may be split into independently reviewable changes. Before each substantial change, verify the current implementation, identify affected contracts and dependencies, preserve working behavior, and add focused regression tests. Prioritize implementation separately with the project owner. A smaller, validated improvement is preferable to a broad refactor that temporarily breaks the existing viewer.

## 6. NAV and route logic

NAV remains the primary high-level routing graph. Collision and Render are supporting spatial layers; they must not replace the NAV graph with generic triangle-mesh pathfinding.

### 6.1 Ladders are parsed but not part of route search or the 3D payload

The current NAV parser in `tools/nav_inspect.py` reads the ladder table and stores ladder endpoints, direction and related areas in `NavMesh.ladders`. However:

- `dijkstra_edges()` searches area-to-area `connections`;
- it does not create graph transitions using the separate ladder table;
- `viewer3d/build.py` does not include the parsed ladder data in its payload;
- 3DsVW therefore does not currently display NAV ladders as a distinct navigation element.

This is a real coverage gap, especially for maps where ladder traversal affects routes.

Represent ladders as explicit transition edges with their own semantics, direction constraints and endpoint relationships. Do not pretend a ladder is an ordinary flat area connection. Ensure one-way and direction rules are preserved. Include ladder geometry/markers in 3DsVW and make it possible to inspect the areas connected by each ladder.

If ladder movement time is estimated, expose the assumption and uncertainty. Do not present a heuristic ladder speed as a measured engine result.

### 6.2 Multi-level area resolution must never silently choose the wrong floor

The current `resolve_area()` path first calls the NAV point lookup, but its fallback `nearest_area_2d()` chooses the area by XY centroid distance only. On multi-level maps, that fallback can select an area on another floor when no containing area is found.

Use Z-aware candidate ranking and explicit ambiguity reporting. If a point cannot be resolved confidently, report it as ambiguous/unmapped rather than silently assigning a possibly unrelated floor. Preserve candidate area IDs and distances/heights for diagnostics.

A visually plausible marker on the wrong floor is not acceptable evidence that the mapping is correct.

### 6.3 Distinguish NAV routing from player traversability

A NAV route represents the bot/navigation abstraction. It does not prove that every human-player movement is physically possible, nor does a collision mesh alone define a complete player route.

Keep distinct concepts for:

- NAV graph reachability and route cost;
- collision-based obstruction/clearance checks;
- future player traversability constraints (player radius/height, step height, jump, crouch, slope, ladder use and movement rules).

The current wall/clearance/sweep tools are useful diagnostics, but their checks are approximations (for example, point samples or limited-height/limited-path probes, not a complete 3D swept player capsule simulation). Reports must keep these limitations visible and treat flags as candidates for inspection, not automatically as proven NAV errors.

A future route-validation layer may check NAV transitions against collision geometry, improve path points, and model player constraints. This must not rewrite the source NAV graph or conflate a bot route with a human-player route.

### 6.4 Route geometry and movement estimates

The current route points are derived from NAV area transitions and edge midpoints. They are not a recorded player trajectory. Smoothing/string-pulling can be explored, but must respect NAV connectivity, one-way links, floors, ladders and collision constraints.

The current movement model explicitly describes itself as a first-pass straight-line ground model. The route profile adds simplified segment/turn/vertical metrics and a jump-time budget. Preserve those caveats:

- a modelled travel time is an estimate, not a measured match route;
- straight-line ground movement does not simulate all ramps, stairs, collision responses, air control, turning or player decisions;
- a jump airtime budget is not a full jump trajectory or proof that a jump is feasible;
- time-only balance is not a full round-win or map-balance verdict.

Do not remove uncertainty labels or upgrade an estimate into a claim of exact CS2 behavior without new in-game measurements and regression evidence.

## 7. Pipeline correctness and artifact safety

### 7.1 Viewer bundle replacement should be transactional

In `viewer3d/build.py`, the current builder deletes an existing `viewer3d` output directory before the new bundle has been fully written and validated.

If the new build fails after deletion, the previous working viewer bundle is lost.

Build into a fresh temporary directory, validate all expected files and references, then replace the old bundle only after the new bundle is complete. Preserve the previous valid output on failure. Apply the same principle to larger map-bundle generation where practical.

### 7.2 The current prepare-map dry-run is not a true dry run

In `tools/prepare_map.py`, `--dry-run` currently does not prevent extraction and SRI conversion: the script creates output directories and writes prepared resources before it forwards the flag to `auto_generate.py`.

Either implement a genuine no-write/no-conversion dry-run that validates inputs and prints the actions that would be taken, or rename/document the existing behavior so the flag does not promise a dry run that it does not perform. Keep the semantics consistent across CLI, UI and documentation.

### 7.3 Sanitize absolute paths in generated manifests

In `tools/auto_generate.py`, the generated analysis manifest currently records `path.resolve()` for inputs and glTF sidecars. On Windows this can expose local usernames and installation paths if a user shares an artifact.

Use stable relative paths or sanitized placeholders (such as `<CS2_GAME>` and bundle-relative paths), while retaining the information needed for reproducibility. Keep hashes, file sizes and source identities. Do not leak a user's home directory or account name into shareable reports.

The preparation manifest already follows a redaction approach; apply a consistent policy to all generated manifests and reports.

### 7.4 Keep generated artifacts self-consistent

A map bundle should not be marked successful until every referenced file exists, its size/hash is correct, all sidecars are confined to the bundle and all required schema validations pass. Partial output should be marked incomplete/failed and should not replace a previous valid bundle.

Keep explicit schema versions for bundle, viewer payload and derived reports. Validate compatibility rather than silently accepting unknown schemas.

## 8. Test and validation requirements

The existing real-map validation and unit tests are valuable and must remain in place. New features need tests that exercise the complexity the current implementation does not yet represent.

### 8.1 SRI and map extraction tests

Include:

- current real Dust2 map extraction as the first end-to-end proof of the broader extraction path;
- inventory and dependency-resolution checks;
- missing and unsupported resource reporting;
- transforms and parent/child composition;
- repeated resources/instances;
- multiple meshes and primitives per object;
- malformed/truncated/oversized compiled resources;
- deterministic manifests and output hashes;
- preservation of existing PHYS triangle counts/metadata and EntityLump regression results.

The Dust2 test must verify geometry and metadata against known map bounds/landmarks and the other available map representations. This is coordinate validation, not geometric fitting.

### 8.2 glTF and 3DsVW tests

Add synthetic fixtures for:

- nested node transforms (translation, rotation and scale);
- the same transform applied exactly once;
- multiple primitives with different materials in one node;
- multiple nodes sharing one mesh/material;
- duplicate node names with distinct stable identities;
- indexed and non-indexed geometry;
- supported and unsupported primitive modes;
- multiple buffers/chunks if the new bundle supports them;
- missing sidecars, unsafe external URIs and buffer-length mismatches;
- world-space bounds across parent/child hierarchies;
- geometry that extends outside NAV bounds;
- independent Render/Collision/NAV visibility and simultaneous overlay;
- transactional bundle replacement after both successful and failed builds.

### 8.3 NAV and routing tests

Add tests for ladder graph transitions and direction, ladder visualization, multi-level point resolution, ambiguous points, disconnected components, one-way links and route paths that move between floors.

Collision validation tests must continue to distinguish a confirmed obstruction from a heuristic warning.

### 8.4 Real-map validation and performance evidence

Dust2 is the first target for new full-map extraction and dual-geometry overlay. Validate on that map before generalizing, but do not hard-code Dust2 assumptions into the architecture.

For the Dust2 prototype, record at least:

- source game build and resource hashes;
- resources discovered, exported, skipped and unresolved;
- Render/Collision/NAV/Entities counts and independent bounds;
- vertex/triangle/object/material counts where applicable;
- canonical and display bundle sizes;
- extraction time and peak memory;
- viewer download/load/initialization time;
- draw calls, frame rate and responsiveness during camera movement;
- browser/process memory where measurable.

Then verify that other maps, especially multi-level maps such as Nuke, Vertigo and Train, do not break coordinate, bounds, NAV or ladder assumptions. Do not extrapolate one Dust2 benchmark to all maps.

## 9. Compatibility and preservation requirements

- Preserve the current working v1.1.0 pipeline and its validated outputs while adding new capabilities.
- Do not break the existing upload/drop workflow, 2D viewer, map library, settings, local-only server behavior or packaged Windows release without an explicit reason and regression tests.
- Do not change PHYS coordinates, collision semantics, NAV interpretation or movement assumptions as an accidental side effect of adding Render Geometry.
- Keep SRI and the viewer self-contained/offline; do not add CDN dependencies.
- Keep the installed CS2 directory read-only.
- Do not commit extracted map VPK contents, NAV files, PHYS exports, Render Geometry, game textures or other Valve game assets.
- Preserve original source-derived data and provenance. Any optimized or experimental representation must be clearly marked as derived.
- Update documentation when behavior or data contracts genuinely change; do not describe unimplemented functionality as available.

## 10. Confirmed findings versus scale-up concerns

For clarity, the following observations were directly visible in the reviewed source at the baseline commit:

- SRI exposes the four commands listed in section 3.1.
- `prepare_map.py` extracts a fixed set of NAV/entity/PHYS resources.
- `viewer3d/build.py` requires one glTF buffer, summarizes material names at node level, derives accessor bounds without composing hierarchy transforms, uses NAV bounds in preference to collision bounds when NAV corners exist, and removes the existing viewer output before writing the replacement.
- The viewer's collision loader clones and processes geometry and may expand indexed geometry for triangle classification.
- The viewer's hidden-document tick still schedules another animation frame.
- NAV ladders are parsed into the NAV data model but are not included in the Dijkstra area-connection search or 3DsVW payload.
- The NAV fallback `nearest_area_2d()` ranks by XY centroid distance only.
- `prepare_map.py --dry-run` still performs preparation/extraction work.
- `auto_generate.py` stores resolved absolute input and sidecar paths in its manifest.
- The PHYS summary helper can use physics-tag strings as a fallback value for `InteractAs`.

Other items in this review (full Source 2 world dependency resolution, render-world completeness, large-map performance, streaming strategy and future player-traversability modelling) are design requirements or risks to investigate, not claims that the feature already exists or that a specific implementation has already failed.

---

**Central principle:** CS2MB should preserve several faithful, independent representations of the same map, place them in one documented world coordinate system, and make their relationships inspectable. It must not manufacture agreement between them.
