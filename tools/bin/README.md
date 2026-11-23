# SRI executable location

This directory is ignored by Git except for this README. It is populated when
the complete CS2MB package is built or installed locally.

## SRI — Source Resource Inspector

The packaged executable lives at:

```text
tools/bin/sri/cs2mb-sri.exe
```

SRI is the first-party Source 2 resource inspector used for PHYS and EntityLump
decoding. It is included in the complete CS2MB Windows package; users do not
download a separate converter.

Verify:

```powershell
& ".\tools\bin\sri\cs2mb-sri.exe" --version
python tools/sri.py --status
Get-FileHash ".\tools\bin\sri\cs2mb-sri.exe" -Algorithm SHA256
```

Expected version: `cs2mb-sri 1.0.0 (SRI — Source Resource Inspector)`.

No .NET runtime, Source2Viewer-CLI or `resourceinfo.exe` is required. Do not
place executables inside the CS2/Steam installation. Upload mode still accepts
`.nav`, entity `.txt`, `.gltf` and `.bin` without SRI.
