"""CLI-level tests for the packaged cs2mb-sri executable.

The malformed-resource cases are synthetic and do not need a CS2 install.
Real-map integration is gated by CS2MB_TEST_GAME so CI remains asset-free.
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sri  # noqa: E402


def converter() -> Path | None:
    try:
        return sri.resolve_sri()
    except sri.SriError:
        return None


EXE = converter()


@unittest.skipIf(EXE is None, "cs2mb-sri is not installed")
class SriCliTests(unittest.TestCase):
    def run_cli(self, *arguments: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
        assert EXE is not None
        return subprocess.run(
            [str(EXE), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )

    def assert_controlled_failure(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertNotEqual(result.returncode, 0)
        combined = (result.stderr or "") + (result.stdout or "")
        self.assertIn("cs2mb-sri:", combined)
        self.assertNotIn("Unhandled exception", combined)
        self.assertNotIn("   at ", combined)

    def test_version(self) -> None:
        result = self.run_cli("--version")
        self.assertEqual(result.returncode, 0)
        self.assertIn("cs2mb-sri", result.stdout)

    def test_minimal_empty_resource_is_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resource = Path(directory) / "empty.vmdl_c"
            resource.write_bytes(struct.pack("<IHHII", 16, 12, 1, 8, 0))
            result = self.run_cli("inspect", "--input", str(resource))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("header_version: 12", result.stdout)

    def test_empty_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resource = Path(directory) / "empty.vmdl_c"
            resource.write_bytes(b"")
            result = self.run_cli("inspect", "--input", str(resource))
        self.assert_controlled_failure(result)

    def test_garbage_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resource = Path(directory) / "garbage.vents_c"
            resource.write_bytes(b"not a Source 2 resource at all")
            result = self.run_cli("entities", "--input", str(resource), "--output", str(Path(directory) / "out.txt"))
        self.assert_controlled_failure(result)

    def test_unsupported_header_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resource = Path(directory) / "future.vmdl_c"
            resource.write_bytes(struct.pack("<IHHII", 16, 13, 1, 8, 0))
            result = self.run_cli("inspect", "--input", str(resource))
        self.assert_controlled_failure(result)

    def test_truncated_block_table_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resource = Path(directory) / "truncated.vmdl_c"
            header = struct.pack("<IHHII", 64, 12, 1, 8, 4)
            resource.write_bytes(header + b"\x00" * 8)
            result = self.run_cli("inspect", "--input", str(resource))
        self.assert_controlled_failure(result)

    def test_oversized_declared_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            resource = Path(directory) / "oversized.vmdl_c"
            header = struct.pack("<IHHII", 0xFFFFFFF0, 12, 1, 8, 0)
            resource.write_bytes(header)
            result = self.run_cli("inspect", "--input", str(resource))
        self.assert_controlled_failure(result)

    def test_missing_input_is_rejected(self) -> None:
        result = self.run_cli("inspect", "--input", "does-not-exist.vmdl_c")
        self.assert_controlled_failure(result)

    @unittest.skipUnless(
        os.environ.get("CS2MB_TEST_GAME"), "set CS2MB_TEST_GAME for real-map checks"
    )
    def test_real_map_entity_dump(self) -> None:
        game = Path(os.environ["CS2MB_TEST_GAME"])
        map_vpk = game / "game" / "csgo" / "maps" / "de_dust2.vpk"
        if not map_vpk.is_file():
            self.skipTest(f"missing {map_vpk}")
        from vpk_read import Vpk

        package = Vpk(map_vpk)
        wanted = "maps/de_dust2/entities/default_ents.vents_c"
        entry = next(
            (item for item in package.entries if item.path.lower() == wanted),
            None,
        )
        if entry is None:
            self.skipTest("entity resource not present in map VPK")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "default_ents.vents_c"
            output = Path(directory) / "entities.txt"
            source.write_bytes(package.read(entry))
            result = self.run_cli(
                "entities", "--input", str(source), "--output", str(output)
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            text = output.read_text(encoding="utf-8")
            self.assertIn('classname                      = "info_player_terrorist"', text)
            self.assertIn('classname                      = "info_player_counterterrorist"', text)


if __name__ == "__main__":
    unittest.main()
