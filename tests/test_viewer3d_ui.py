"""Static contracts for the 3DsVW viewer and application shell."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "viewer3d" / "assets"
APP = ROOT / "app" / "index.html"


class ViewerUiContractTests(unittest.TestCase):
    def test_viewer_assets_are_local_and_have_no_inline_script(self) -> None:
        html = (VIEWER / "index.html").read_text(encoding="utf-8")
        scripts = re.findall(r"<script\b[^>]*>", html)
        self.assertTrue(scripts)
        for tag in scripts:
            self.assertIn("src=", tag)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        for name in ("viewer.css", "viewer.js"):
            text = (VIEWER / name).read_text(encoding="utf-8")
            self.assertNotIn("http://", text)
            self.assertNotIn("https://", text)

    def test_viewer_uses_vendored_three_and_safe_text(self) -> None:
        js = (VIEWER / "viewer.js").read_text(encoding="utf-8")
        self.assertIn("./vendor/three.module.min.js", js)
        self.assertIn("textContent", js)
        self.assertNotIn("innerHTML", js)
        self.assertTrue((VIEWER / "vendor" / "three.module.min.js").is_file())
        self.assertTrue((VIEWER / "vendor" / "LICENSE-three.txt").is_file())
        license_text = (VIEWER / "vendor" / "LICENSE-three.txt").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)

    def test_application_has_viewer_and_settings_contracts(self) -> None:
        html = APP.read_text(encoding="utf-8")
        for marker in (
            'id="viewer3d-frame"',
            'id="viewer3d-link"',
            'id="viewer3d-tab"',
            'data-viewer-tab="3d"',
            'data-viewer-tab="2d"',
            'id="setting-viewer-mode"',
            'id="setting-quality"',
            'id="setting-layer-collision"',
            'id="setting-layer-routes"',
            'data-view-panel="overview"',
            'data-view-panel="process"',
            'data-view-panel="library"',
            'data-view-panel="viewer"',
            'data-view-panel="settings"',
            'docs/USER_GUIDE.md',
        ):
            self.assertIn(marker, html)


if __name__ == "__main__":
    unittest.main()
