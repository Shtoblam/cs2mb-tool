"""Focused tests for prepare_map dry-run and passthrough behavior."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import prepare_map  # noqa: E402


class PrepareMapTests(unittest.TestCase):
    def _game(self, base: Path) -> Path:
        game = base / "game"
        (game / "game" / "csgo" / "maps").mkdir(parents=True)
        (game / "game" / "csgo" / "gameinfo.gi").write_text("", encoding="utf-8")
        (game / "game" / "csgo" / "maps" / "de_dust2.vpk").write_bytes(b"vpk")
        converter = base / "cs2mb-sri.exe"
        converter.write_bytes(b"MZ")
        return game, converter

    def _run(self, arguments: list[str], converter_path: Path | None = None, **patches) -> tuple[int, str]:
        stdout = io.StringIO()
        with mock.patch.object(sys, "argv", ["prepare_map.py", *arguments]), mock.patch.object(
            prepare_map, "resolve_sri", return_value=converter_path or Path("cs2mb-sri.exe")
        ), mock.patch.object(prepare_map, "version", return_value="cs2mb-sri 1.0.0"), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
            with contextlib.ExitStack() as stack:
                for name, value in patches.items():
                    stack.enter_context(mock.patch.object(prepare_map, name, value))
                result = prepare_map.main()
        return result, stdout.getvalue()

    def test_dry_run_writes_nothing_and_calls_no_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            game, converter = self._game(base)
            out = base / "out"
            generated = base / "generated"
            vpk = mock.Mock()
            with mock.patch.object(prepare_map, "Vpk", return_value=vpk) as vpk_factory, mock.patch.object(
                prepare_map, "extract_entry"
            ) as extract, mock.patch.object(prepare_map, "convert_entities") as convert_entities, mock.patch.object(
                prepare_map, "convert_physics"
            ) as convert_physics, mock.patch.object(prepare_map, "run") as run:
                result, output = self._run(
                    [
                        "--map",
                        "de_dust2",
                        "--game",
                        str(game),
                        "--out-dir",
                        str(out),
                        "--generate-out",
                        str(generated),
                        "--dry-run",
                    ]
                )
            self.assertEqual(result, 0, output)
            self.assertIn("no files were written", output)
            self.assertFalse(out.exists())
            self.assertFalse(generated.exists())
            vpk_factory.assert_not_called()
            extract.assert_not_called()
            convert_entities.assert_not_called()
            convert_physics.assert_not_called()
            run.assert_not_called()

    def test_dry_run_reports_missing_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            out = base / "out"
            result, output = self._run(
                ["--map", "de_dust2", "--game", str(base / "missing"), "--out-dir", str(out), "--dry-run"]
            )
            self.assertEqual(result, 2)
            self.assertIn("missing required path", output if output else "")
            self.assertFalse(out.exists())

    def test_normal_mode_still_reaches_conversion_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            game, converter = self._game(base)
            out = base / "out"

            def extract_entry(_vpk, _wanted, target):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"resource")

            def convert_entities(_source, target, explicit=None):
                target.write_text('classname = "worldspawn"\n', encoding="utf-8")
                return "entity ok"

            def convert_physics(_source, target, explicit=None):
                target.write_text(
                    json.dumps({"asset": {"version": "2.0"}, "buffers": [{"uri": target.with_suffix(".bin").name}]}),
                    encoding="utf-8",
                )
                target.with_suffix(".bin").write_bytes(b"\0")
                return "phys ok"

            with mock.patch.object(prepare_map, "Vpk", return_value=mock.Mock()), mock.patch.object(
                prepare_map, "extract_entry", side_effect=extract_entry
            ), mock.patch.object(
                prepare_map, "convert_entities", side_effect=convert_entities
            ) as entities_call, mock.patch.object(
                prepare_map, "convert_physics", side_effect=convert_physics
            ) as physics_call:
                result, output = self._run(
                    ["--map", "de_dust2", "--game", str(game), "--out-dir", str(out)],
                    converter_path=converter,
                )
            self.assertEqual(result, 0, output)
            self.assertTrue((out / "prepared" / "entities.txt").is_file())
            self.assertTrue((out / "prepared_manifest.json").is_file())
            entities_call.assert_called_once()
            physics_call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
