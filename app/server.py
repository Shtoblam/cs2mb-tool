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
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from simulation.balance import time_only_balance  # noqa: E402
from sri import (  # noqa: E402
    SriError,
    resolve_sri,
    status as sri_status,
)

APP_DIR = ROOT / "app"
JOBS_DIR = ROOT / "artifacts" / "auto"
UPLOADS_DIR = ROOT / "artifacts" / "uploads"
MAX_UPLOAD = 300 * 1024 * 1024
MAX_FILES = 12
MAX_FILE_SIZE = 160 * 1024 * 1024
JOB_TIMEOUT_SECONDS = 900
MAX_ACTIVE_JOBS = 2
MAX_JOB_RECORDS = 100
JOB_RETENTION_SECONDS = 6 * 60 * 60
UPLOAD_RETENTION_SECONDS = 24 * 60 * 60
ACTIVE_JOB_STATUSES = {"queued", "running"}
ALLOWED_INPUT_ROOTS = (ROOT / "inputs", UPLOADS_DIR)
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
MAP_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
JOB_RE = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
ALLOWED_SUFFIXES = {".nav", ".txt", ".gltf", ".bin"}
VIEWER3D_ASSETS = ROOT / "viewer3d" / "assets"
DOCS_DIR = ROOT / "docs"
VIEWER3D_SUFFIXES = {
    ".html",
    ".js",
    ".css",
    ".json",
    ".gltf",
    ".bin",
    ".png",
    ".svg",
    ".txt",
    ".woff2",
}
VIEWER3D_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".gltf": "model/gltf+json",
    ".bin": "application/octet-stream",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".txt": "text/plain; charset=utf-8",
    ".woff2": "font/woff2",
}
LOCAL_PATHS = ROOT / "config" / "paths.local.json"


class JobLimitError(RuntimeError):
    """Raised when the configured simultaneous-job limit is reached."""


def _timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def prune_jobs_locked() -> None:
    """Drop expired finished jobs and cap retained in-memory records."""
    now = datetime.now(timezone.utc)
    finished: list[tuple[datetime, str]] = []
    for job_id, job in list(JOBS.items()):
        if job.get("status") in ACTIVE_JOB_STATUSES:
            continue
        stamp = _timestamp(job.get("finished_utc") or job.get("started_utc"))
        if stamp is None:
            continue
        if now - stamp > timedelta(seconds=JOB_RETENTION_SECONDS):
            JOBS.pop(job_id, None)
        else:
            finished.append((stamp, job_id))
    if len(JOBS) > MAX_JOB_RECORDS:
        for _stamp, job_id in sorted(finished)[: len(JOBS) - MAX_JOB_RECORDS]:
            JOBS.pop(job_id, None)


def prune_jobs() -> None:
    with JOBS_LOCK:
        prune_jobs_locked()


def prune_uploads() -> None:
    """Remove old upload directories, but never an active job's uploads."""
    if not UPLOADS_DIR.is_dir():
        return
    active: set[Path] = set()
    with JOBS_LOCK:
        for job in JOBS.values():
            if job.get("status") in ACTIVE_JOB_STATUSES and job.get("uploads"):
                try:
                    active.add(Path(job["uploads"]).resolve())
                except OSError:
                    continue
    cutoff = time.time() - UPLOAD_RETENTION_SECONDS
    for directory in UPLOADS_DIR.iterdir():
        if not directory.is_dir() or directory.is_symlink():
            continue
        try:
            if directory.resolve() in active or directory.stat().st_mtime >= cutoff:
                continue
            shutil.rmtree(directory, ignore_errors=True)
        except OSError:
            continue


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Terminate a pipeline process and its descendants where supported."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (OSError, ProcessLookupError):
            try:
                process.kill()
            except OSError:
                pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass


