# CS2 Map Balance v1.1.1 — release notes

**Application version:** `v1.1.1`
**SRI version:** `1.0.0`
**3DsVW version:** `1.0.0`
**Release type:** patch release, Windows x64

v1.1.1 is a correctness, path-sanitization and build-maintenance patch. It adds
no new features and preserves existing data formats, coordinate contracts and
component versions.

## Pipeline and security

- SRI now reads `InteractAs` and `PhysicsTags` from their separate source fields.
- 3DsVW bundle replacement is transactional: a validated staging bundle is
  swapped into place, and failures preserve the last known-good viewer.
- `prepare_map.py --dry-run` is a real no-write preflight, including the
  application game-mode flow.
- Analysis manifests and summaries no longer expose absolute local paths,
  usernames or Python installation paths.
- glTF sidecar URI sanitization is host-independent. Windows drive and UNC paths
  are reduced to file names on POSIX; remote URLs and data URIs remain excluded.
  Existing sidecar traversal checks are unchanged.

## 3DsVW correctness

- Independent collision, NAV and aggregate scene bounds are stored. Fit, Top,
  Isometric and grid framing use scene bounds; camera padding remains
  presentation-only.
- Material identity, collision metadata, triangle counts and clip/sky state are
  tracked per primitive rather than per node.
- Parent/child TRS and explicit node matrices are composed exactly once for
  conservative world-space bounds. The contract is recorded in `bounds_mode`.
- Indexed and non-indexed triangle accounting, the default primitive mode,
  unsupported modes and malformed node/accessor references are validated with
  controlled errors.
- Duplicate node names retain distinct stable node identities.

## Build and CI

- SRI uses `System.Text.Json` source generation for `PhysSummary` and `GltfDto`,
  including nested types. Existing naming, null handling and the custom
  `Vector3JsonConverter` are preserved; the trimmed Release build has no IL2026
  warnings.
- The CI .NET setup action uses a Node.js 24 release.

## Compatibility

- Windows 10/11 x64.
- Portable Python 3.13 included; no separate installation.
- SRI and 3DsVW versions remain `1.0.0`.
- No new dependencies and no changes to PHYS coordinates, routing, movement or
  balance calculations.
- Existing viewer payloads remain readable; new bounds and primitive fields are
  additive.

## Verification

- Python suite: 132 tests discovered / 131 executed / 1 gated real-map test.
- Security scan, compile checks, JavaScript syntax checks and asset/reference
  checks passed.
- Dust2 PHYS regression preserved 435,649 collision triangles.
- Trimmed SRI Release build and both GitHub Actions jobs passed.

## Assets

- `CS2MB-v1.1.1-win-x64.zip`
- `SBOM.spdx.json`
- `SHA256SUMS.txt`
