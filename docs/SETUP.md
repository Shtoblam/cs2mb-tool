# Setup and troubleshooting

This guide installs the local CS2 Map Balance application on Windows and
explains how to produce a map from the installed CS2 folder or from uploaded
files.

The application is a local, read-only file analyzer. It does not launch CS2 or
Steam, does not read game memory, and does not interact with anti-cheat. Keep
the local server on `127.0.0.1`.

## 1. Requirements

- Windows 10/11 **x64**.
- **Python 3.13 x64** — the tested version. No `pip install` step is required.
- The project folder, or the source ZIP from `main`.
- CS2 installed for **Prepare + Generate from installed CS2**.
- The **cs2mb-source2** engine asset for automatic PHYS and EntityLump
  decoding. It is a first-party, self-contained CS2MB component. No .NET
  runtime, Source2Viewer-CLI or `resourceinfo.exe` is required.

No administrator rights, system-wide installation or game-file changes are
needed.

## 2. Install Python 3.13

1. Open <https://www.python.org/downloads/windows/>.
2. Download the **Windows installer (64-bit)** for Python 3.13.
3. Tick **Add python.exe to PATH**, then choose **Install Now**.
4. Open a **new** PowerShell window and verify:

```powershell
py -3.13 --version
python --version
```

If `python` opens the Microsoft Store or is not found, use `py -3.13` in every
command below, or reinstall Python with the PATH option enabled.

## 3. Get the project

The repository is public: <https://github.com/Shtoblam/cs2mb-tool>.

Option A — source ZIP:

1. Download <https://github.com/Shtoblam/cs2mb-tool/archive/refs/heads/main.zip>.
2. Extract it to a normal user folder, for example:
   `%USERPROFILE%\Documents\cs2mb-tool`.

Option B — Git clone:

```powershell
git clone https://github.com/Shtoblam/cs2mb-tool.git
cd cs2mb-tool
```

Do **not** extract the project inside the CS2/Steam installation directory.

## 4. Install the internal Source 2 engine

Automatic map intake uses `cs2mb-source2.exe`, built from `source2/` in this
repository. It links the MIT-licensed ValveResourceFormat library in-process and
does not wrap or launch a third-party CLI.

1. Open the CS2MB release page:
   <https://github.com/Shtoblam/cs2mb-tool/releases/tag/source2-v1.0.0>.
2. Download `cs2mb-source2-win-x64.zip`.
3. Verify the archive against `SHA256SUMS.txt` from the same release.
4. Extract `cs2mb-source2.exe` to:

```text
<PROJECT>\tools\bin\source2\cs2mb-source2.exe
```

5. Verify the installation from the project root:

```powershell
& ".\tools\bin\source2\cs2mb-source2.exe" --version
py -3.13 tools\source2.py --status
Get-FileHash ".\tools\bin\source2\cs2mb-source2.exe" -Algorithm SHA256
```

Expected status: `"ready": true` and a `cs2mb-source2 1.0.0` version. The
executable is ignored by Git. Do not put it in the CS2/Steam installation,
`C:\Windows`, or a path you do not trust.

The engine is self-contained. The .NET runtime, Source2Viewer-CLI,
`resourceinfo.exe` and the `S2V_CLI` configuration are not used. Optional
override locations:

- `CS2MB_SOURCE2` environment variable;
- `tools\bin\cs2mb-source2.exe`;
- `source2\bin\win-x64\cs2mb-source2.exe`;
- `--source2 <path>` for a manual `tools/prepare_map.py` run.

An explicit path or `CS2MB_SOURCE2` is authoritative: a stale value fails
instead of silently falling back to another executable.

### Build the engine from source (optional)

Normal users do not need this step. Building requires the .NET SDK 10.0.x; the
published executable does not require the SDK or runtime.

```powershell
source2\build.ps1
source2\build.ps1 -Install   # copies to tools\bin\source2\
```

