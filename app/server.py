#!/usr/bin/env python3
"""Local auto-generation web app for CS2 Map Balance.

Run:
  python app/server.py --port 8765
Then open http://127.0.0.1:8765/

The app accepts browser upload/drop of extracted map files or prepares them
from an installed CS2 folder, then runs the local read-only analysis pipeline.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from simulation.balance import time_only_balance  # noqa: E402

APP_DIR = ROOT / "app"
JOBS_DIR = ROOT / "artifacts" / "auto"
UPLOADS_DIR = ROOT / "artifacts" / "uploads"
MAX_UPLOAD = 300 * 1024 * 1024
MAX_FILES = 12
MAX_FILE_SIZE = 160 * 1024 * 1024
JOB_TIMEOUT_SECONDS = 900
ALLOWED_INPUT_ROOTS = (ROOT / "inputs", UPLOADS_DIR)
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
MAP_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
JOB_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
ALLOWED_SUFFIXES = {".nav", ".txt", ".gltf", ".bin"}
LOCAL_PATHS = ROOT / "config" / "paths.local.json"
VIEWER_HEADERS = {
    "X-Frame-Options": "SAMEORIGIN",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'unsafe-inline'; "
        "style-src 'unsafe-inline'; img-src 'self' data: blob:; "
        "font-src 'self' data:; connect-src 'none'; frame-src 'none'; "
        "object-src 'none'; base-uri 'none'; form-action 'none'; "
        "frame-ancestors 'self'"
    ),
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}
UI_HEADERS = {
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "frame-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'self'"
    ),
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}


def parse_json_object(body: bytes) -> dict:
    """Decode a JSON request body and reject valid non-object JSON values."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid JSON body") from error
    if not isinstance(payload, dict):
        raise ValueError("JSON body must be an object")
    return payload


