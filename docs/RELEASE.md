# CS2 Map Balance v1.0.0-pre.1 — complete pre-release

**Application version:** `v1.0.0-pre.1`
**SRI version:** `1.0.0`
**Release type:** pre-release, Windows x64

This is the first complete CS2MB distribution. It contains the application, the
first-party **SRI — Source Resource Inspector**, a portable Python 3.13 runtime,
launchers, documentation, checksums and an SPDX SBOM.

## Source 2 processing

- Renamed the internal component to SRI — Source Resource Inspector.
- SRI decodes compiled PHYS and EntityLump resources in-process with the pinned
  MIT ValveResourceFormat `20.1.7467` library.
- Source2Viewer-CLI and `resourceinfo.exe` are no longer runtime dependencies.
- Coordinates remain in Hammer units and Source axes (`x`, `y`, `z-up`); the
  legacy glTF node matrix is not applied.
- Mesh and convex-hull geometry is exact; sphere/capsule primitives use bounded
  tessellation.
- `InteractAs`, `SurfaceProperty` and `CollisionGroup` metadata is preserved.
- SRI path, version and SHA-256 are recorded in preparation manifests.

## Application

- One complete Windows package with `Start-CS2MB.bat` and `Start-CS2MB.ps1`.
- Portable Python 3.13 runtime; no Python install or `pip` for packaged users.
- SRI detection and version reporting in the application.
- Existing NAV parsing, routing, collision, movement, simulation, viewer and
  library behaviour is preserved.
- Manual upload of `.nav`, entity `.txt`, `.gltf` and `.bin` remains available.

## Visual identity

- Restored the owner's original `logo.png` byte-for-byte as the canonical mark.
- Removed invented vector logo variants.
- Rebuilt banners, SRI/pipeline diagrams, navigation, collision and security
  illustrations with a restrained charcoal/crimson system.
- Rebuilt the 1280×640 social preview around the original logo.
- Reorganized assets into `brand/`, `banners/`, `illustrations/` and
  `screenshots/`.
- Captured actual current screenshots of the application, map viewer, map
  library and onboarding guide.

## Security

- Maximum two simultaneous jobs; excess requests return HTTP 429.
- Stale job records and upload directories are pruned.
- Windows timeout terminates the full process tree, including SRI.
- Loopback Host allow-list and same-origin POST checks; missing Origin rejected.
- Remote binding (`--allow-remote`) is rejected.
- Rejected uploads are removed.
- Preparation manifests omit personal absolute paths.
- Direct endpoint tests cover oversized uploads, malformed multipart data,
  traversal, extensions, missing sidecars, invalid JSON, viewer confinement,
  Host/Origin rejection and job limits.
- GitHub Actions pinned to immutable commit SHAs.
- Release includes `SHA256SUMS.txt` and `SBOM.spdx.json`.
- SRI is not code-signed; hashes are integrity checks, not a signature.

## Compatibility

- Windows 10/11 x64.
- Portable Python 3.13 included in the complete package.
- Local CS2 installation optional for automatic extraction.
- Validated against CS2 build `2000948` (2026-11-19).
- Upload mode works without CS2 or SRI.

## Known limitations

- SRI is Windows x64 only.
- Curved collision primitives are tessellated approximations.
- Full clearance validation was performed on Dust2 and Nuke; the other maps in
  the recorded batch used `Skip clearance`.
- Entity/PHYS support is tied to the recorded CS2 build; future Valve format
  changes may require an SRI update.
- The movement model remains straight-line calibrated and does not include
  combat, utility, visibility or player decisions.
- Viewer HTML generation is not a browser sandbox; remaining viewer-content
  and code-signing work is tracked in `docs/SECURITY_BACKLOG.md`.
- The route-time indicator is a preliminary heuristic, not a balance verdict.

## Verification

- 88 tests discovered / 87 executed / 1 real-map test gated by
  `CS2MB_TEST_GAME`.
- SRI Release build and engine-backed tests.
- Nine-map local integration validation.
- Python compilation, repository hygiene scan, Markdown links, SVG/XML and
  asset-reference checks.
- Package extraction, launcher, SRI detection and HTTP startup checks.
- Checksums re-calculated from the published archive.

## Historical release notes

Earlier 2.x notes remain under [releases/](releases/). The old standalone
`source2-v1.0.0` component release is retired after this complete release is
verified.
