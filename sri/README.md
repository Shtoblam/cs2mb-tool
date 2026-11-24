# SRI — Source Resource Inspector

SRI is the first-party Source 2 resource inspector and converter for CS2 Map Balance.

The component reads the two compiled resources that the automatic intake
pipeline needs:

- `world_physics.vmdl_c` — decodes the `PHYS` block and writes collision
  geometry as glTF 2.0 plus a binary sidecar;
- `default_ents.vents_c` — decodes the `DATA` block as an `EntityLump` and
  writes the project's line-oriented entity dump.

It is not a wrapper around Source2Viewer-CLI. It links the MIT-licensed
[ValveResourceFormat](https://github.com/ValveResourceFormat/ValveResourceFormat)
library (`20.1.7467`) in-process and exposes a small CS2MB-specific command
line. The library provides the versioned binary KV3, Zstandard/LZ4, PHYS and
EntityLump decoders. CS2MB owns the command surface, resource validation,
coordinate contract and glTF/entity output.

## Why a packaged component

The Python application stays Python 3.13 + standard library. Source 2 binary
KV3 uses Zstandard and LZ4 and the compiled resources carry versioned PHYS and
EntityLump layouts. Reimplementing those codecs would add risk without helping
the map-analysis model. SRI is included in the complete CS2MB Windows package as a self-contained
x64 executable, so no .NET runtime, Source2Viewer-CLI or `resourceinfo.exe` is
required at runtime.

## Commands

```text
cs2mb-sri inspect --input <resource>
cs2mb-sri phys-summary --input <world_physics.vmdl_c>
cs2mb-sri phys --input <world_physics.vmdl_c> --output <world_physics_physics.gltf>
cs2mb-sri entities --input <default_ents.vents_c> --output <entities.txt>
cs2mb-sri --version
```

`phys` writes `<name>_physics.gltf` and `<name>_physics.bin`. Positions stay in
Hammer units and Source axes (`x`, `y`, `z-up`); the legacy VRF node matrix is
not applied. This matches the accepted CS2MB coordinate decision and keeps the
existing collision engine unchanged. Primitive grouping follows collision
attribute × surface property, preserving `InteractAs` and `SurfaceProperty`
metadata. `InteractAs` is read only from `m_InteractAsStrings`; `PhysicsTags`
is a separate summary field read only from `m_PhysicsTagStrings`.

## Build

Prerequisites: .NET SDK 10.0.x. Normal users do **not** need the SDK; they use
the SRI executable included in the complete CS2MB package.

```powershell
sri\build.ps1
sri\build.ps1 -Install   # also copies to tools\bin\sri\
```

The build is pinned by `global.json` and `Cs2mb.Sri/packages.lock.json`.
The publish command is self-contained, single-file, trimmed and excludes debug
symbols. Expected size is about 18 MB.

Maintainers can create a standalone diagnostic zip:

```powershell
sri\package.ps1
```

Outputs `sri/dist/cs2mb-sri-win-x64.zip` and `SHA256SUMS.txt`. This is not the
primary user download; SRI is shipped inside the complete CS2MB application
package.

## Security

- Read-only input; the component never writes to the game directory.
- Output paths are explicit command arguments supplied by the local pipeline.
- Inputs are untrusted binary resources. Parsing errors are reported as a
  concise non-zero exit, never as an unhandled stack trace.
- No network access, telemetry, process injection, game-process access or
  anti-cheat interaction.
- The executable is self-contained and does not download updates.

## Validation

SRI `1.0.0` was validated locally against the installed CS2 build
`2000948` (2026-11-19) for all nine active-duty maps. Mesh and convex-hull
geometry is exact; sphere and capsule primitives are tessellated with bounded
ring counts. Dust2 reproduces the historical collision totals exactly: 39
primitives, 1,306,947 exported vertices and 435,649 triangles. The repository's
floor test reports 98.77% agreement with nav floors, matching the historical
reference.

All nine maps were decoded and floor-tested:

| Map | Primitives | Triangles | Floor agreement |
|---|---:|---:|---:|
| de_dust2 | 39 | 435,649 | 98.77% |
| de_mirage | 41 | 133,133 | 99.06% |
| de_nuke | 32 | 191,628 | 99.27% |
| de_inferno | 52 | 2,733,610 | 99.54% |
| de_ancient | 15 | 967,778 | 98.73% |
| de_train | 40 | 1,574,220 | 99.39% |
| de_vertigo | 37 | 210,596 | 99.45% |
| de_anubis | 34 | 715,842 | 97.34% |
| de_overpass | 36 | 884,775 | 97.71% |

Entity output matches the local `resourceinfo` dump semantically for every map:
identical entity counts, class distributions and origins (one Inferno spawn
differs only by 0.01 units from text formatting). These are local integration
results, not claims about every CS2 build. See `docs/STATE.md` and
`docs/RESEARCH.md` for the current evidence and limits.
