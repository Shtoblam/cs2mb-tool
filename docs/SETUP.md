# Setup and troubleshooting

This guide installs the local CS2 Map Balance application on Windows and
explains how to produce a map with either the installed CS2 folder or uploaded
files.

The application is a local file analyzer. It does not launch CS2 or Steam, does
not read game memory, and does not interact with anti-cheat. Keep the local
server on `127.0.0.1`.

## 1. Requirements

- Windows 10/11 **x64**.
- **Python 3.13 x64** — the tested version. No `pip install` step is required.
- The project folder, or the source ZIP from `main`.
- CS2 installed if you want **Prepare + Generate from installed CS2**.
- **Source2Viewer-CLI 20.1** if you want automatic physics collision export.
  It is not needed when you already have a physics glTF + `.bin`.

No administrator rights, system-wide installation, or game-file changes are
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

The repository is public.

Option A — source ZIP:

1. Download <https://github.com/Shtoblam/cs2mb-tool/archive/refs/heads/main.zip>.
2. Extract it to a normal user folder, for example:
   `%USERPROFILE%\Documents\cs2mapbalance`.

Option B — Git clone:

```powershell
git clone https://github.com/Shtoblam/cs2mb-tool.git
cd cs2mapbalance
```

Do **not** extract the project inside the CS2/Steam installation directory.

Verify that the project root contains `app`, `tools`, `docs`, `config`, and
`README.md`:

```powershell
Get-ChildItem
```

## 4. Start the local app

From the project root:

```powershell
py -3.13 app\server.py --port 8765
```

Or, when `python` points to Python 3.13:

```powershell
python app\server.py --port 8765
```

Open <http://127.0.0.1:8765/>. The first-run tutorial opens automatically; the
**? Установка** button opens it again later. Press `Ctrl+C` in PowerShell to stop
the server.

If port 8765 is busy:

```powershell
py -3.13 app\server.py --port 8766
```

Then open `http://127.0.0.1:8766/`. Do not expose the server to the internet.

## 5. Generate a map

### Automatic mode (recommended)

1. Start the app with CS2 closed.
2. Set **CS2 game folder** to the CS2 installation root.
3. Set **Map name**, for example `de_mirage` or `de_dust2`.
4. Click **Prepare + Generate**.
5. Wait for the `viewer` link and the new `Map library` row.

The selected folder must contain:

```text
game\csgo\maps\<map>.vpk
game\csgo\gameinfo.gi
game\bin\win64\resourceinfo.exe
```

Find it in Steam: **Library → Counter-Strike 2 → Manage → Browse local files**.
The app rejects a folder that does not contain the CS2 data layout.

### File mode (no CS2 folder access)

1. Obtain the four files described in
   [Getting map files](GETTING_FILES.md).
2. Set **Map name**.
3. Drag the `.nav`, entity `.txt`, `.gltf` and `.bin` into the drop zone.
4. Click **Generate map**.

`Skip clearance` takes about 20 seconds on Dust2; a full clearance job takes
about 2.5 minutes on the recorded test machine. The viewer and library row appear
after the job.

## 6. Source2Viewer-CLI setup

