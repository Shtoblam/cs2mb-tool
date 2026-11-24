# SECURITY — v1.1.0

**Scope:** local `app/server.py`, auto-generation pipeline, SRI (`sri/`),
`tools/sri.py`, user-provided files.

**Patch note:** application `v1.1.1` adds host-independent glTF sidecar
URI sanitization for Windows drive/UNC paths on POSIX. It does not weaken
the traversal, size or endpoint controls recorded below.

## Security management update

This `v1.1.0` audit closes the first security-management backlog cycle:

- bounded simultaneous jobs (maximum two) with controlled `429` rejection;
- stale job records, upload directories and active process trees are cleaned up;
- Windows timeout now terminates the full process tree, including SRI;
- direct endpoint tests cover Host, Origin, oversized uploads, malformed
  multipart data, traversal, extensions, missing sidecars, invalid JSON and
  viewer confinement;
- `--allow-remote` is rejected; the server is loopback-only;
- upload failures remove their temporary directory;
- preparation manifests use `<CS2_GAME>` and `prepared/...` instead of personal
  absolute paths.

No critical or high-severity application finding is currently open. Remaining
residual risks are listed below and in `SECURITY_BACKLOG.md`.

## What it does NOT do

- does not launch CS2 or Steam;
- does not read game memory or interact with anti-cheat;
- does not connect to game servers;
- does not execute uploaded code;
- does not send telemetry or files to external services;
- does not write to the game directory;
- does not require administrator/root.

The app does not contain a mechanism that by itself would trigger an
anti-cheat ban. Game resources are only read by explicit extraction commands.
Normal Valve rules still apply: do not use third-party software to interfere
with matches.

## VAC / anti-cheat audit

Audit date: **2026-11-24**. Scope: `app/server.py`, `app/index.html`,
`tools/prepare_map.py`, `tools/sri.py`, `sri/`, `tools/auto_generate.py`, the
viewer generator, the release packaging scripts, both GitHub Actions workflows
and all runtime Python modules. The previous audit dates `2026-10-20` and
`2026-11-20` remain in the historical record.

Result: **no VAC-relevant interaction found**. This is a static code and
dependency review, not a security certification or a guarantee about Valve's
future policy.

- no reference to `cs2.exe`, `steam.exe`, process enumeration or process attach;
- no `OpenProcess`, `ReadProcessMemory`, `WriteProcessMemory`,
  `CreateRemoteThread`, `VirtualAllocEx`, DLL injection or hooking;
- no overlay, input automation, console command or match interaction;
- no connection to Steam, game servers, VAC or an external API;
- no game-memory access and no write into the game directory;
- no administrator/root requirement;
- the only child processes are the local Python pipeline and SRI; no Valve
  diagnostic tool or Source2Viewer-CLI is launched at runtime.

The app can be used with CS2 completely closed. The generated viewer is
self-contained HTML and does not load external JavaScript, CSS or tracking
pixels. The local HTTP server is loopback-only by default.

**No absolute guarantee:** Valve can change policies in the future. The
statement above is about this code and the listed runtime dependencies, not a
promise about all third-party files a user may place in `tools/bin/`.

### Why the CS2 folder is needed

Only the optional **Prepare + Generate** mode reads the game folder. It opens
the map VPK and extracted `nav`, entity lump and `world_physics.vmdl_c`
read-only, then writes copies/results under `artifacts/`. Upload/drop mode does
not require the folder at all. The compiled entity and PHYS resources are
decoded by SRI, not by a Valve diagnostic tool or a separately installed
converter.

### SRI — Source Resource Inspector

SRI is built from `sri/` in this repository. It links the MIT-licensed
ValveResourceFormat 20.1.7467 library in-process for binary KV3,
Zstandard/LZ4, PHYS and EntityLump decoding. The executable is self-contained,
does not download updates, does not connect to the network and does not attach
to CS2. It reads the extracted resources and writes the requested glTF/entity
output paths supplied by the local pipeline.

SRI is a trusted local binary included in the complete CS2MB package. Verify its
SHA-256 against `SHA256SUMS.txt` and keep it outside the game directory.
`tools/prepare_map.py` records its path, version and SHA-256 in
`prepared_manifest.json`. A stale `CS2MB_SRI` or `--sri` path fails loudly
instead of silently selecting another executable.

### Removed external runtime tools

Source2Viewer-CLI and `resourceinfo.exe` are not resolved, launched or required
by the application. Setup instructions for them were removed from the normal
workflow. The legacy upload mode still accepts prepared `.gltf`/`.bin` and
entity text files from any source the user chooses.

## Threat model

- arbitrary local file read via the path API;
- CSRF requests from a third-party website to localhost;
- filename/sidecar traversal;
- resource exhaustion from huge or malformed compiled resources;
- memory-safety or bounds errors while decoding untrusted PHYS/EntityLump data;
- substitution of a malicious local engine executable;
- command injection through paths or names;
- accidental publication of personal paths or secrets.

## Controls

- loopback bind only; `--allow-remote` and non-loopback hosts are rejected;
- Host allow-list and same-origin POST checks (`Origin` plus
  `Sec-Fetch-Site`); direct POSTs without `Origin` are rejected;
- path API accepts only `inputs/` and `artifacts/uploads/`;
- upload limits: 300 MB total, 12 files, 160 MB per file;
- extensions: `.nav`, `.txt`, `.gltf`, `.bin`;
- map names: `[A-Za-z0-9_-]{1,64}`;
- uploaded names are reduced to their basename;
- rejected upload directories are removed; old uploads and job records are
  pruned;