def stop_active_jobs() -> None:
    """Terminate every active pipeline before the server exits."""
    with JOBS_LOCK:
        processes = [
            job.get("process")
            for job in JOBS.values()
            if job.get("status") in ACTIVE_JOB_STATUSES
        ]
    for process in processes:
        if process is not None:
            terminate_process_tree(process)


def register_job(job: dict) -> None:
    """Reserve a job slot or raise JobLimitError."""
    with JOBS_LOCK:
        prune_jobs_locked()
        active = sum(
            1 for existing in JOBS.values()
            if existing.get("status") in ACTIVE_JOB_STATUSES
        )
        if active >= MAX_ACTIVE_JOBS:
            raise JobLimitError(
                f"too many active jobs (max {MAX_ACTIVE_JOBS}); wait for one to finish"
            )
        JOBS[job["id"]] = job
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
VIEWER3D_HEADERS = {
    "X-Frame-Options": "SAMEORIGIN",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; connect-src 'self'; font-src 'self'; "
        "worker-src 'self' blob:; object-src 'none'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'self'"
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
        spawn_kwargs: dict = {}
        if os.name == "nt":
            spawn_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            spawn_kwargs["start_new_session"] = True
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **spawn_kwargs,
        )
        with JOBS_LOCK:
            job["process"] = process
        if process.stdout is None:
            raise RuntimeError("pipeline stdout is unavailable")

        def on_timeout() -> None:
            timed_out.set()
            terminate_process_tree(process)

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
        with JOBS_LOCK:
            job.pop("process", None)
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
    server_version = "CS2MapBalance/v1.1.0"

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
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

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
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def _serve_app(self) -> None:
        self._file(
            APP_DIR / "index.html",
            "text/html; charset=utf-8",
            UI_HEADERS,
        )

    def _viewer3d_url(self, map_name: str, job_id: str, out_dir: Path) -> str | None:
        if not MAP_RE.fullmatch(map_name) or not JOB_RE.fullmatch(job_id):
            return None
        data = out_dir / "viewer3d" / "data.json"
        return f"/viewer3d/{map_name}/{job_id}/" if data.is_file() else None

    def _job_public(self, job_id: str) -> dict | None:
        with JOBS_LOCK:
            job = JOBS.get(job_id)
            if job is None:
                return None
            out_dir = Path(job["out_dir"])
            viewer3d = self._viewer3d_url(job["map"], job_id, out_dir)
            manifest = job.get("manifest")
            if manifest:
                try:
                    manifest = str(Path(manifest).relative_to(ROOT))
                except ValueError:
                    manifest = Path(manifest).name
            return {
                "id": job_id,
                "status": job["status"],
                "map": job["map"],
                "log": job["log"][-160:],
                "viewer_url": f"/viewer/{job_id}" if job.get("viewer") else None,
                "viewer3d_url": viewer3d,
                "manifest": manifest,
                "returncode": job.get("returncode"),
            }

    def _serve_docs(self, path: str) -> None:
        tail = unquote(path[len("/docs/") :]) if path.startswith("/docs/") else ""
        if (
            not tail
            or "/" in tail
            or "\\" in tail
            or ".." in tail
            or "\x00" in tail
            or not tail.endswith(".md")
            or Path(tail).name != tail
        ):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        name = tail
        target = (DOCS_DIR / name).resolve()
        if not target.is_relative_to(DOCS_DIR.resolve()) or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._file(
            target,
            "text/plain; charset=utf-8",
            {
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "Cache-Control": "no-store",
            },
        )

    def _serve_viewer3d(self, path: str) -> None:
        """Serve fixed viewer assets or a confined generated map bundle."""
        decoded = unquote(path)
        if "\x00" in decoded or "\\" in decoded:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        parts = [part for part in decoded.split("/") if part]
        if not parts or parts[0] != "viewer3d" or len(parts) < 2:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if parts[1] == "assets":
            relative = parts[2:] or ["index.html"]
            root = VIEWER3D_ASSETS.resolve()
            target = root.joinpath(*relative).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            suffix = target.suffix.lower()
            if suffix not in VIEWER3D_SUFFIXES:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._file(target, VIEWER3D_TYPES[suffix], VIEWER3D_HEADERS)
            return

        map_name, job_id = parts[1], parts[2] if len(parts) > 2 else ""
        if not MAP_RE.fullmatch(map_name) or not JOB_RE.fullmatch(job_id):
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if len(parts) == 3 and not decoded.endswith("/"):
            self.send_response(HTTPStatus.PERMANENT_REDIRECT)
            self.send_header("Location", decoded + "/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        relative = parts[3:] or ["index.html"]
        root = (JOBS_DIR / map_name / job_id / "viewer3d").resolve()
        if not root.is_relative_to(JOBS_DIR.resolve()):
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if relative == ["index.html"]:
            target = (VIEWER3D_ASSETS / "index.html").resolve()
        else:
            target = root.joinpath(*relative).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        suffix = target.suffix.lower()
        if suffix not in VIEWER3D_SUFFIXES:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._file(target, VIEWER3D_TYPES[suffix], VIEWER3D_HEADERS)

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

    def _host_ok(self) -> bool:
        """Reject requests whose Host does not identify this loopback server."""
        host = self.headers.get("Host", "").strip().lower()
        port = self.server.server_address[1]
        allowed = {
            f"127.0.0.1:{port}",
            f"localhost:{port}",
            "127.0.0.1",
            "localhost",
        }
        if self.server.server_address[0] in {"::1", "::"}:
            allowed.add(f"[::1]:{port}")
            allowed.add("[::1]")
        if host in allowed:
            return True
        self._json(HTTPStatus.FORBIDDEN, {"error": "invalid Host header"})
        return False

    def _origin_ok(self) -> bool:
        """Require a same-origin browser request for state-changing POSTs."""
        sec_fetch_site = self.headers.get("Sec-Fetch-Site")
        if sec_fetch_site and sec_fetch_site not in {"same-origin", "none"}:
            self._json(HTTPStatus.FORBIDDEN, {"error": "cross-site request rejected"})
            return False
        origin = self.headers.get("Origin")
        if not origin:
            self._json(HTTPStatus.FORBIDDEN, {"error": "missing Origin header"})
            return False
        port = self.server.server_address[1]
        allowed = {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }
        if self.server.server_address[0] in {"::1", "::"}:
            allowed.add(f"http://[::1]:{port}")
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
                    "viewer3d_url": self._viewer3d_url(
                        str(data.get("map") or ""),
                        job_id,
                        summary_path.parent,
                    ),
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
        try:
            register_job(job)
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            with JOBS_LOCK:
                JOBS.pop(job_id, None)
            shutil.rmtree(out_dir, ignore_errors=True)
            raise

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
        sri: Path,
        dry_run: bool,
        skip_clearance: bool,
    ) -> str:
        job_id = uuid.uuid4().hex[:12]
        out_dir = JOBS_DIR / map_name / job_id
        job = {
            "id": job_id,
            "map": map_name,
            "status": "queued",
            "log": [],
            "out_dir": str(out_dir),
            "viewer": None,
            "manifest": None,
        }
        try:
            register_job(job)
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            with JOBS_LOCK:
                JOBS.pop(job_id, None)
            shutil.rmtree(out_dir, ignore_errors=True)
            raise
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
            "--sri",
            str(sri),
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
            game / "game" / "csgo" / "maps" / f"{map_name}.vpk",
        )
        if not all(path.exists() for path in required):
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid CS2 game folder or map name"},
            )
            return
        try:
            converter = resolve_sri()
        except SriError as error:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": str(error)},
            )
            return

        try:
            job_id = self._start_game_job(
                map_name,
                game,
                converter,
                dry_run=payload.get("dry_run") is True
                or str(payload.get("dry_run", "")).lower() == "true",
                skip_clearance=payload.get("skip_clearance") is True
                or str(payload.get("skip_clearance", "")).lower() == "true",
            )
        except JobLimitError as error:
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": str(error)})
            return
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
        prune_uploads()
        upload_dir = UPLOADS_DIR / upload_id
        upload_dir.mkdir(parents=True, exist_ok=True)

        def fail(status: int, payload: dict) -> None:
            shutil.rmtree(upload_dir, ignore_errors=True)
            self._json(status, payload)

        saved: dict[str, Path] = {}
        try:
            for _field, filename, payload in files:
                target = upload_dir / Path(filename).name
                if target.exists() or target.is_symlink():
                    target = upload_dir / f"{target.stem}_{uuid.uuid4().hex[:6]}{target.suffix}"
                target.write_bytes(payload)
                saved[filename] = target
        except OSError as error:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": f"could not store uploaded file: {error}"},
            )
            shutil.rmtree(upload_dir, ignore_errors=True)
            return

        def first(suffix: str) -> Path | None:
            return next(
                (path for name, path in saved.items() if Path(name).suffix.lower() == suffix),
                None,
            )

        nav = first(".nav")
        gltf = first(".gltf")
        entity = first(".txt")
        if nav is None or gltf is None or entity is None:
            fail(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": "need at least one .nav, one entity .txt and one .gltf",
                    "files": list(saved),
                },
            )
            return
        missing_sidecars = self._missing_gltf_sidecars(gltf)
        if missing_sidecars:
            fail(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": "missing glTF buffer sidecar(s); upload .bin too",
                    "missing": missing_sidecars,
                },
            )
            return
        try:
            job_id = self._start_job(
                map_name,
                {"nav": nav, "entities": entity, "collision_gltf": gltf},
                dry_run=fields.get("dry_run", "").lower() == "true",
                skip_clearance=fields.get("skip_clearance", "").lower() == "true",
                uploads_dir=upload_dir,
            )
        except JobLimitError as error:
            fail(HTTPStatus.TOO_MANY_REQUESTS, {"error": str(error)})
            return
        self._json(
            HTTPStatus.ACCEPTED,
            {"job_id": job_id, "status": "queued", "upload_id": upload_id},
        )

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_ok():
            return
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
            engine = sri_status()
            sri_display = engine.path
            if sri_display:
                try:
                    sri_display = str(Path(sri_display).relative_to(ROOT))
                except ValueError:
                    sri_display = Path(sri_display).name
            self._json(
                HTTPStatus.OK,
                {
                    "cs2_game": game,
                    "sri": sri_display,
                    "sri_ready": engine.ready,
                    "sri_version": engine.version,
                    "sri_sha256": engine.sha256,
                    "viewer3d": "1.0.0",
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
        if path.startswith("/docs/"):
            self._serve_docs(path)
            return
        if path.startswith("/viewer3d/"):
            self._serve_viewer3d(path)
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
        if not self._host_ok():
            return
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

        try:
            job_id = self._start_job(
                map_name,
                inputs,
                dry_run=payload.get("dry_run") is True
                or str(payload.get("dry_run", "")).lower() == "true",
                skip_clearance=payload.get("skip_clearance") is True
                or str(payload.get("skip_clearance", "")).lower() == "true",
            )
        except JobLimitError as error:
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": str(error)})
            return
        self._json(HTTPStatus.ACCEPTED, {"job_id": job_id, "status": "queued"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    loopback = {"127.0.0.1", "localhost", "::1"}
    if args.allow_remote or args.host not in loopback:
        print(
            "remote binding is disabled: the local application has no "
            "authentication. Use a loopback bind and an SSH tunnel if remote "
            "access is required.",
            file=sys.stderr,
        )
        return 2
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    prune_uploads()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"CS2 Map Balance auto-generation app: http://{args.host}:{args.port}/")
    print(f"Inputs: {ROOT / 'inputs'} (map subdirectories)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        stop_active_jobs()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