Source2Viewer-CLI is a separate **MIT-licensed** tool from the
[ValveResourceFormat](https://github.com/ValveResourceFormat/ValveResourceFormat)
project. It is not bundled, not downloaded automatically, and not required for
the upload path.

It converts an already extracted `world_physics.vmdl_c` into:

```text
world_physics_physics.gltf
world_physics_physics.bin
```

The analyzer reads those files. Source2Viewer is not loaded into CS2 and is not
an anti-cheat or game-process tool.

### Download

Use the official release page:

<https://github.com/ValveResourceFormat/ValveResourceFormat/releases/tag/20.1>

Download the Windows x64 archive:

```text
cli-windows-x64.zip
```

Direct asset:
<https://github.com/ValveResourceFormat/ValveResourceFormat/releases/download/20.1/cli-windows-x64.zip>

Do **not** download `Source2Viewer.exe` for automatic mode; that is the GUI. Do
not use Linux/macOS assets on Windows. The archive contains:

```text
Source2Viewer-CLI.exe
libSkiaSharp.dll
spirv-cross.dll
```

Tested 20.1 artifacts (recorded 2026-10-20):

```text
cli-windows-x64.zip
SHA-256 67AAF8A67A85CA60FD09FF343E62103A4CDF3A2D177FC656231D7D734C5B3AA3

Source2Viewer-CLI.exe (extracted)
SHA-256 EF9F6FB3943C30B73F0991BCE6654128727B0807968F7997A6BB014EFBEC8830
```

These are hashes of the tested artifacts, not a promise about future releases.
Verify the download, and do not disable Windows Defender to run an unknown
binary.

### Where to put it for automatic mode

Extract **all three files** into the project’s `tools\bin` folder:

```text
cs2mapbalance\
  app\
  config\
  docs\
  tools\
    bin\
      Source2Viewer-CLI.exe
      libSkiaSharp.dll
      spirv-cross.dll
```

Exact executable path:

```text
<PROJECT>\tools\bin\Source2Viewer-CLI.exe
```

Do not put it in:

- `game\bin\win64` — do not modify the CS2 installation;
- the Steam folder;
- `C:\Windows`;
- a path you do not trust.

The executable and DLLs are ignored by Git and must not be committed.

### Alternative: keep the CLI outside the project

Resolution order:

- when calling `tools/prepare_map.py` manually: `--s2v-cli`, then the `S2V_CLI`
  environment variable, then `tools\bin\Source2Viewer-CLI.exe`;
- in the local app: `S2V_CLI` or the `s2v_cli` value from
  `config\paths.local.json`, then `tools\bin\Source2Viewer-CLI.exe`. The server
  passes the resolved path to `prepare_map.py` as `--s2v-cli`.

For a separate folder, keep all three files together and use:

```powershell
$env:S2V_CLI = "C:\Tools\Source2Viewer\Source2Viewer-CLI.exe"
py -3.13 app\server.py --port 8765
```

Or copy the template and edit the local config:

```powershell
Copy-Item config\paths.example.json config\paths.local.json
notepad config\paths.local.json
```

Example JSON (use double backslashes):

```json
{
  "cs2_game": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Counter-Strike Global Offensive",
  "s2v_cli": "C:\\Tools\\Source2Viewer\\Source2Viewer-CLI.exe"
}
```

`config/paths.local.json` is ignored by Git and is only a local convenience.

### Verify

```powershell
& ".\tools\bin\Source2Viewer-CLI.exe" --help
Get-FileHash ".\tools\bin\Source2Viewer-CLI.exe" -Algorithm SHA256
```

Restart the app and open <http://127.0.0.1:8765/>. The intake panel should show
**S2V ready**. If it shows **S2V not configured**:

- the file is named exactly `Source2Viewer-CLI.exe`;
- all three extracted files are in the same folder;
- the app was started from the project root;
- the app was restarted after changing the environment or config.

### If you do not want to use the CLI

Upload a glTF + `.bin` exported elsewhere, or use the Source2Viewer GUI
(`Source2Viewer.exe`) and export `world_physics.vmdl_c` as **glTF Separate**. The
upload mode only needs the four map files.

## 7. Troubleshooting

| Problem | Fix |
|---|---|
| `python` is not recognized / opens the Store | Use `py -3.13`; reinstall Python 3.13 with **Add python.exe to PATH**. |
| `ModuleNotFoundError` when starting | Run from the project root, not from `app\`; no `pip install` is needed. |
| `S2V not configured` | Put all three CLI files in `tools\bin`, or set `S2V_CLI` / `config\paths.local.json`; restart the app. |
| `libSkiaSharp.dll` missing | Extract the whole `cli-windows-x64.zip`, not only the exe. |
| `invalid CS2 game folder` | Select the CS2 install root containing `game\csgo\maps`, not the `maps` folder itself. |
| Map VPK not found | Install the map or use the upload path for workshop/non-standard maps. |
| Port already in use | Start with `--port 8766` and open the new URL. |
| VPK is locked | Close CS2 while running automatic extraction. |
| No collision in viewer | Upload both `.gltf` and `.bin`; the sidecar is required. |
| Empty route cards | The map needs standard `BombsiteA`, `BombsiteB` and `Middle` callouts; nav/collision can still render. |
| Windows Defender warns about the CLI | Do not disable Defender; verify the official source and SHA-256, or use upload mode. |

## 8. Stop and remove

Press `Ctrl+C` in PowerShell. The program does not install a service, driver,
registry entry, or anything into CS2. Delete the project folder to remove it;
delete `tools\bin` separately if you no longer need the CLI.

## 9. Related documentation

- [Getting map files](GETTING_FILES.md) — manual extraction commands and file formats.
- [Security](SECURITY.md) — threat model and controls.
- [Documentation index](README.md) — all project documents.
- [Troubleshooting in Russian](SETUP.ru.md).
