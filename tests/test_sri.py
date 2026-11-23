"""Tests for the internal Source 2 converter wrapper and dependency removal."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import sri  # noqa: E402


class SriWrapperTests(unittest.TestCase):
    def test_explicit_converter_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "cs2mb-sri.exe"
            candidate.write_bytes(b"MZ")
            self.assertEqual(
                sri.resolve_sri(candidate), candidate.resolve()
            )

    def test_environment_converter_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "cs2mb-sri.exe"
            candidate.write_bytes(b"MZ")
            with mock.patch.dict(os.environ, {sri.ENV_VAR: str(candidate)}):
                self.assertEqual(
                    sri.resolve_sri(), candidate.resolve()
                )

    def test_missing_converter_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.exe"
            with self.assertRaises(sri.SriError) as context:
                sri.resolve_sri(missing)
            self.assertIn("SRI (cs2mb-sri) was not found", str(context.exception))

    def test_run_uses_an_argument_array_without_a_shell(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="ok\n", stderr=""
        )
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "cs2mb-sri.exe"
            candidate.write_bytes(b"MZ")
            with mock.patch.object(
                sri.subprocess, "run", return_value=completed
            ) as run:
                result = sri.run(
                    ["entities", "--input", "a", "--output", "b"],
                    explicit=candidate,
                )
        self.assertEqual(result.stdout, "ok\n")
        command = run.call_args.args[0]
        self.assertIsInstance(command, list)
        self.assertEqual(command[0], str(candidate.resolve()))
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_run_reports_stderr_tail_on_failure(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="line1\nline2\nboom"
        )
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "cs2mb-sri.exe"
            candidate.write_bytes(b"MZ")
            with mock.patch.object(
                sri.subprocess, "run", return_value=completed
            ), self.assertRaises(sri.SriError) as context:
                sri.run(["inspect"], explicit=candidate)
        self.assertIn("boom", str(context.exception))

    def test_run_reports_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "cs2mb-sri.exe"
            candidate.write_bytes(b"MZ")
            with mock.patch.object(
                sri.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(["exe"], 1),
            ), self.assertRaises(sri.SriError) as context:
                sri.run(["inspect"], explicit=candidate, timeout=1)
        self.assertIn("timed out", str(context.exception))

    def test_status_is_not_ready_for_a_missing_converter(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.exe"
            status = sri.status(explicit=missing)
        self.assertFalse(status.ready)
        self.assertEqual(status.path, "")
        self.assertIsNotNone(status.error)

    def test_file_hash_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "data.bin"
            candidate.write_bytes(b"cs2mb")
            self.assertEqual(
                sri.sha256(candidate),
                "295e7fa5d860e6d2756f78a71633e68be10f7ec3a6413e0db2aafc33abb30eee",
            )


class SriDependencyRemovalTests(unittest.TestCase):
    def test_pipeline_has_no_external_converter_references(self) -> None:
        for relative in (
            "tools/prepare_map.py",
            "app/server.py",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            lowered = text.lower()
            self.assertNotIn("s2v_cli", lowered, relative)
            self.assertNotIn("--s2v-cli", lowered, relative)
            self.assertNotIn("sriviewer", lowered, relative)
            self.assertNotIn("resourceinfo.exe", lowered, relative)

    def test_example_config_has_no_external_cli(self) -> None:
        data = json.loads(
            (ROOT / "config" / "paths.example.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("s2v_cli", data)
        self.assertIn("cs2_game", data)


if __name__ == "__main__":
    unittest.main()
