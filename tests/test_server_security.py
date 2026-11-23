"""Security-focused tests for the local auto-generation server."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.server import (  # noqa: E402
    ALLOWED_INPUT_ROOTS,
    ALLOWED_SUFFIXES,
    JOB_RE,
    MAP_RE,
    Handler,
    UI_HEADERS,
    VIEWER_HEADERS,
    allowed_input_path,
    parse_json_object,
)


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
            self.assertEqual(
                Handler._missing_gltf_sidecars(gltf),
                ["world.bin"],
            )
            (root / "world.bin").write_bytes(b"\0")
            self.assertEqual(Handler._missing_gltf_sidecars(gltf), [])

            gltf.write_text(
                json.dumps({"buffers": [{"uri": "../outside.bin", "byteLength": 1}]}),
                encoding="utf-8",
            )
            self.assertTrue(
                Handler._missing_gltf_sidecars(gltf)[0].startswith("../outside.bin")
            )

    def test_config_reports_internal_engine_not_external_cli(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/config"
            with urlopen(url, timeout=10) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))
            self.assertIn("source2_ready", data)
            self.assertIn("source2", data)
            self.assertNotIn("s2v_cli", data)
            self.assertNotIn("s2v_ready", data)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
