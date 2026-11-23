# Getting map files

This guide produces the four inputs the app expects:

```text
<map>.nav
entities.txt
world_physics_physics.gltf
world_physics_physics.bin
```

The app never launches CS2 or Steam and never writes to the game directory.
All commands below are read-only with respect to the game.

## Fast path: automatic extraction

If you do not want to run these commands manually:

1. Put `Source2Viewer-CLI.exe` in `tools/bin/` or set `S2V_CLI`.
2. Start the app.
3. Enter `CS2 game folder` and the map name.
4. Click **Prepare + Generate**.

The app runs the same extraction steps internally. The manual path below is a
fallback and for debugging.

## Source2Viewer-CLI setup

For automatic generation, download the official Windows x64 CLI archive from
the [ValveResourceFormat 20.1 release](https://github.com/ValveResourceFormat/ValveResourceFormat/releases/tag/20.1):

```text
cli-windows-x64.zip
```

Extract **all three files** into the project folder:

```text
cs2mapbalance\tools\bin\Source2Viewer-CLI.exe
cs2mapbalance\tools\bin\libSkiaSharp.dll
cs2mapbalance\tools\bin\spirv-cross.dll
```

Do not put them in the game folder or Steam directory. They are ignored by Git.
Alternatively, keep them together elsewhere and set `S2V_CLI` to the full
`Source2Viewer-CLI.exe` path, or set `s2v_cli` in
`config\paths.local.json`.

Verify:

```powershell
& ".\tools\bin\Source2Viewer-CLI.exe" --help
Get-FileHash ".\tools\bin\Source2Viewer-CLI.exe" -Algorithm SHA256
```

The intake panel should show `S2V ready` after restarting the app. Full install
and troubleshooting guide: **[SETUP.md](SETUP.md)**.

## 1. Variables

Set paths for your machine. These are examples, not personal defaults.

```powershell
$CS2  = "<CS2_GAME>"       # e.g. the Counter-Strike Global Offensive folder
$TEMP = "<TEMP>\cs2mb"     # a scratch directory
$MAP  = "de_mirage"        # change to your map
New-Item -ItemType Directory -Force $TEMP | Out-Null
```

Map VPK:

```text
$CS2\game\csgo\maps\<map>.vpk
```

## 2. Extract nav

From the project root:

```powershell
python tools\vpk_read.py "$CS2\game\csgo\maps\$MAP.vpk" `
  extract "maps/$MAP.nav" "$TEMP\$MAP.nav"
```

Result:

```text
<TEMP>\<map>.nav
```

## 3. Extract entity lump and physics model

```powershell
python tools\vpk_read.py "$CS2\game\csgo\maps\$MAP.vpk" `
  extract "maps/$MAP/entities/default_ents.vents_c" "$TEMP\default_ents.vents_c"

python tools\vpk_read.py "$CS2\game\csgo\maps\$MAP.vpk" `
  extract "maps/$MAP/world_physics.vmdl_c" "$TEMP\world_physics.vmdl_c"
```

## 4. Dump entities to text

`resourceinfo.exe` ships with CS2:

```powershell
& "$CS2\game\bin\win64\resourceinfo.exe" `
  -game "$CS2\game\csgo" `
  -i "$TEMP\default_ents.vents_c" -all `
  > "$TEMP\entities.txt"
```

PowerShell may write this file as UTF-16. The app accepts UTF-8,
UTF-8 BOM and UTF-16 LE/BE.

## 5. Export physics collision to glTF

Use the pinned Source2Viewer-CLI 20.1 or a compatible VRF release. It does not
need to be installed system-wide.

```powershell
& "<S2V>\Source2Viewer-CLI.exe" `
  -i "$TEMP\world_physics.vmdl_c" `
  -o "$TEMP\world_physics.gltf" `
  -d --gltf_export_format gltf `
  --gltf_export_materials `
  --game "$CS2\game\csgo\gameinfo.gi"
```

The exporter creates:

```text
<TEMP>\world_physics_physics.gltf
<TEMP>\world_physics_physics.bin
```

The `.bin` is required. Do not upload the `.gltf` alone.

If you use Source2Viewer GUI instead, export the same
`world_physics.vmdl_c` to **glTF Separate** (`.gltf` + `.bin`).

## 6. Files to drop into the app

```text
<TEMP>\<map>.nav
<TEMP>\entities.txt
<TEMP>\world_physics_physics.gltf
<TEMP>\world_physics_physics.bin
```

Open the app:

```powershell
python app\server.py --port 8765
```

Then <http://127.0.0.1:8765/>:

1. Set `Map name` to `<map>`.
2. Drag all four files into the drop zone.
3. Click `Generate map`.
4. Wait for the viewer and `Map library` row.

## 7. Common problems

### Missing `.bin`

The app rejects the job with:

```text
missing glTF buffer sidecar(s); upload .bin too
```

Export again with glTF Separate, or upload the `.bin` next to the `.gltf`.

### Empty route cards

Route cards need standard callouts:

```text
BombsiteA
BombsiteB
Middle
```

The nav/collision viewer can still be generated if a map uses different
callouts, but route cards may be empty.

### `resourceinfo` output is empty

Make sure you extracted `default_ents.vents_c`, not a different entity file.
Re-run with `-all` and redirect to a new text file.

### Map has no `world_physics.vmdl_c`

Check the extracted map VPK. Some non-standard/workshop maps may not contain
the same resource layout; the app will report a missing input instead of
guessing.

### Large files

Use the fallback path mode with files under `inputs/<map>/`, or upload
individually. The server limit is 300 MB per request and 160 MB per file.

## 8. Safety

- The app only reads the provided files.
- It does not launch CS2/Steam.
- It does not read game memory or interact with anti-cheat.
- Do not expose the local server to the internet.
- Do not commit extracted game resources to Git.
