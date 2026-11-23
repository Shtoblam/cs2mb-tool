# SECURITY — pre-alpha v1.0

**Scope:** local `app/server.py`, auto-generation pipeline, `source2/` engine,
`tools/source2.py`, user-provided files.

## Security management update

Security work is tracked in [SECURITY_BACKLOG.md](SECURITY_BACKLOG.md). The first
baseline update adds CSP, referrer and cross-origin response headers to the
intake UI, with a matching regression test. No critical or high-severity
application finding is currently open; the remaining process, concurrency and
endpoint-testing work is tracked by priority.

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

Audit date: **2026-10-20**; later viewer/UI hardening was reviewed on
**2026-11-20**, intake UI response-header hardening on **2026-11-23**, and the
internal Source 2 engine on **2026-11-23**. Scope: `app/server.py`,
`app/index.html`, `tools/prepare_map.py`, `tools/source2.py`, `source2/`,
`tools/auto_generate.py`, the viewer generator and all runtime Python modules.

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
- the only child processes are the local Python pipeline and the first-party
  `cs2mb-source2` engine; no Valve diagnostic tool or Source2Viewer-CLI is
  launched at runtime.

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
decoded by the first-party `cs2mb-source2` engine, not by a Valve diagnostic
tool or a separately installed converter.

### Internal Source 2 engine

`cs2mb-source2` is built from `source2/` in this repository. It links the
MIT-licensed ValveResourceFormat 20.1.7467 library in-process for binary KV3,
Zstandard/LZ4, PHYS and EntityLump decoding. The executable is self-contained,
does not download updates, does not connect to the network and does not attach
to CS2. It reads the extracted resources and writes the requested glTF/entity
output paths supplied by the local pipeline.

The engine is a trusted local binary. Install it from the CS2MB release page,
verify its SHA-256 against `SHA256SUMS.txt`, and keep it outside the game
directory. `tools/prepare_map.py` records its path, version and SHA-256 in
`prepared_manifest.json`. A stale `CS2MB_SOURCE2` or `--source2` path fails
loudly instead of silently selecting another executable.

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

- loopback bind by default; non-loopback requires explicit `--allow-remote`;
- path API accepts only `inputs/` and `artifacts/uploads/`;
- POST origin guard rejects third-party origins;
- upload limits: 300 MB total, 12 files, 160 MB per file;
- extensions: `.nav`, `.txt`, `.gltf`, `.bin`;
- map names: `[A-Za-z0-9_-]{1,64}`;
- uploaded names are reduced to their basename;
- glTF sidecars must stay inside the glTF directory;
- subprocesses use argument lists, never `shell=True`;
- job timeout: 900 s; engine calls also have explicit timeouts;
- engine resolution is explicit path or `CS2MB_SOURCE2`, then packaged
  locations; a stale override fails instead of falling back;
- engine path, version and SHA-256 are recorded in the preparation manifest;
- compiled resources are treated as untrusted input; the engine reports
  controlled errors, validates bounds and tessellates curved primitives with
  bounded ring counts;
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
- `docs/assets/` contains only abstract SVG banners/diagrams and one UI
  tutorial screenshot; no map screenshots or game assets;
- `config/paths.local.json`, `tools/bin/*.exe` and `source2/dist/` are ignored;
- two GitHub Actions workflows are tracked: `tests.yml` runs Python checks, the
  engine build and engine-backed tests; `pages.yml` builds and publishes the
  static website from an explicit file list. No deployment secrets are tracked;
- GitHub release assets contain the self-contained engine zip, checksums,
  license and notices; the engine binary is not committed to Git;
- old commit objects may contain historical path examples from earlier
  research. Current `main` is clean; history rewriting was not performed
  without explicit approval. No secret keys were found in the history audit.

### Viewer response policy (2026-11-20)

Generated viewer HTML is served only from a resolved path under `artifacts/auto/` after the job ID is validated. The response now sets `default-src 'none'`, allows only the viewer's inline scripts/styles and local/data/blob images, blocks network connections and nested frames, and restricts framing to the same origin. `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-origin`, and `Cache-Control: no-store` are also set. The local UI may embed the viewer; opening it in a separate tab uses the same endpoint and policy.

## Residual risks

- Python nav/glTF/entity parsers are not a sandbox; do not process untrusted
  files without need.
- Upload bodies are read into memory up to 300 MB.
- The local server has no authentication; never expose it to the internet.
- The engine executable is a trusted local binary. Hashing detects accidental
  corruption or substitution but is not a code signature; download it only
  from the CS2MB release page.
- The engine links an upstream MIT library. A future library or CS2 format
  change may require an update; the current validation is tied to the recorded
  game build.
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
