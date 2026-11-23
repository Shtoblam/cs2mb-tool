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

1. Install the complete CS2MB package; SRI is included at `tools/bin/sri/`.
2. Start the app with `Start-CS2MB.bat`.
3. Enter `CS2 game folder` and the map name.
4. Click **Prepare + Generate**.

The app runs the same extraction steps internally. The manual path below is a
fallback and for debugging.

## SRI setup

The complete CS2MB package already contains SRI at:

```text
CS2MB\tools\bin\sri\cs2mb-sri.exe
```

No separate download, .NET runtime, Source2Viewer-CLI or `resourceinfo.exe` is
required. For a source checkout, verify:

```powershell
& ".\tools\bin\sri\cs2mb-sri.exe" --version
Get-FileHash ".\tools\bin\sri\cs2mb-sri.exe" -Algorithm SHA256
```

The intake panel should show `SRI ready` after restarting the app. Full install
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

Use the internal engine; it decodes the compiled EntityLump directly:

```powershell
& ".\tools\bin\sri\cs2mb-sri.exe" entities `
  --input "$TEMP\default_ents.vents_c" `
  --output "$TEMP\entities.txt"
```

The output is UTF-8 and uses the same `key = value` contract as the former
diagnostic dump. The app also accepts UTF-8 BOM and UTF-16 LE/BE.

## 5. Export physics collision to glTF

Use the internal engine; it reads `world_physics.vmdl_c` and writes the glTF
plus `.bin` sidecar expected by the collision loader:

```powershell
& ".\tools\bin\sri\cs2mb-sri.exe" phys `
  --input "$TEMP\world_physics.vmdl_c" `
  --output "$TEMP\world_physics_physics.gltf"
```

The exporter creates:

```text
<TEMP>\world_physics_physics.gltf
<TEMP>\world_physics_physics.bin
```

Positions remain in Hammer units and Source axes. The `.bin` is required. Do not
upload the `.gltf` alone.

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

### `entities.txt` is empty

Make sure you extracted `default_ents.vents_c`, not a different entity file.
Re-run `cs2mb-sri entities` and check the printed entity count.

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
