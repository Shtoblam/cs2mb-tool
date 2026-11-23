# Optional local executables

This directory is ignored by Git except for this README.

## Internal Source 2 engine

Automatic map intake uses the first-party `cs2mb-source2.exe` component. Install
the Windows x64 asset from the CS2MB release page into:

```text
tools/bin/source2/cs2mb-source2.exe
```

The executable is self-contained: it does not require the .NET runtime,
Source2Viewer-CLI, resourceinfo or a separately installed Valve utility. It is
built from `source2/` in this repository against the pinned MIT
ValveResourceFormat library.

Verify the installation:

```powershell
& ".\tools\bin\source2\cs2mb-source2.exe" --version
python tools/source2.py --status
Get-FileHash ".\tools\bin\source2\cs2mb-source2.exe" -Algorithm SHA256
```

Compare the hash with `SHA256SUMS.txt` from the same release. Alternative
locations are `tools/bin/cs2mb-source2.exe` and
`source2/bin/win-x64/cs2mb-source2.exe`; `CS2MB_SOURCE2` overrides both.

Do not place executables inside the CS2/Steam installation. Without the
engine, manual upload of `.nav`, entity `.txt`, `.gltf` and `.bin` still works.
