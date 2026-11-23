# Setup and troubleshooting

This guide installs CS2 Map Balance `v1.1.0` on Windows and explains how
to produce a map from the installed CS2 folder or from uploaded files.

The application is a local, read-only file analyzer. It does not launch CS2 or
Steam, read game memory, or interact with anti-cheat. The server binds
`127.0.0.1`; remote binding is disabled.

## 1. Requirements

- Windows 10/11 **x64**.
- The complete CS2MB package
  `CS2MB-v1.1.0-win-x64.zip`.
- A WebGL2 browser for 3DsVW (current Chrome, Edge or Firefox).
- CS2 installed for **Prepare + Generate from installed CS2**.
- No separate Python install, `pip install`, .NET runtime, Source2Viewer-CLI or
  `resourceinfo.exe` is required for the packaged build.

The package includes a portable Python 3.13 runtime and **SRI — Source Resource
Inspector** at `tools/bin/sri/cs2mb-sri.exe`.

## 2. Install and start

1. Download the complete package from
   <https://github.com/Shtoblam/cs2mb-tool/releases/tag/v1.1.0>.
2. Verify the archive against `SHA256SUMS.txt`.
3. Extract it to a normal user folder, for example
   `%USERPROFILE%\Documents\CS2MB`.
4. Run `Start-CS2MB.bat` (or `Start-CS2MB.ps1`).
5. Open <http://127.0.0.1:8765/> if the browser does not open automatically.

Do not extract the package inside the CS2/Steam installation directory.

The launcher uses `runtime\python.exe` from the package, verifies that SRI is
present, starts the local server and opens the local URL. No administrator
rights or registry changes are needed.

## 3. Source checkout (developers)

Normal users should use the complete package. For a source checkout:

```powershell
git clone https://github.com/Shtoblam/cs2mb-tool.git
cd cs2mb-tool
py -3.13 tools\sri.py --status
py -3.13 app\server.py --port 8765
```

Source checkout requirements:

- Python 3.13 x64;
- SRI installed at `tools/bin/sri/cs2mb-sri.exe`, or `CS2MB_SRI` set to the
  executable.

Build SRI from source only when developing it:

```powershell
sri\build.ps1
```

Building requires the .NET SDK 10.0.x; normal execution does not.

## 4. SRI — Source Resource Inspector

SRI is the first-party CS2MB component that reads compiled Source 2 resources.
It is not a universal Source 2 viewer, editor or a renamed third-party CLI.

- `world_physics.vmdl_c` → PHYS → glTF + `.bin`;
- `default_ents.vents_c` → EntityLump → entity text;
- positions stay in Hammer units and Source axes (`x`, `y`, `z-up`);
- `InteractAs`, `SurfaceProperty` and `CollisionGroup` are preserved;
- sphere/capsule primitives are tessellated with bounded ring counts;
- the existing collision loader and analysis modules are unchanged.

Verify the packaged component:

```powershell
& ".\tools\bin\sri\cs2mb-sri.exe" --version
py -3.13 tools\sri.py --status
Get-FileHash ".\tools\bin\sri\cs2mb-sri.exe" -Algorithm SHA256
```

Expected: `cs2mb-sri 1.0.0 (SRI — Source Resource Inspector)` and
`"ready": true`. The application badge shows **SRI ready** with the version.

Override locations, in priority order:

- `CS2MB_SRI` environment variable;
- `tools\bin\sri\cs2mb-sri.exe`;
- `tools\bin\cs2mb-sri.exe`;
- `sri\bin\win-x64\cs2mb-sri.exe`;
- `--sri <path>` for a manual `tools/prepare_map.py` run.

An explicit path or `CS2MB_SRI` is authoritative: a stale value fails instead
of silently falling back.

## 4.1 3DsVW — 3D Source Map Viewer

3DsVW is embedded in the package at `viewer3d/`; its three.js runtime is bundled
under `viewer3d/assets/vendor/`. It requires WebGL2 and needs no network access.

After a job completes, open **Viewer** in the application. You can:

- view 3DsVW embedded in the application;
- open it in a separate tab;
- switch to the existing 2D viewer;
- toggle collision, floor, wall, clip, NAV, entity, site-label and route layers;
- use Fit, Top, Iso and Reset camera actions;
- click geometry, NAV or an entity to inspect available metadata.

The viewer displays SRI PHYS collision geometry, not render-world geometry,
materials or textures. See [USER_GUIDE.md](USER_GUIDE.md) for controls and
limitations.

## 5. Generate a map

### Automatic mode (recommended)

1. Start the app with CS2 closed.
2. Set **CS2 game folder** to the CS2 installation root.
3. Set **Map name**, for example `de_mirage` or `de_dust2`.
4. Click **Prepare + Generate**.
5. Wait for the viewer link and the new Map library row.

The selected folder must contain:

```text
game\csgo\maps\<map>.vpk
game\csgo\gameinfo.gi
```

Find it in Steam: **Library → Counter-Strike 2 → Manage → Browse local files**.
The game is read-only; extracted resources and generated output go to
`artifacts/`.

### File mode (no CS2 folder access)

1. Obtain the four files described in
   [Getting map files](GETTING_FILES.md).
2. Set **Map name**.
3. Drag the `.nav`, entity `.txt`, `.gltf` and `.bin` into the drop zone.
4. Click **Generate map**.

`Skip clearance` takes about 20 seconds on Dust2; a full clearance job takes
about 2.5 minutes on the recorded test machine.

## 6. Security controls

- loopback-only server; `--allow-remote` is rejected;
- Host and Origin checks on the local HTTP surface;
- upload limits: 300 MB total, 12 files, 160 MB per file;
- allowed suffixes: `.nav`, `.txt`, `.gltf`, `.bin`;
- path mode restricted to `inputs/` and `artifacts/uploads/`;
- maximum two simultaneous jobs;
- 900 s job timeout with Windows process-tree termination;
- stale job records and old upload directories are pruned;
- no telemetry, external uploads, game-process access or anti-cheat interaction;
- SRI is a trusted local binary; verify its SHA-256.

The preparation manifest stores provenance without personal absolute paths:
`<CS2_GAME>` and `prepared/...` are used instead of the local username or home
directory.

## 7. Troubleshooting

| Symptom | Action |
|---|---|
| `SRI not installed` | Verify `tools\bin\sri\cs2mb-sri.exe` exists; run `Start-CS2MB.ps1` from the package root. |
| `SRI failed` | Check `artifacts/.../prepared/sri.log`; verify the resource belongs to a supported CS2 build. |
| Launcher cannot find Python | Use the complete package, or install Python 3.13 x64 for a source checkout. |
| `invalid CS2 folder` | Select the CS2 root containing `game\csgo\maps`, not the `maps` folder. |
| Port busy | Start with a different port: `py -3.13 app\server.py --port 8766`. |
| `no .bin` | Upload/export `.gltf` and `.bin` together. |
| `too many active jobs` | Wait for a running job to finish; the limit is two. |
| `missing Origin header` | Use the local web UI; direct non-browser POSTs are rejected. |

## 8. Limits

- SRI is Windows x64 only.
- Curved collision primitives are tessellated approximations.
- Entity and PHYS support is validated against the recorded CS2 build; a future
  Valve format change may require an SRI update.
- The movement model remains straight-line calibrated and does not include
  combat, utility, visibility or player decisions.
- Full clearance was exercised on Dust2 and Nuke; other maps in the recorded
  batch used `Skip clearance`.

See [SECURITY.md](SECURITY.md), [VALIDATION.md](VALIDATION.md) and
[STATE.md](STATE.md) for the current evidence and residual limitations.
