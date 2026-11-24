"""Regression tests for shareable auto_generate manifests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import auto_generate  # noqa: E402


class ManifestSanitizationTests(unittest.TestCase):
    def test_dry_run_manifest_contains_no_absolute_local_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "Users" / "alice" / "project"
            base.mkdir(parents=True)
            nav = base / "map.nav"
            entities = base / "entities.txt"
            gltf = base / "world.gltf"
            sidecar = base / "world.bin"
            nav.write_bytes(b"nav")
            entities.write_text('classname = "worldspawn"\n', encoding="utf-8")
            gltf.write_text(
                json.dumps({"asset": {"version": "2.0"}, "buffers": [{"uri": "world.bin", "byteLength": 1}]}),
                encoding="utf-8",
            )
            sidecar.write_bytes(b"\0")
            out = base / "out"
            result = subprocess.run(
                [
                    sys.executable,
                    "tools/auto_generate.py",
                    "--map",
                    "de_dust2",
                    "--nav",
                    str(nav),
                    "--entities",
                    str(entities),
                    "--collision-gltf",
                    str(gltf),
                    "--out-dir",
                    str(out),
                    "--dry-run",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-1000:])
            text = (out / "manifest.json").read_text(encoding="utf-8")
            manifest = json.loads(text)
            self.assertNotIn(str(base), text)
            self.assertNotIn(str(Path.home()), text)
            self.assertNotIn(sys.executable, text)
            self.assertNotIn("alice", text)
            self.assertIn("<INPUT>/nav/map.nav", text)
            self.assertIn("<INPUT>/entities/entities.txt", text)
            self.assertIn("<INPUT>/collision/world.gltf", text)
            self.assertIn("<INPUT>/collision/world.bin", text)
            self.assertIn("<PYTHON>", text)
            self.assertEqual(manifest["inputs"]["nav"]["size"], 3)
            self.assertEqual(
                manifest["inputs"]["collision_gltf"]["sidecars"][0]["uri"], "world.bin"
            )
            self.assertTrue(manifest["inputs"]["nav"]["sha256"])

    def test_viewer_info_is_relative_when_out_dir_is_temporary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            info = {
                "ok": True,
                "data": str(base / "viewer3d" / "data.json"),
                "scene": str(base / "viewer3d" / "scene.gltf"),
                "bytes": 10,
            }
            shown = auto_generate.display_viewer3d(info, base)
            self.assertEqual(shown["data"], "viewer3d/data.json")
            self.assertEqual(shown["scene"], "viewer3d/scene.gltf")
            self.assertNotIn(str(base), json.dumps(shown))

    def test_command_display_hides_absolute_paths_and_python(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            command = [
                sys.executable,
                str(base / "tools" / "step.py"),
                "--input",
                str(base / "inputs" / "alice.nav"),
                "--out",
                str(base / "out"),
                "--flag",
            ]
            shown = auto_generate.display_command(command, {}, base)
            self.assertEqual(shown[0], "<PYTHON>")
            self.assertNotIn(str(base), " ".join(shown))
            self.assertIn("--flag", shown)


class SafeUriTests(unittest.TestCase):
    def test_private_and_parent_components_are_removed(self) -> None:
        self.assertEqual(
            auto_generate.safe_uri(r"C:\maps\world.bin"),
            "world.bin",
        )
        self.assertEqual(
            auto_generate.safe_uri("../private/world.bin"),
            "private/world.bin",
        )
        self.assertEqual(
            auto_generate.safe_uri("sub/world.bin"),
            "sub/world.bin",
        )
        self.assertEqual(
            auto_generate.safe_uri("https://example.invalid/world.bin"),
            "",
        )


if __name__ == "__main__":
    unittest.main()
