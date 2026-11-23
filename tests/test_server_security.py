"""Security-focused tests for the local auto-generation server."""

from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest import mock
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app.server as server_module  # noqa: E402
from app.server import (  # noqa: E402
    ALLOWED_INPUT_ROOTS,
    ALLOWED_SUFFIXES,
    JOB_RE,
    MAP_RE,
    MAX_UPLOAD,
    Handler,
    UI_HEADERS,
    VIEWER_HEADERS,
    allowed_input_path,
    parse_json_object,
    prune_jobs,
    run_job,
    prune_uploads,
    terminate_process_tree,
)


@contextmanager
def live_server():
    """Run the real handler against isolated artifact/upload directories."""
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        jobs = base / "auto"
        uploads = base / "uploads"
        inputs = base / "inputs"
        for path in (jobs, uploads, inputs):
            path.mkdir(parents=True, exist_ok=True)
        with mock.patch.multiple(
            server_module,
            JOBS_DIR=jobs,
            UPLOADS_DIR=uploads,
            ALLOWED_INPUT_ROOTS=(inputs, uploads),
        ):
            with server_module.JOBS_LOCK:
                server_module.JOBS.clear()
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                yield server.server_port, inputs, uploads
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)
                with server_module.JOBS_LOCK:
                    server_module.JOBS.clear()


