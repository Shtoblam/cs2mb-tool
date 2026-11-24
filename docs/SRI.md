# SRI — Source 2 Resource Inspector

SRI (`cs2mb-sri`) is the first-party Source 2 resource inspector and converter
used by CS2 Map Balance. It is a .NET command-line tool that reads Source 2
resource files, reports their structure, and converts physics and entity data
into formats used by the rest of CS2MB.

## Role in CS2MB

SRI is the conversion step between extracted map resources and the analysis
pipeline:

```text
map VPK -> extracted .nav / .vents_c / .vmdl_c
        -> SRI -> entities.txt + collision glTF + BIN
        -> map preparation / analysis -> 2D viewer and 3DsVW
```

`tools/prepare_map.py` extracts the required resources and invokes SRI for the
EntityLump and PHYS conversions. The resulting collision glTF is consumed by
collision checks and by the [3DsVW map viewer](3D_VIEWER.md). NAV parsing is
performed by the Python pipeline, not by SRI.

## What it can inspect and convert

SRI exposes four commands:

| Command | Purpose |
|---|---|
| `inspect` | Print resource header, version, type, size and block list for a Source 2 resource. |
| `phys-summary` | Print a JSON summary of a PHYS block: parts, totals, bounds, surfaces and collision attributes. |
| `phys` | Convert PHYS collision data to glTF 2.0 and a binary buffer sidecar. |
| `entities` | Convert an EntityLump resource to the line-oriented `entities.txt` format. |

PHYS conversion preserves Hammer units and Source axes (`x`, `y`, `z-up`).
Meshes and convex hulls are emitted directly; spheres and capsules are
tessellated approximations with bounded segment counts. Collision attributes,
surface properties, collision groups and `InteractAs` values are preserved in
the generated glTF metadata.

SRI is **not**:

- a general VPK extractor — `prepare_map.py` extracts resources from the map VPK;
- a render-geometry or material/texture exporter;
- a NAV parser or route/balance calculator;
- a 3D viewer — [3DsVW](3D_VIEWER.md) renders the generated collision data.

## Using SRI independently

### Requirements

- Windows x64.
- .NET SDK 10.0.
- PowerShell for the provided build script.
- Network access for the first NuGet restore, unless packages are already cached.

The published executable is self-contained; the .NET runtime is not required on
the machine that runs it.

### Build the standalone executable

From the repository root:

```powershell
.\sri\build.ps1
```

The script restores packages and publishes a trimmed, single-file executable to:

```text
sri\dist\win-x64\cs2mb-sri.exe
```

Optional arguments:

```powershell
.\sri\build.ps1 -Configuration Release -Runtime win-x64
.\sri\build.ps1 -Install
```

`-Install` also copies the executable to `tools\bin\sri\cs2mb-sri.exe`, where the
application looks for it by default. The build may emit trim warnings from
third-party assemblies; the CS2MB code does not use reflection-based JSON
serialization.

### Command-line usage

```text
cs2mb-sri inspect --input <resource>
cs2mb-sri phys-summary --input <world_physics.vmdl_c>
cs2mb-sri phys --input <world_physics.vmdl_c> --output <world_physics_physics.gltf>
cs2mb-sri entities --input <default_ents.vents_c> --output <entities.txt>
cs2mb-sri --version
```

The four resource commands (`inspect`, `phys-summary`, `phys`, `entities`)
require `--input`; `phys` and `entities` also require `--output`. `--version`
and `--help` do not require or accept an input resource.
Successful commands return exit code `0`; usage, input and conversion errors
return a non-zero code and print a short error message to standard error.

### Practical examples

Inspect a resource:

```powershell
.\sri\dist\win-x64\cs2mb-sri.exe inspect --input .\world_physics.vmdl_c
```

Print a PHYS summary without writing files:

```powershell
.\sri\dist\win-x64\cs2mb-sri.exe phys-summary --input .\world_physics.vmdl_c
```

Convert collision geometry:

```powershell
.\sri\dist\win-x64\cs2mb-sri.exe phys `
  --input .\world_physics.vmdl_c `
  --output .\prepared\world_physics_physics.gltf
```

This writes the glTF file and a matching binary sidecar. The sidecar uses the
output stem; if the output does not already end in `_physics.gltf`, SRI adds
`_physics` to the sidecar stem. For example, `--output collision.gltf` writes
`collision.gltf` and `collision_physics.bin`.

Convert an entity lump:

```powershell
.\sri\dist\win-x64\cs2mb-sri.exe entities `
  --input .\default_ents.vents_c `
  --output .\prepared\entities.txt
```

### Expected inputs and outputs

- Inputs are read-only Source 2 resource files. The map preparation flow normally
  provides `world_physics.vmdl_c` and `default_ents.vents_c`.
- `inspect` and `phys-summary` write text/JSON to standard output.
- `phys` writes `*.gltf` plus `*.bin`; the glTF uses the generated binary sidecar.
- `entities` writes UTF-8 text consumed by the analysis pipeline and viewers.

### Basic troubleshooting

- **`cs2mb-sri` is not found**: build the executable or pass its full path; the
  packaged location is `tools\bin\sri\cs2mb-sri.exe`.
- **SDK not found**: install .NET SDK 10.0 and reopen the terminal.
- **Restore fails**: the first build needs access to NuGet or a populated package
  cache.
- **`resource has no PHYS block`**: use the map's compiled
  `world_physics.vmdl_c`, not an arbitrary map resource.
- **`DATA block is not an entity lump`**: use the compiled
  `default_ents.vents_c`.
- **Output directory missing**: SRI creates the output directory for `phys` and
  `entities`.

## Capabilities and limitations

Capabilities:

- bounded parsing through the bundled ValveResourceFormat library;
- PHYS summaries with separate `InteractAs` and `PhysicsTags`;
- collision glTF with per-primitive metadata;
- entity-lump conversion to a stable text format;
- deterministic, self-contained Windows executable.

Limitations:

- Windows x64 only for the provided build script;
- curved collision primitives are tessellated approximations;
- only PHYS and EntityLump conversion paths are part of the CS2MB contract;
- not a VPK browser, renderer, material exporter or NAV tool;
- the executable is not code-signed;
- future Valve resource-format changes may require a new SRI build.

See also: [3DsVW viewer guide](3D_VIEWER.md) ·
[architecture](ARCHITECTURE.md) · [setup](SETUP.md) ·
[SRI source notes](../sri/README.md).
