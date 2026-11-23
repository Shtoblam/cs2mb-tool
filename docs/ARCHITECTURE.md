# Architecture — CS2 Map Balance

**Status:** current pre-alpha v1.0 architecture after the internal Source 2
engine integration (2026-11-23). Historical research remains in
[RESEARCH.md](RESEARCH.md); superseded decisions remain in
[DECISIONS.md](DECISIONS.md).

## 1. Principles

1. **The game installation is a read-only input.** No component writes to the
   CS2/Steam directory, launches the game, reads its memory, or interacts with
   anti-cheat.
2. **Prepared data is separate from analysis.** Ingestion produces explicit
   files; navigation, collision, movement, simulation and presentation operate
   on those files and never silently re-read the game.
3. **Layers stay distinct.** Visual, geometric, collision, navigation, movement,
   gameplay and balance data are not interchangeable.
4. **Navigation is directed where the source requires it.** One-way links,
   disconnected components, ladders and vertical relationships are preserved.
5. **Uncertainty is explicit.** A movement estimate is not a measurement; a
   time-only route result is not a balance verdict.
6. **Reproducibility matters.** Inputs, component versions and output hashes are
   recorded in the preparation manifest.

## 2. Runtime pipeline

```text
Installed CS2 (read-only)
        |
        v
   Map VPK reader (Python, stdlib)
        |
        +----------------------------+-----------------------------+
        |                            |                             |
        v                            v                             v
   <map>.nav                default_ents.vents_c          world_physics.vmdl_c
        |                            |                             |
        v                            v                             v
 Python NAV parser          cs2mb-source2 entities        cs2mb-source2 phys
 (existing)                 (internal EntityLump)         (internal PHYS)
        |                            |                             |
        |                            v                             v
        |                     entity dump text              glTF + .bin
        |                            |                             |
        +----------------------------+-----------------------------+
                                     |
                                     v
                         Existing CS2MB analysis layer
                    nav graph · collision · movement · routes
                    scenarios · balance · library · viewer
                                     |
                                     v
                         artifacts/auto/<map>/<job>/
```

The `cs2mb-source2` component is a first-party Windows x64 executable built
from `source2/`. It links the MIT ValveResourceFormat library in-process for
binary KV3, Zstandard/LZ4, PHYS and EntityLump decoding. It is not
Source2Viewer-CLI under another name and it does not launch an external CLI.

## 3. Component boundaries

### 3.1 Ingestion

`tools/prepare_map.py`:

- validates the map name and CS2 folder layout;
- extracts `<map>.nav`, `default_ents.vents_c` and `world_physics.vmdl_c` from
  the map VPK with the project's own VPK reader;
- invokes `cs2mb-source2 entities` and `cs2mb-source2 phys` with argument
  arrays, timeouts and explicit paths;
- writes `prepared_manifest.json` with source paths, sizes, SHA-256 values and
  the engine path/version/hash.

`tools/source2.py` is the only Python entry point for locating and running the
engine. Resolution order is explicit path, `CS2MB_SOURCE2`, packaged locations,
then `PATH`. No `shell=True`.

### 3.2 Navigation

The existing Python parser builds directed areas, connections, one-way links,
components, ladders and z-aware lookups. The internal engine does not replace or
alter this layer.

### 3.3 Collision

The engine writes a glTF 2.0 mesh set plus a `.bin` sidecar:

- one primitive per collision-attribute × surface-property group;
- triangle positions in Hammer units and Source axes (`x`, `y`, `z-up`);
- `InteractAs`, `SurfaceProperty` and `CollisionGroup` in node extras;
- material names that preserve clip/sky semantics for the existing filters.

The existing collision loader (`tools/gltf_collision.py`) consumes the files
unchanged. It ignores any glTF node matrix, so the engine deliberately does not
emit the legacy render-time `meters/Y-up` matrix.

### 3.4 Entity data

The engine writes the same line-oriented entity dump contract consumed by
`tools/nav_experiment.py` and `tools/auto_generate.py`: class names, origins,
angles, target names, callout names and other entity properties. The order puts
`classname`, `targetname`, `place_name` and `origin` first so the existing
line-oriented parser sees them in the expected sequence.

### 3.5 Movement, simulation and balance

These Python modules are unchanged. The converter migration did not change
movement assumptions, route semantics or balance calculations. The current
model remains a straight-line calibrated time model, not a demo-tick or combat
simulation.

### 3.6 Viewer and library

The viewer generator, local library, manifests and upload/drop workflow are
unchanged. The viewer remains self-contained and offline.

## 4. Data contracts

| Contract | Producer | Consumer |
|---|---|---|
| `<map>.nav` | VPK extraction | existing NAV parser |
| entity dump `.txt` | `cs2mb-source2 entities` | `parse_entity_points`, auto-generation |
| `world_physics_physics.gltf` | `cs2mb-source2 phys` | `gltf_collision.py` |
| `world_physics_physics.bin` | `cs2mb-source2 phys` | glTF sidecar validation |
| `prepared_manifest.json` | `prepare_map.py` | provenance and job manifest |
| viewer HTML | `prototype/dust2_viewer.py` | local browser / server |

The manual upload path accepts `.nav`, `.txt`, `.gltf` and `.bin` and does not
require the engine or a CS2 installation.

## 5. Coordinate and geometry rules

- Hammer units, Source axes, z-up for analysis.
- No double transform: the engine writes the coordinates the existing loader
  expects; the node matrix is omitted.
- Physics geometry comes from `world_physics.vmdl_c`, not render geometry.
- Collision attributes and surface properties are preserved.
- Sphere and capsule primitives are tessellated with bounded ring counts;
  mesh and convex-hull geometry is emitted directly.

## 6. Validation layers

1. Synthetic malformed/truncated/oversized/unsupported-version resources.
2. Minimal valid resource header.
3. Dust2 historical collision totals and floor agreement.
4. Nine active-duty maps: parsed entity sets, collision counts, bounds and floor
   tests.
5. Existing 76-test Python suite, security scan and repository hygiene checks.

See [VALIDATION.md](VALIDATION.md) and [STATE.md](STATE.md) for measured results
and limitations. A visual viewer is not proof of geometric or collision
correctness.

## 7. Security boundaries

- Loopback-only server by default.
- Upload size/count/suffix allow-listing, path confinement and Origin checks.
- Job timeout and bounded logs.
- SHA-256 provenance for prepared inputs and outputs.
- No telemetry, external uploads, game-process access, injection or anti-cheat
  interaction.
- The engine executable is a local trusted component; its hash is recorded in
  the preparation manifest and can be checked against the release.

## 8. Known limits

- The engine emits mesh and convex-hull collision directly and tessellates
  sphere/capsule primitives; curved surfaces are analysis approximations.
- Entity and PHYS layouts are validated against the recorded CS2 build; future
  Valve format changes may require an engine update.
- The Python application remains stdlib-only for analysis; the engine is the
  only packaged binary component.
- The movement model does not include combat, utility, visibility or
  player-choice policy.
