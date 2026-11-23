# Architecture — CS2 Map Balance

**Status:** current `v1.0.0-pre.1` architecture after the SRI rename and the
container security audit.

## 1. Principles

1. The game installation is a read-only input. No component writes to the CS2
   or Steam directory, launches the game, reads its memory or interacts with
   anti-cheat.
2. Prepared data is separate from analysis. Ingestion produces explicit files;
   navigation, collision, movement, simulation and presentation operate on
   those files.
3. Visual, geometric, collision, navigation, movement, gameplay and balance
   data remain distinct.
4. Navigation is directed where the source requires it; one-way links,
   disconnected components, ladders and vertical relationships are preserved.
5. Uncertainty is explicit. A movement estimate is not a measurement; a
   time-only route result is not a balance verdict.
6. Reproducibility matters. Inputs, SRI version and output hashes are recorded.

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
 Python NAV parser          SRI entities                  SRI phys
 (existing)                 (EntityLump)                  (PHYS)
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

## 3. Component boundaries

### 3.1 Ingestion

`tools/prepare_map.py`:

- validates the map name and CS2 folder layout;
- extracts `<map>.nav`, `default_ents.vents_c` and `world_physics.vmdl_c` from
  the map VPK with the project's own VPK reader;
- invokes `cs2mb-sri entities` and `cs2mb-sri phys` with argument arrays,
  timeouts and explicit paths;
- writes `prepared_manifest.json` with relative provenance, sizes, SHA-256
  values and the SRI path/version/hash.

`tools/sri.py` is the only Python entry point for locating and running SRI.
Resolution order is explicit path, `CS2MB_SRI`, packaged locations, then
`PATH`. No `shell=True`.

### 3.2 SRI — Source Resource Inspector

SRI is a small first-party Windows x64 executable built from `sri/`. It links
the MIT ValveResourceFormat `20.1.7467` library in-process for binary KV3,
Zstandard/LZ4, PHYS and EntityLump decoding. It is not a universal Source 2
viewer/editor, and it does not launch Source2Viewer-CLI or resourceinfo.

Commands:

```text
cs2mb-sri inspect --input <resource>
cs2mb-sri phys-summary --input <world_physics.vmdl_c>
cs2mb-sri phys --input <world_physics.vmdl_c> --output <world_physics_physics.gltf>
cs2mb-sri entities --input <default_ents.vents_c> --output <entities.txt>
```

### 3.3 Navigation

The existing Python parser builds directed areas, connections, one-way links,
components, ladders and z-aware lookups. SRI does not replace or alter this
layer.

### 3.4 Collision

SRI writes a glTF 2.0 mesh set plus a `.bin` sidecar:

- one primitive per collision-attribute × surface-property group;
- triangle positions in Hammer units and Source axes (`x`, `y`, `z-up`);
- `InteractAs`, `SurfaceProperty` and `CollisionGroup` in node extras;
- material names that preserve clip/sky semantics for the existing filters.

The existing collision loader (`tools/gltf_collision.py`) consumes the files
unchanged. It ignores any glTF node matrix, so SRI deliberately does not emit
the legacy render-time `meters/Y-up` matrix.

### 3.5 Entity data

SRI writes the same line-oriented entity dump contract consumed by
`tools/nav_experiment.py` and `tools/auto_generate.py`: class names, origins,
angles, target names, callout names and other entity properties. The order puts
`classname`, `targetname`, `place_name` and `origin` first.

### 3.6 Movement, simulation and balance

These Python modules are unchanged. The converter migration did not change
movement assumptions, route semantics or balance calculations.

### 3.7 Viewer and library

The viewer generator, map library, manifests and upload/drop workflow are
unchanged. The viewer remains self-contained and offline.

## 4. Data contracts

| Contract | Producer | Consumer |
|---|---|---|
| `<map>.nav` | VPK extraction | existing NAV parser |
| entity dump `.txt` | SRI `entities` | `parse_entity_points`, auto-generation |
| `world_physics_physics.gltf` | SRI `phys` | `gltf_collision.py` |
| `world_physics_physics.bin` | SRI `phys` | glTF sidecar validation |
| `prepared_manifest.json` | `prepare_map.py` | provenance and job manifest |
| viewer HTML | `prototype/dust2_viewer.py` | local browser / server |

The manual upload path accepts `.nav`, `.txt`, `.gltf` and `.bin` and does not
require SRI or a CS2 installation.

## 5. Coordinate and geometry rules

- Hammer units, Source axes, z-up for analysis.
- No double transform: SRI writes the coordinates the existing loader expects;
  the node matrix is omitted.
- Physics geometry comes from `world_physics.vmdl_c`, not render geometry.
- Collision attributes and surface properties are preserved.
- Sphere/capsule primitives are tessellated with bounded ring counts; mesh and
  convex-hull geometry is emitted directly.

## 6. Local application security

- `127.0.0.1` only; `--allow-remote` and non-loopback hosts are rejected.
- Host allow-list and same-origin POST checks (`Origin`, `Sec-Fetch-Site`);
  missing Origin is rejected.
- Upload count/size/suffix limits, basename reduction and path confinement.
- Rejected uploads are removed; old uploads and job records are pruned.
- Maximum two simultaneous jobs; excess requests return `429`.
- 900 s job timeout; Windows process-tree termination includes SRI.
- Generated viewer and intake UI carry restrictive CSP/frame/referrer headers.
- SRI path, version and SHA-256 are recorded; manifests avoid personal absolute
  paths.

## 7. Distribution

The complete Windows package contains the application, SRI, a portable Python
3.13 runtime, launchers, documentation, checksums and an SPDX SBOM. The binary
is not committed to Git. Users do not download a separate converter release.

## 8. Validation layers

1. Synthetic malformed/truncated/oversized/unsupported-version resources.
2. Minimal valid resource header.
3. Endpoint security tests against the real HTTP handler.
4. Dust2 historical collision totals and floor agreement.
5. Nine active-duty maps: entity sets, collision counts, bounds and floor tests.
6. Existing Python suite, security scan, Markdown and asset checks.
7. Package extraction, launcher, SRI detection and HTTP startup checks.

See [VALIDATION.md](VALIDATION.md) and [STATE.md](STATE.md) for measured results
and limitations. A visual viewer is not proof of geometric or collision
correctness.

## 9. Known limits

- SRI is Windows x64 only.
- Curved collision primitives are tessellated approximations.
- Entity and PHYS layouts are validated against the recorded CS2 build; future
  Valve format changes may require an SRI update.
- The Python application remains stdlib-only for analysis; SRI is the only
  packaged binary component.
- The movement model does not include combat, utility, visibility or
  player-choice policy.
