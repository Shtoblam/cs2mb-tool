# SECURITY — pre-alpha v1.0

**Scope:** local `app/server.py`, auto-generation pipeline, user-provided files.

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
**2026-11-20**, and intake UI response-header hardening on **2026-11-23**. Scope: `app/server.py`, `app/index.html`,
`tools/prepare_map.py`, `tools/auto_generate.py`, the viewer generator and all
runtime Python modules.

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
- the only child processes are the local Python pipeline, Valve's read-only
  `resourceinfo.exe`, and the optional MIT Source2Viewer-CLI.

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
not require the folder at all. `resourceinfo.exe` is Valve's diagnostic tool;
Source2Viewer-CLI only converts an extracted vmdl to glTF.

### Source2Viewer-CLI

Source2Viewer is a separate MIT-licensed tool. It is not bundled or
auto-downloaded. The tested version was 20.1. It reads the extracted
`world_physics.vmdl_c` and writes glTF + `.bin`; it does not attach to CS2,
read process memory or communicate with VAC. Use a trusted pinned build and
verify its source/hash.

## Threat model

- arbitrary local file read via the path API;
- CSRF requests from a third-party website to localhost;
- filename/sidecar traversal;
- resource exhaustion from huge or malformed files;
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
- job timeout: 900 s;
- generated viewer: restrictive CSP response header
  (`default-src 'none'`, `connect-src 'none'`), `X-Frame-Options: SAMEORIGIN`,
  `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-origin`
  and `Cache-Control: no-store`;
- intake UI: restrictive CSP response header and matching `<meta>` policy,
  plus `Referrer-Policy: no-referrer` and a matching referrer meta element;
  served with `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Cross-Origin-Resource-Policy: same-origin` and `Cache-Control: no-store`;
- `.gitignore` excludes game resources, uploads and local path config;
- current tracked tree passes `tools/security_scan.py`.

## Repository / Git audit

- current tracked tree: no personal Windows paths, usernames, keys, tokens,
  `.env` files or game assets;
- `docs/assets/` contains only abstract SVG banners/diagrams and one UI
  tutorial screenshot; no map screenshots or game assets;
- `config/paths.local.json` and `tools/bin/*.exe` are ignored;
- two GitHub Actions workflows are tracked: `tests.yml` runs compilation, unit
  tests and the hygiene scan; `pages.yml` builds and publishes the static
  website from an explicit file list. No deployment secrets are tracked;
- GitHub release assets contain source/docs only;
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
- The intake UI sends its CSP as a response header and also includes a
  matching meta policy. `frame-ancestors` remains unavailable from meta tags,
  but the response header and `X-Frame-Options: DENY` enforce framing.
- Old commit objects may contain historical path examples. Current tracked tree
  is clean; history rewriting requires explicit approval.
- Automatic game preparation executes `resourceinfo.exe` from the selected
  CS2 folder. Point it only at a trusted game installation; do not use a
  directory controlled by an untrusted party.

## Check

```powershell
python -m unittest discover -s tests -v
python tools\security_scan.py
```

Russian version: [SECURITY.ru.md](SECURITY.ru.md).