- glTF sidecars must stay inside the glTF directory;
- subprocesses use argument lists, never `shell=True`;
- maximum two simultaneous jobs; excess requests receive `429`;
- job timeout: 900 s; Windows process-tree termination includes SRI;
- SRI resolution is explicit path or `CS2MB_SRI`, then packaged locations; a
  stale override fails instead of falling back;
- SRI path, version and SHA-256 are recorded in the preparation manifest;
- analysis manifests use `<INPUT>/...`, bundle-relative outputs and `<PYTHON>`;
- preparation and analysis manifests omit personal absolute paths,
  usernames and Python installation paths;
- compiled resources are treated as untrusted input; SRI reports controlled
  errors, validates bounds and tessellates curved primitives with bounded ring
  counts;
- generated viewer: restrictive CSP response header
  (`default-src 'none'`, `connect-src 'none'`), `X-Frame-Options: SAMEORIGIN`,
  `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-origin`
  and `Cache-Control: no-store`;
- intake UI: restrictive CSP response header and matching `<meta>` policy,
  plus `Referrer-Policy: no-referrer` and a matching referrer meta element;
  served with `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Cross-Origin-Resource-Policy: same-origin` and `Cache-Control: no-store`;
- `.gitignore` excludes game resources, uploads, local path config and engine
  build output;
- current tracked tree passes `tools/security_scan.py`.

## Repository / Git audit

- current tracked tree: no personal Windows paths, usernames, keys, tokens,
  `.env` files or game assets;
- `docs/assets/` contains the original logo, original SVG diagrams and actual
  current application/site screenshots; no extracted map assets;
- `config/paths.local.json`, `tools/bin/*.exe` and `sri/dist/` are ignored;
- two GitHub Actions workflows are tracked: `tests.yml` runs Python checks, the
  SRI build and SRI-backed tests; `pages.yml` builds and publishes the static
  website from an explicit file list. Actions are pinned to immutable commit
  SHAs;
- the complete CS2MB release contains SRI, the portable Python runtime,
  checksums, SBOM and notices; the binary is not committed to Git;
- old commit objects may contain historical path examples from earlier
  research. Current `main` is clean; history rewriting was not performed
  without explicit approval. No secret keys were found in the history audit.

### Viewer response policy (2026-11-20)

Generated viewer HTML is served only from a resolved path under `artifacts/auto/` after the job ID is validated. The response now sets `default-src 'none'`, allows only the viewer's inline scripts/styles and local/data/blob images, blocks network connections and nested frames, and restricts framing to the same origin. `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-origin`, and `Cache-Control: no-store` are also set. The local UI may embed the viewer; opening it in a separate tab uses the same endpoint and policy.

## 3DsVW viewer audit (2026-11-24)

3DsVW adds a second generated-data viewer and new server routes. Reviewed:

- `/viewer3d/<map>/<job>/` and `/viewer3d/assets/` only; map and job IDs use the
  same strict regex as the existing job API.
- Resolved paths must remain under the fixed viewer asset root or the job's
  `viewer3d/` directory. Percent-encoded traversal, backslashes, NULs, missing
  files and arbitrary suffixes return 404.
- The generic viewer page is served from the fixed asset root; job directories
  cannot replace it.
- `viewer3d/build.py` normalizes the glTF: fills `bufferViews[].buffer`, rejects
  external or missing sidecars, rejects mismatched buffer length, strips
  images/textures/animations/skins and caps glTF, sidecar, nodes/accessors and
  collision triangles.
- The viewer CSP is `default-src 'none'; script-src 'self'; connect-src 'self'`;
  no inline scripts or remote origins are allowed.
- Object/NAV/entity metadata is inserted with `textContent`/DOM nodes. The viewer
  does not use `innerHTML` for generated data.
- `postMessage` settings are accepted only from the same origin.
- Endpoint tests cover traversal, invalid IDs, missing bundles, CSP, asset
  content type and confined paths.
- Builder tests cover synthetic NAV/glTF, texture scrubbing and external buffer
  rejection.

3DsVW remains a local read-only viewer. It does not execute uploaded code or
fetch remote assets. A malicious local process that can rewrite generated files
is outside this threat model.

## Residual risks

- Python nav/glTF/entity parsers are not a sandbox; do not process untrusted
  files without need.
- Upload bodies are read into memory up to 300 MB.
- The local server has no authentication; remote binding is disabled, but never
  expose the loopback server through an unsafe proxy.
- SRI is a trusted local binary. Hashing detects accidental corruption or
  substitution but is not a code signature; verify the SHA-256 from the release.
- SRI links an upstream MIT library. A future library or CS2 format change may
  require an update; the current validation is tied to the recorded game build.
- The intake UI sends its CSP as a response header and also includes a
  matching meta policy. `frame-ancestors` remains unavailable from meta tags,
  but the response header and `X-Frame-Options: DENY` enforce framing.
- Old commit objects may contain historical path examples. Current tracked tree
  is clean; history rewriting requires explicit approval.
- Automatic game preparation reads the selected CS2 folder. Point it only at a
  trusted game installation; do not use a directory controlled by an untrusted
  party.

## Check

```powershell
python -m unittest discover -s tests -v
python tools\security_scan.py
```

Russian version: [SECURITY.ru.md](SECURITY.ru.md).
