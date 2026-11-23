# Optional Source2Viewer CLI

Place the pinned Windows CLI files here so the app can extract collision from
the installed game automatically.

Download **`cli-windows-x64.zip`** from the official
[ValveResourceFormat 20.1 release](https://github.com/ValveResourceFormat/ValveResourceFormat/releases/tag/20.1),
then extract **all three files**:

```text
tools/bin/Source2Viewer-CLI.exe
tools/bin/libSkiaSharp.dll
tools/bin/spirv-cross.dll
```

Do not copy only the `.exe`; the two DLLs are required. Do not put these files
inside the CS2/Steam installation.

The binary is not committed. Alternatively set `S2V_CLI` or configure
`config/paths.local.json`; keep the three files together.

Without this CLI, map intake still works by uploading
`world_physics_physics.gltf` + `.bin`.
