# CS2 Map Balance v1.1.0 — release notes

**Application version:** `v1.1.0`
**SRI version:** `1.0.0`
**3DsVW version:** `1.0.0`
**Release type:** normal release, Windows x64

This release turns CS2MB into a complete desktop-oriented analysis workspace and
adds **3DsVW — 3D Source Map Viewer**, a read-only spatial view built from the
data the existing pipeline already produces.

## Application UI

- New workspace navigation: Overview, Process, Library, Viewer, Settings.
- Rectangular panels, compact typography and a cool cyan/blue technical accent.
- Local SVG icons only; no emoji and no icon CDN.
- Repeated tutorial-style text removed from the workflow; contextual help and a
  dedicated user guide remain.
- Recent maps, document shortcuts and clear status reporting on the overview.

## 3DsVW

- Browser-based WebGL2 viewer with locally bundled three.js `0.160.0`.
- Renders collision geometry from SRI PHYS, NAV polygons/links, entity markers
  and representative routes.
- Floors, walls, other collision surfaces and clip/sky volumes are separated.
- Orbit, pan, zoom, fit, top, isometric and reset camera actions.
- Independent collision/NAV/entity/route layers.
- Object inspector exposes only available metadata: node, category, surface,
  collision group, `InteractAs`, material, hit point, NAV area or entity fields.
- Embedded in the application and available in a separate tab; both use the
  same implementation.
- No CDN, no external textures, no runtime downloads.
- On-demand rendering, frustum culling and grouped draw calls.

## Settings

- Default viewer mode: 3DsVW or 2D.
- 3D quality: Performance, Balanced, Quality (pixel ratio).
- Default 3DsVW layers, including clips/sky and NAV links.
- Remember-viewer toggle and reset to defaults.
- Preferences persist locally and apply to embedded and separate-tab viewers.

## Documentation

- New English and Russian user guides.
- Setup, SRI, 2D viewer, 3DsVW, settings, troubleshooting, privacy and
  limitations are documented against the current application.
- Current screenshots replace the v1.0 application screenshots.
- Website, README files, social preview and Pages workflow updated.

## Security and performance

- Viewers accept only generated bundles under confined map/job paths.
- Invalid map/job identifiers, traversal paths and missing files return 404.
- glTF is normalized before serving: `bufferViews[].buffer` filled, textures and
  images stripped, external buffer URIs rejected.
- Viewer input is bounded by glTF size, sidecar size, node/accessor count and
  four million collision triangles.
- Viewer CSP is `script-src 'self'`, `connect-src 'self'`,
  `frame-ancestors 'self'`; the application can embed it, external origins cannot.
- Generated metadata is inserted with safe DOM text APIs, not unsafe HTML.
- Existing loopback-only binding, Host/Origin checks, upload limits, job limits
  and process-tree timeouts are preserved.
- 3DsVW renders on demand and pauses when the document is hidden.

## Measured local data

| Map | Collision triangles | NAV areas | Draw calls | Viewer data |
|---|---:|---:|---:|---:|
| de_dust2 | 435,649 | 2,242 | 164 | ~407 KB + glTF/bin |
| de_anubis | 715,842 | 2,633 | 141 | ~480 KB + glTF/bin |

Draw calls are from the reference desktop run in Edge. They are not a universal
benchmark. The SRI collision glTF remains the large file; 3DsVW normalizes and
copies it into the job bundle.

## Verification

- Python suite, security scan, compileall, JavaScript syntax, SVG XML and asset
  reference checks.
- 3DsVW builder tests with synthetic NAV/glTF and external-buffer rejection.
- Viewer endpoint tests for traversal, invalid IDs, missing bundles, CSP and
  confined paths.
- Dust2 and Anubis automatic preparation and upload-mode generation.
- Embedded and separate-tab viewer loading with real generated data.
- Package extraction, SRI detection, launcher, docs access and checksum checks.

## Compatibility and limits

- Windows 10/11 x64.
- Portable Python 3.13 included; no separate install.
- WebGL2 browser required for 3DsVW.
- SRI is Windows x64 only and is not code-signed.
- 3DsVW is a collision-derived technical view, not game render geometry,
  materials or textures.
- No map editing, box selection or measurement tools.
- Curved collision primitives are tessellated approximations.
- Route time is an estimate, not match balance.
- Validation is tied to the recorded CS2 build; future Valve format changes may
  require an SRI update.

## Historical notes

The v1.0.0-pre.1 complete package, SRI rename and the earlier validation record
remain in [releases/](releases/) and the changelog.