def request(
    port: int,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    base_headers = {"Host": f"127.0.0.1:{port}"}
    if headers:
        base_headers.update(headers)
    connection.request(method, path, body=body, headers=base_headers)
    response = connection.getresponse()
    payload = response.read()
    connection.close()
    return response.status, payload


def json_request(
    port: int,
    path: str,
    payload: dict | list,
    *,
    origin: bool = True,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    extra = {"Content-Type": "application/json"}
    if origin:
        extra["Origin"] = f"http://127.0.0.1:{port}"
        extra["Sec-Fetch-Site"] = "same-origin"
    if headers:
        extra.update(headers)
    status, body = request(port, "POST", path, json.dumps(payload).encode(), extra)
    return status, json.loads(body.decode("utf-8"))


def multipart_body(files: list[tuple[str, bytes]], map_name: str = "de_dust2") -> tuple[bytes, str]:
    boundary = "----cs2mb-test-boundary"
    chunks = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"map\"\r\n\r\n{map_name}\r\n".encode()
    ]
    for filename, payload in files:
        chunks.append(
            (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
                "Content-Type: application/octet-stream\r\n\r\n"
            ).encode()
        )
        chunks.append(payload)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


class ServerSecurityTests(unittest.TestCase):
    def test_path_api_is_limited_to_input_roots(self) -> None:
        self.assertTrue(allowed_input_path(ROOT / "inputs" / "README.md"))
        self.assertTrue(allowed_input_path(ALLOWED_INPUT_ROOTS[1] / "example.nav"))
        self.assertFalse(allowed_input_path(ROOT / "README.md"))
        self.assertFalse(allowed_input_path(ROOT / "docs" / "STATE.md"))

    def test_map_name_rejects_traversal(self) -> None:
        self.assertTrue(MAP_RE.fullmatch("de_dust2"))
        self.assertFalse(MAP_RE.fullmatch("../de_dust2"))
        self.assertFalse(MAP_RE.fullmatch("de_dust2/../../x"))
        self.assertFalse(MAP_RE.fullmatch(""))

    def test_job_id_rejects_traversal(self) -> None:
        self.assertTrue(JOB_RE.fullmatch("beta0000005"))
        self.assertTrue(JOB_RE.fullmatch("51840fe93523"))
        self.assertFalse(JOB_RE.fullmatch("../beta"))
        self.assertFalse(JOB_RE.fullmatch("beta/../../x"))

    def test_logo_route_serves_only_the_expected_png_asset(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/logo.png"
            with urlopen(url, timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), "image/png")
                self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
                self.assertEqual(response.read(8), b"\x89PNG\r\n\x1a\n")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_upload_extensions_are_allowlisted(self) -> None:
        self.assertEqual(ALLOWED_SUFFIXES, {".nav", ".txt", ".gltf", ".bin"})
        self.assertNotIn(".exe", ALLOWED_SUFFIXES)
        self.assertNotIn(".py", ALLOWED_SUFFIXES)

    def test_json_request_body_must_be_an_object(self) -> None:
        self.assertEqual(parse_json_object(b'{"map":"de_dust2"}'), {"map": "de_dust2"})
        for body in (b"[]", b"null", b'"text"', b"42", b"not json"):
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_json_object(body)

    def test_intake_ui_has_csp_and_referrer_headers(self) -> None:
        policy = UI_HEADERS["Content-Security-Policy"]
        self.assertIn("default-src 'self'", policy)
        self.assertIn("frame-src 'self'", policy)
        self.assertEqual(UI_HEADERS["Referrer-Policy"], "no-referrer")
        self.assertEqual(UI_HEADERS["X-Frame-Options"], "DENY")

    def test_viewer_response_is_self_contained_and_same_origin(self) -> None:
        policy = VIEWER_HEADERS["Content-Security-Policy"]
        self.assertIn("default-src 'none'", policy)
        self.assertIn("connect-src 'none'", policy)
        self.assertIn("frame-ancestors 'self'", policy)
        self.assertEqual(VIEWER_HEADERS["X-Frame-Options"], "SAMEORIGIN")
        self.assertEqual(VIEWER_HEADERS["Referrer-Policy"], "no-referrer")

    def test_gltf_sidecar_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gltf = root / "world.gltf"
            gltf.write_text(
                json.dumps({"buffers": [{"uri": "world.bin", "byteLength": 1}]}),
                encoding="utf-8",
            )
            self.assertEqual(Handler._missing_gltf_sidecars(gltf), ["world.bin"])
            (root / "world.bin").write_bytes(b"\0")
            self.assertEqual(Handler._missing_gltf_sidecars(gltf), [])

            gltf.write_text(
                json.dumps({"buffers": [{"uri": "../outside.bin", "byteLength": 1}]}),
                encoding="utf-8",
            )
            self.assertTrue(
                Handler._missing_gltf_sidecars(gltf)[0].startswith("../outside.bin")
            )

    def test_config_reports_sri_not_external_cli(self) -> None:
        with live_server() as (port, _inputs, _uploads):
            status, body = request(port, "GET", "/api/config")
            self.assertEqual(status, 200)
            data = json.loads(body.decode("utf-8"))
        self.assertIn("sri_ready", data)
        self.assertIn("sri", data)
        self.assertNotIn("s2v_cli", data)
        self.assertNotIn("s2v_ready", data)

    def test_host_header_must_be_loopback(self) -> None:
        with live_server() as (port, _inputs, _uploads):
            status, _body = request(
                port, "GET", "/api/health", headers={"Host": "evil.example"}
            )
        self.assertEqual(status, 403)

    def test_post_requires_same_origin(self) -> None:
        with live_server() as (port, _inputs, _uploads):
            status, _ = json_request(port, "/api/generate", {}, origin=False)
            self.assertEqual(status, 403)
            status, _ = json_request(
                port,
                "/api/generate",
                {},
                headers={"Origin": "http://evil.example", "Sec-Fetch-Site": "cross-site"},
            )
            self.assertEqual(status, 403)
            status, _ = json_request(
                port,
                "/api/generate",
                {},
                headers={"Origin": "http://evil.example"},
            )
            self.assertEqual(status, 403)

    def test_invalid_json_and_map_name(self) -> None:
        with live_server() as (port, _inputs, _uploads):
            status, _ = json_request(port, "/api/generate", [])
            self.assertEqual(status, 400)
            status, _ = json_request(port, "/api/generate", {"map": "../escape"})
            self.assertEqual(status, 400)

    def test_upload_rejects_extension_and_missing_sidecar(self) -> None:
        with live_server() as (port, _inputs, uploads):
            body, content_type = multipart_body([("evil.exe", b"MZ")])
            status, _ = request(
                port,
                "POST",
                "/api/upload",
                body,
                {
                    "Content-Type": content_type,
                    "Origin": f"http://127.0.0.1:{port}",
                    "Sec-Fetch-Site": "same-origin",
                },
            )
            self.assertEqual(status, 400)
            self.assertEqual(list(uploads.iterdir()), [])

            body, content_type = multipart_body(
                [
                    ("map.nav", b"nav"),
                    ("entities.txt", b'classname = "worldspawn"\n'),
                    (
                        "world.gltf",
                        json.dumps({"buffers": [{"uri": "world.bin", "byteLength": 1}]}).encode(),
                    ),
                ]
            )
            status, _ = request(
                port,
                "POST",
                "/api/upload",
                body,
                {
                    "Content-Type": content_type,
                    "Origin": f"http://127.0.0.1:{port}",
                    "Sec-Fetch-Site": "same-origin",
                },
            )
            self.assertEqual(status, 400)
            self.assertEqual(list(uploads.iterdir()), [])

    def test_oversized_upload_is_rejected_without_body_read(self) -> None:
        with live_server() as (port, _inputs, _uploads):
            status, _ = request(
                port,
                "POST",
                "/api/upload",
                b"",
                {
                    "Content-Type": "multipart/form-data; boundary=x",
                    "Content-Length": str(MAX_UPLOAD + 1),
                    "Origin": f"http://127.0.0.1:{port}",
                    "Sec-Fetch-Site": "same-origin",
                },
            )
        self.assertEqual(status, 400)

    def test_job_limit_rejects_controlled(self) -> None:
        with live_server() as (port, inputs, _uploads):
            nav = inputs / "map.nav"
            entities = inputs / "entities.txt"
            gltf = inputs / "world.gltf"
            nav.write_bytes(b"nav")
            entities.write_text('classname = "worldspawn"\n', encoding="utf-8")
            gltf.write_text('{"asset":{"version":"2.0"}}', encoding="utf-8")
            with mock.patch.object(server_module, "MAX_ACTIVE_JOBS", 0):
                status, data = json_request(
                    port,
                    "/api/generate",
                    {
                        "map": "de_dust2",
                        "nav": str(nav),
                        "entities": str(entities),
                        "collision_gltf": str(gltf),
                    },
                )
        self.assertEqual(status, 429)
        self.assertIn("too many active jobs", data["error"])

    def test_viewer_path_confinement(self) -> None:
        with live_server() as (port, _inputs, _uploads):
            for path in ("/viewer/../../README.md", "/viewer/..%2f..%2fREADME.md", "/viewer/abc"):
                status, _body = request(port, "GET", path)
                self.assertEqual(status, 404, path)

    def test_prune_jobs_and_uploads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with mock.patch.multiple(
                server_module,
                UPLOADS_DIR=base,
                JOB_RETENTION_SECONDS=60,
            ):
                old = datetime.now(timezone.utc) - timedelta(days=1)
                with server_module.JOBS_LOCK:
                    server_module.JOBS.clear()
                    server_module.JOBS["old"] = {
                        "status": "ok",
                        "finished_utc": old.isoformat(),
                    }
                    server_module.JOBS["active"] = {"status": "running"}
                prune_jobs()
                with server_module.JOBS_LOCK:
                    self.assertNotIn("old", server_module.JOBS)
                    self.assertIn("active", server_module.JOBS)
                    server_module.JOBS.clear()

                stale = base / "stale"
                stale.mkdir()
                os.utime(stale, (time.time() - 2 * 24 * 60 * 60,) * 2)
                fresh = base / "fresh"
                fresh.mkdir()
                prune_uploads()
                self.assertFalse(stale.exists())
                self.assertTrue(fresh.exists())

    def test_process_tree_termination(self) -> None:
        kwargs = {}
        if os.name != "nt":
            kwargs["start_new_session"] = True
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **kwargs,
        )
        try:
            terminate_process_tree(process)
            self.assertIsNotNone(process.poll())
        finally:
            if process.poll() is None:
                process.kill()

    def test_process_tree_termination_includes_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory) / "child.pid"
            code = (
                "import pathlib, subprocess, sys, time\n"
                "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
                "time.sleep(60)\n"
            )
            kwargs = {}
            if os.name != "nt":
                kwargs["start_new_session"] = True
            parent = subprocess.Popen(
                [sys.executable, "-c", code, str(pid_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **kwargs,
            )
            try:
                for _ in range(50):
                    if pid_file.is_file():
                        break
                    time.sleep(0.1)
                self.assertTrue(pid_file.is_file())
                child_pid = int(pid_file.read_text(encoding="utf-8"))
                terminate_process_tree(parent)
                time.sleep(0.5)
                if os.name == "nt":
                    listing = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {child_pid}", "/NH"],
                        capture_output=True,
                        text=True,
                        check=False,
                    ).stdout
                    alive = str(child_pid) in listing
                else:
                    try:
                        os.kill(child_pid, 0)
                        alive = True
                    except OSError:
                        alive = False
                self.assertFalse(alive)
            finally:
                if parent.poll() is None:
                    parent.kill()

    def test_remote_binding_is_rejected(self) -> None:
        for arguments in (["--host", "0.0.0.0"], ["--allow-remote"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, "app/server.py", *arguments],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("remote binding is disabled", result.stderr)

    def test_job_timeout_sets_failed_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out_dir = Path(directory) / "out"
            out_dir.mkdir()
            job_id = "timeouttest01"
            with server_module.JOBS_LOCK:
                server_module.JOBS.clear()
                server_module.JOBS[job_id] = {
                    "id": job_id,
                    "map": "de_dust2",
                    "status": "queued",
                    "log": [],
                    "out_dir": str(out_dir),
                }
            try:
                with mock.patch.object(server_module, "JOB_TIMEOUT_SECONDS", 1):
                    run_job(
                        job_id,
                        [sys.executable, "-c", "import time; time.sleep(30)"],
                        out_dir,
                    )
                with server_module.JOBS_LOCK:
                    job = server_module.JOBS[job_id]
                self.assertEqual(job["status"], "failed")
                self.assertEqual(job["returncode"], -1)
                self.assertTrue(any("timed out" in line for line in job["log"]))
            finally:
                with server_module.JOBS_LOCK:
                    server_module.JOBS.clear()



if __name__ == "__main__":
    unittest.main()