The build is pinned by `source2/global.json`, the package version in
`source2/Cs2mb.Source2/Cs2mb.Source2.csproj` and `packages.lock.json`. See
`source2/README.md` and `source2/THIRD_PARTY_NOTICES.md` for the library
provenance and license notices.

## 5. Start the local app

From the project root:

```powershell
py -3.13 app\server.py --port 8765
```

Open <http://127.0.0.1:8765/>. The first-run tutorial opens automatically; the
tutorial button opens it again later. Press `Ctrl+C` in PowerShell to stop the
server.

If port 8765 is busy:

```powershell
py -3.13 app\server.py --port 8766
```

Then open `http://127.0.0.1:8766/`. Do not expose the server to the internet.

## 6. Generate a map

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
The app rejects a folder that does not contain the CS2 data layout. The game is
read-only; extracted resources and generated output go to `artifacts/`.

The state badge shows `engine ready` and the component version. `engine not
installed` means the executable is missing or the path is wrong.

### File mode (no CS2 folder access)

1. Obtain the four files described in
   [Getting map files](GETTING_FILES.md).
2. Set **Map name**.
3. Drag the `.nav`, entity `.txt`, `.gltf` and `.bin` into the drop zone.
4. Click **Generate map**.

`Skip clearance` takes about 20 seconds on Dust2; a full clearance job takes
about 2.5 minutes on the recorded test machine. The viewer and library row
appear after the job.

## 7. What the internal engine does

```text
map VPK (read-only)
   ├─ <map>.nav                  → existing Python NAV parser
   ├─ default_ents.vents_c       → cs2mb-source2 entities → entity dump
   └─ world_physics.vmdl_c       → cs2mb-source2 phys     → glTF + .bin
```

- `cs2mb-source2 entities` decodes the compiled EntityLump and writes the
  line-oriented dump consumed by the existing parser. It preserves class names,
  origins, angles, target names, callouts and other entity properties.
- `cs2mb-source2 phys` decodes the PHYS block, emits collision triangles grouped
  by collision attribute and surface property, and preserves `InteractAs`
  metadata. Positions remain in Hammer units and Source axes (`x`, `y`,
  `z-up`); the legacy glTF node matrix is not applied.
- The existing collision loader, movement model, routing and balance logic are
  unchanged.

The converter does not use render geometry as a substitute for physics
geometry. It reads `world_physics.vmdl_c`.

## 8. Troubleshooting

| Symptom | Action |
|---|---|
| `python not found` | Use `py -3.13`; reinstall Python with PATH. |
| `engine not installed` | Extract `cs2mb-source2.exe` to `tools\bin\source2\`; restart the server. |
| `cs2mb-source2 failed` | Check `artifacts/.../prepared/source2.log`; verify the file is a CS2 resource from the supported build. |
| Large collision output | Maps with many triangles (for example Inferno) produce a larger `.bin` and take longer; this is expected. |
| `invalid CS2 folder` | Select the CS2 root containing `game\csgo\maps`, not the `maps` folder. |
| Port busy | Use `--port 8766` and open the new URL. |
| `no .bin` | Upload/export `.gltf` and `.bin` together. |

## 9. Security and limits

- Loopback-only server by default; do not expose it to a LAN or the internet.
- Upload limits, path allow-listing, Origin checks, job timeouts and response
  security headers remain in force.
- No telemetry, external uploads, game-process access, injection or anti-cheat
  interaction.
- The engine executable is a local trusted component. Verify its SHA-256 from
  the release. It processes untrusted binary resources and reports controlled
  errors.
- The current converter emits mesh and convex-hull collision directly and
  tessellates sphere/capsule primitives with bounded ring counts. Curved
  surfaces are approximations for analysis, not exact analytic collision.
- Entity and physics support is validated against the installed CS2 build
  recorded in [STATE.md](STATE.md); a future Valve format change may require an
  engine update.

The engine is independently implemented for CS2MB. ValveResourceFormat is an
MIT-licensed upstream library, not a Valve product or an official CS2 SDK.