def load_local_paths() -> dict:
    if not LOCAL_PATHS.is_file():
        return {}
    try:
        data = json.loads(LOCAL_PATHS.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def allowed_input_path(path: Path) -> bool:
    """Only project input/upload roots are accepted by the path API."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return any(resolved.is_relative_to(root.resolve()) for root in ALLOWED_INPUT_ROOTS)


def append_log(job: dict, line: str) -> None:
    with JOBS_LOCK:
        job["log"].append(line.rstrip("\n"))
        if len(job["log"]) > 2000:
            del job["log"][:500]


def run_job(job_id: str, command: list[str], out_dir: Path) -> None:
    job = JOBS[job_id]
    with JOBS_LOCK:
        job["status"] = "running"
        job["started_utc"] = datetime.now(timezone.utc).isoformat()
    append_log(job, "$ " + " ".join(command))
    timed_out = threading.Event()
    process: subprocess.Popen[str] | None = None
    timer: threading.Timer | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        if process.stdout is None:
            raise RuntimeError("pipeline stdout is unavailable")

        def on_timeout() -> None:
            timed_out.set()
            process.kill()

        timer = threading.Timer(JOB_TIMEOUT_SECONDS, on_timeout)
        timer.daemon = True
        timer.start()
        for line in process.stdout:
            append_log(job, line)
        returncode = process.wait()
    except Exception as error:  # noqa: BLE001 - report to UI
        append_log(job, f"runner error: {error}")
        returncode = 1
    finally:
        if timer is not None:
            timer.cancel()
    if timed_out.is_set():
        append_log(job, f"job timed out after {JOB_TIMEOUT_SECONDS} s")
        returncode = -1

    viewer = out_dir / "viewer.html"
    manifest = out_dir / "manifest.json"
    with JOBS_LOCK:
        job["returncode"] = returncode
        job["finished_utc"] = datetime.now(timezone.utc).isoformat()
        job["manifest"] = str(manifest) if manifest.is_file() else None
        if returncode == 0 and viewer.is_file():
            job["status"] = "ok"
            job["viewer"] = str(viewer)
        elif returncode == 0:
            job["status"] = "dry-run"
        else:
            job["status"] = "failed"


class Handler(BaseHTTPRequestHandler):
    server_version = "CS2MapBalance/pre-alpha v1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _file(
        self,
        path: Path,
        content_type: str,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def _serve_app(self) -> None:
        self._file(
            APP_DIR / "index.html",
            "text/html; charset=utf-8",
            UI_HEADERS,
        )

    def _job_public(self, job_id: str) -> dict | None:
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job is None:
                return None
            return {
                "id": job_id,
                "status": job["status"],
                "map": job["map"],
                "log": job["log"][-160:],
                "viewer_url": f"/viewer/{job_id}" if job.get("viewer") else None,
                "manifest": job.get("manifest"),
                "returncode": job.get("returncode"),
            }

    def _discover(self, map_name: str) -> dict:
        if not MAP_RE.fullmatch(map_name):
            return {"ok": False, "error": "invalid map name"}
        directory = ROOT / "inputs" / map_name
        if not directory.is_dir():
            return {
                "ok": False,
                "error": f"input directory not found: {directory.relative_to(ROOT)}",
            }
        nav = sorted(directory.glob("*.nav"))
        entities = sorted(directory.glob("*.txt"))
        gltf = sorted(directory.glob("*.gltf"))
        return {
            "ok": True,
            "map": map_name,
            "nav": str(nav[0].relative_to(ROOT)) if nav else "",
            "entities": str(entities[0].relative_to(ROOT)) if entities else "",
            "collision_gltf": str(gltf[0].relative_to(ROOT)) if gltf else "",
            "directory": str(directory.relative_to(ROOT)),
        }

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        port = self.server.server_address[1]
        allowed = {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }
        if origin in allowed:
            return True
        self._json(HTTPStatus.FORBIDDEN, {"error": "cross-origin request rejected"})
        return False

    def _multipart(self) -> tuple[dict, list[tuple[str, str, bytes]]]:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.lower().startswith("multipart/form-data"):
            raise ValueError("expected multipart/form-data")
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_UPLOAD:
            raise ValueError("upload is empty or too large")
        body = self.rfile.read(length)
        raw = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()
            + body
        )
        message = BytesParser(policy=policy.default).parsebytes(raw)
        fields: dict[str, str] = {}
        files: list[tuple[str, str, bytes]] = []
        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition") or ""
            filename = part.get_filename()
            payload = part.get_payload(decode=True) or b""
            if filename:
                safe_name = Path(filename).name
                if safe_name:
                    files.append((name, safe_name, payload))
            else:
                fields[name] = payload.decode("utf-8", "replace").strip()
        if len(files) > MAX_FILES:
            raise ValueError(f"too many files (max {MAX_FILES})")
        for _field, filename, payload in files:
            if len(payload) > MAX_FILE_SIZE:
                raise ValueError(f"file too large: {filename}")
            if Path(filename).suffix.lower() not in ALLOWED_SUFFIXES:
                raise ValueError(f"unsupported file type: {filename}")
        return fields, files

    def _library(self) -> dict:
        rows = []
        for summary_path in JOBS_DIR.glob("*/*/summary.json"):
            try:
                data = json.loads(summary_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            job_id = summary_path.parent.name
            viewer = summary_path.parent / "viewer.html"
            floor = data.get("collision_floor") or {}
            wall = data.get("wall") or {}
            clearance = data.get("clearance") or {}
            routes = data.get("routes") or {}
            balance = data.get("balance")
            if not balance:
                verdict = time_only_balance(routes)
                balance = verdict.as_dict() if verdict else {}
            ct_a = (routes.get("CT") or {}).get("A") or {}
            t_a = (routes.get("T") or {}).get("A") or {}
            rows.append(
                {
                    "map": data.get("map"),
                    "job_id": job_id,
                    "generated_utc": data.get("generated_utc"),
                    "areas": (data.get("nav") or {}).get("area_count"),
                    "edges": (data.get("nav") or {}).get("edge_count"),
                    "floor_pct": floor.get("matched_pct"),
                    "wall_blocked": wall.get("blocked"),
                    "wall_tested": wall.get("tested"),
                    "low_ceiling": clearance.get("area_low_ceiling"),
                    "narrow": clearance.get("area_narrow"),
                    "ct_a_low": ct_a.get("time_low"),
                    "ct_a_high": ct_a.get("time_high"),
                    "t_a_low": t_a.get("time_low"),
                    "t_a_high": t_a.get("time_high"),
                    "balance_side": balance.get("side"),
                    "balance_verdict": balance.get("verdict"),
                    "balance_advantage_s": balance.get("ct_advantage_s"),
                    "balance_relative_pct": balance.get("relative_pct"),
                    "balance_targets": balance.get("targets", []),
                    "viewer_url": f"/viewer/{job_id}" if JOB_RE.fullmatch(job_id) and viewer.is_file() else None,
                }
            )
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            map_name = str(row.get("map") or "unknown")
            grouped.setdefault(map_name, []).append(row)
        latest_rows = []
        for versions in grouped.values():
            versions.sort(
                key=lambda row: row.get("generated_utc") or "", reverse=True
            )
            latest = versions[0]
            latest["versions"] = len(versions)
            latest_rows.append(latest)
        latest_rows.sort(
            key=lambda row: row.get("generated_utc") or "", reverse=True
        )
        return {"maps": latest_rows}

    def _start_job(
        self,
        map_name: str,
        inputs: dict[str, Path],
        dry_run: bool,
        skip_clearance: bool,
        uploads_dir: Path | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex[:12]
        out_dir = JOBS_DIR / map_name / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        job = {
            "id": job_id,
            "map": map_name,
            "status": "queued",
            "log": [],
            "out_dir": str(out_dir),
            "uploads": str(uploads_dir) if uploads_dir else None,
            "viewer": None,
            "manifest": None,
        }
        with JOBS_LOCK:
            JOBS[job_id] = job

        command = [
            sys.executable,
            "tools/auto_generate.py",
            "--map",
            map_name,
            "--nav",
            str(inputs["nav"]),
            "--entities",
            str(inputs["entities"]),
            "--collision-gltf",
            str(inputs["collision_gltf"]),
            "--out-dir",
            str(out_dir),
        ]
        if skip_clearance:
            command.append("--skip-clearance")
        if dry_run:
            command.append("--dry-run")
        thread = threading.Thread(
            target=run_job,
            args=(job_id, command, out_dir),
            daemon=True,
        )
        thread.start()
        return job_id

    @staticmethod
    def _missing_gltf_sidecars(path: Path) -> list[str]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ["<invalid glTF>"]
        missing = []
        for buffer in data.get("buffers", []):
            uri = buffer.get("uri")
            if not uri or uri.startswith("data:"):
                continue
            sidecar = (path.parent / uri).resolve()
            if not sidecar.is_relative_to(path.parent.resolve()):
                missing.append(f"{uri} (outside glTF directory)")
            elif not sidecar.is_file():
                missing.append(uri)
        return missing

    def _start_game_job(
        self,
        map_name: str,
        game: Path,
        s2v_cli: Path,
        dry_run: bool,
        skip_clearance: bool,
    ) -> str:
        job_id = uuid.uuid4().hex[:12]
        out_dir = JOBS_DIR / map_name / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        job = {
            "id": job_id,
            "map": map_name,
            "status": "queued",
            "log": [],
            "out_dir": str(out_dir),
            "viewer": None,
            "manifest": None,
        }
        with JOBS_LOCK:
            JOBS[job_id] = job
        command = [
            sys.executable,
            "tools/prepare_map.py",
            "--map",
            map_name,
            "--game",
            str(game),
            "--out-dir",
            str(out_dir),
            "--generate-out",
            str(out_dir),
            "--s2v-cli",
            str(s2v_cli),
        ]
        if skip_clearance:
            command.append("--skip-clearance")
        if dry_run:
            command.append("--dry-run")
        thread = threading.Thread(
            target=run_job,
            args=(job_id, command, out_dir),
            daemon=True,
        )
        thread.start()
        return job_id

    def _game_generate(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 2 * 1024 * 1024:
                raise ValueError("body is empty or too large")
            payload = parse_json_object(self.rfile.read(length))
        except (ValueError, UnicodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON body"})
            return

        map_name = str(payload.get("map", "")).strip()
        if not MAP_RE.fullmatch(map_name):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid map name"})
            return
        paths = load_local_paths()
        game_value = str(payload.get("game", "")).strip() or str(
            os.environ.get("CS2_GAME") or paths.get("cs2_game") or ""
        )
        if not game_value or "<" in game_value:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": "set CS2 game path in the form or config/paths.local.json"},
            )
            return
        game = Path(game_value).expanduser().resolve()
        required = (
            game / "game" / "csgo" / "maps",
            game / "game" / "csgo" / "gameinfo.gi",
            game / "game" / "bin" / "win64" / "resourceinfo.exe",
            game / "game" / "csgo" / "maps" / f"{map_name}.vpk",
        )
        if not all(path.exists() for path in required):
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid CS2 game folder or map name"},
            )
            return
        cli_value = str(
            os.environ.get("S2V_CLI") or paths.get("s2v_cli") or ""
        ).strip()
        if not cli_value:
            candidate = ROOT / "tools" / "bin" / "Source2Viewer-CLI.exe"
            cli_value = str(candidate) if candidate.is_file() else ""
        if not cli_value or "<" in cli_value:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": "Source2Viewer-CLI not configured; put it in tools/bin or set S2V_CLI"
                },
            )
            return
        cli = Path(cli_value).expanduser().resolve()
        if not cli.is_file():
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Source2Viewer-CLI not found"})
            return

        job_id = self._start_game_job(
            map_name,
            game,
            cli,
            dry_run=payload.get("dry_run") is True
            or str(payload.get("dry_run", "")).lower() == "true",
            skip_clearance=payload.get("skip_clearance") is True
            or str(payload.get("skip_clearance", "")).lower() == "true",
        )
        self._json(HTTPStatus.ACCEPTED, {"job_id": job_id, "status": "queued"})

    def _upload(self) -> None:
        try:
            fields, files = self._multipart()
        except ValueError as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return
        map_name = fields.get("map", "de_dust2").strip() or "de_dust2"
        if not MAP_RE.fullmatch(map_name):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid map name"})
            return
        if not files:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "no files uploaded"})
            return

        upload_id = uuid.uuid4().hex[:12]
        upload_dir = UPLOADS_DIR / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved: dict[str, Path] = {}
        for _field, filename, payload in files:
            target = upload_dir / Path(filename).name
            if target.exists() or target.is_symlink():
                target = upload_dir / f"{target.stem}_{uuid.uuid4().hex[:6]}{target.suffix}"
            target.write_bytes(payload)
            saved[filename] = target

        def first(suffix: str) -> Path | None:
            return next(
                (path for name, path in saved.items() if Path(name).suffix.lower() == suffix),
                None,
            )

        nav = first(".nav")
        gltf = first(".gltf")
        entity = first(".txt")
        if nav is None or gltf is None or entity is None:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": "need at least one .nav, one entity .txt and one .gltf",
                    "files": list(saved),
                },
            )
            return
        missing_sidecars = self._missing_gltf_sidecars(gltf)
        if missing_sidecars:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": "missing glTF buffer sidecar(s); upload .bin too",
                    "missing": missing_sidecars,
                },
            )
            return
        job_id = self._start_job(
            map_name,
            {"nav": nav, "entities": entity, "collision_gltf": gltf},
            dry_run=fields.get("dry_run", "").lower() == "true",
            skip_clearance=fields.get("skip_clearance", "").lower() == "true",
            uploads_dir=upload_dir,
        )
        self._json(
            HTTPStatus.ACCEPTED,
            {"job_id": job_id, "status": "queued", "upload_id": upload_id},
        )

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            self._serve_app()
            return
        if path == "/logo.png":
            self._file(ROOT / "logo.png", "image/png", {"Cache-Control": "no-store"})
            return
        if path == "/api/health":
            self._json(HTTPStatus.OK, {"ok": True, "service": "cs2mapbalance"})
            return
        if path == "/api/config":
            paths = load_local_paths()
            game = os.environ.get("CS2_GAME") or paths.get("cs2_game") or ""
            cli = os.environ.get("S2V_CLI") or paths.get("s2v_cli") or ""
            if not cli:
                candidate = ROOT / "tools" / "bin" / "Source2Viewer-CLI.exe"
                cli = str(candidate) if candidate.is_file() else ""
            self._json(
                HTTPStatus.OK,
                {
                    "cs2_game": game,
                    "s2v_cli": cli,
                    "s2v_ready": bool(cli and Path(cli).is_file()),
                },
            )
            return
        if path == "/api/discover":
            map_name = parse_qs(parsed.query).get("map", ["de_dust2"])[0]
            self._json(HTTPStatus.OK, self._discover(map_name))
            return
        if path == "/api/library":
            self._json(HTTPStatus.OK, self._library())
            return
        if path == "/api/jobs":
            with JOBS_LOCK:
                rows = [
                    {
                        "id": job_id,
                        "map": job["map"],
                        "status": job["status"],
                        "started_utc": job.get("started_utc"),
                    }
                    for job_id, job in JOBS.items()
                ]
            self._json(HTTPStatus.OK, {"jobs": rows})
            return
        if path.startswith("/api/jobs/"):
            job_id = path.rsplit("/", 1)[-1]
            job = self._job_public(job_id)
            if job is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "job not found"})
            else:
                self._json(HTTPStatus.OK, job)
            return
        if path.startswith("/viewer/"):
            job_id = path.rsplit("/", 1)[-1]
            if not JOB_RE.fullmatch(job_id):
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            with JOBS_LOCK:
                job = JOBS.get(job_id)
                viewer = job.get("viewer") if job else None
            if not viewer:
                persisted = list(JOBS_DIR.glob(f"*/{job_id}/viewer.html"))
                if len(persisted) == 1:
                    viewer = str(persisted[0])
            if not viewer:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            viewer_path = Path(viewer).resolve()
            if not viewer_path.is_relative_to(JOBS_DIR.resolve()):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            self._file(viewer_path, "text/html; charset=utf-8", VIEWER_HEADERS)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if not self._origin_ok():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/api/upload":
            self._upload()
            return
        if parsed.path == "/api/generate_from_game":
            self._game_generate()
            return
        if parsed.path != "/api/generate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "empty JSON body"})
                return
            if length > 2 * 1024 * 1024:
                self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "body too large"})
                return
            payload = parse_json_object(self.rfile.read(length))
        except (ValueError, UnicodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid JSON body"})
            return

        map_name = str(payload.get("map", "")).strip()
        if not MAP_RE.fullmatch(map_name):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid map name"})
            return
        inputs = {}
        for key in ("nav", "entities", "collision_gltf"):
            value = str(payload.get(key, "")).strip()
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = ROOT / path
            path = path.resolve()
            if not path.is_file():
                self._json(HTTPStatus.BAD_REQUEST, {"error": f"missing input {key}: {value}"})
                return
            if not allowed_input_path(path):
                self._json(
                    HTTPStatus.FORBIDDEN,
                    {
                        "error": "path mode accepts only inputs/ or artifacts/uploads/",
                        "path": str(path),
                    },
                )
                return
            inputs[key] = path

        missing_sidecars = self._missing_gltf_sidecars(inputs["collision_gltf"])
        if missing_sidecars:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": "missing glTF buffer sidecar(s); upload .bin too",
                    "missing": missing_sidecars,
                },
            )
            return

        job_id = self._start_job(
            map_name,
            inputs,
            dry_run=payload.get("dry_run") is True
            or str(payload.get("dry_run", "")).lower() == "true",
            skip_clearance=payload.get("skip_clearance") is True
            or str(payload.get("skip_clearance", "")).lower() == "true",
        )
        self._json(HTTPStatus.ACCEPTED, {"job_id": job_id, "status": "queued"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="allow binding to a non-loopback interface (not recommended)",
    )
    args = parser.parse_args()
    loopback = {"127.0.0.1", "localhost", "::1"}
    if args.host not in loopback and not args.allow_remote:
        print(
            "refusing non-loopback host without --allow-remote; "
            "the app has no authentication",
            file=sys.stderr,
        )
        return 2
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"CS2 Map Balance auto-generation app: http://{args.host}:{args.port}/")
    print(f"Inputs: {ROOT / 'inputs'} (map subdirectories)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
