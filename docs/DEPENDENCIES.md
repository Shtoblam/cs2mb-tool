# Dependencies and licenses

**Status:** current for `v1.1.0`.

SRI is built against the pinned NuGet packages below. 3DsVW uses the locally
vendored three.js runtime. The table is
derived from `sri/Cs2mb.Sri/packages.lock.json`; exact versions are resolved by
the lockfile. The complete Windows package also includes the official Python
3.13.3 embeddable runtime.

| Package | Version | Scope | License |
|---|---:|---|---|
| Blake3 | 3.0.2 | transitive | MIT |
| K4os.Compression.LZ4 | 1.3.8 | transitive | MIT |
| KeyValues2 | 0.8.0 | transitive | MIT |
| SharpGLTF.Core | 1.0.6 | transitive | MIT |
| SharpGLTF.Runtime | 1.0.6 | transitive | see package notice |
| SharpGLTF.Toolkit | 1.0.6 | transitive | MIT |
| SkiaSharp | 4.151.1 | transitive | MIT |
| SkiaSharp.NativeAssets.Linux.NoDependencies | 4.151.1 | transitive | see package notice |
| SkiaSharp.NativeAssets.Win32 | 4.151.1 | transitive | see package notice |
| SkiaSharp.NativeAssets.macOS | 4.151.1 | transitive | see package notice |
| System.IO.Hashing | 10.0.10 | transitive | MIT |
| TinyBCSharp | 0.1.2 | transitive | MIT |
| TinyEXR.NET | 1.1.0 | transitive | MIT |
| ValveKeyValue | 0.70.0.499 | transitive | MIT |
| ValvePak | 5.0.2.177 | transitive | MIT |
| ValveResourceFormat | 20.1.7467 | direct | MIT |
| Vortice.SPIRV | 1.0.5 | transitive | MIT |
| Vortice.SpirvCross | 1.5.4 | transitive | MIT |
| ZstdSharp.Port | 0.8.8 | transitive | MIT |

## Python runtime

| Component | Version | Scope | License |
|---|---:|---|---|
| Python embeddable runtime | 3.13.3 | packaged runtime | PSF-2.0 |

Official source:
<https://www.python.org/ftp/python/3.13.3/python-3.13.3-embed-amd64.zip>
SHA-256: `59ff76e16e6597de47474fb22be69e7191a89116910d728ab735079b078e52db`

## 3DsVW runtime

| Component | Version | Scope | License |
|---|---:|---|---|
| three.js module + addons | 0.160.0 | 3DsVW runtime | MIT |

three.js `0.160.0` is vendored under `viewer3d/assets/vendor/`. The files are
served locally; only module import paths were adjusted. The upstream license is
included at `viewer3d/assets/vendor/LICENSE-three.txt`. The npm package archive
SHA-256 used during preparation was
`1ee2f935c4f555814b388e87b5ef78a44856bd2e9d0feb88643a6e193fb42856`.

## Audit notes

- `dotnet list sri/Cs2mb.Sri/Cs2mb.Sri.csproj package --include-transitive --vulnerable`
  reported no vulnerable packages from the configured NuGet source on
  2026-11-23.
- This is a point-in-time advisory check, not a guarantee about future
  advisories.
- GitHub Actions in `.github/workflows/` are pinned to immutable commit SHAs.
- ValveResourceFormat is an MIT-licensed community project, not a Valve
  product or an official CS2 SDK.
- Third-party license notices are shipped in `sri/THIRD_PARTY_NOTICES.md`
  and the complete package `THIRD_PARTY_NOTICES.md`.
- The release includes `SBOM.spdx.json`.
