"""Tests for the resourceinfo text dump parser."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from nav_experiment import parse_entity_points  # noqa: E402

DUMP = """\
classname = "info_player_terrorist"
origin = [ -456.0, -2384.0, -156.0 ]
classname = "env_cs_place"
place_name = "BombsiteA"
origin = [ 10.0, 20.0, 30.0 ]
"""


class EntityParserTests(unittest.TestCase):
    def _parse_bytes(self, data: bytes) -> list:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "entities.txt"
            path.write_bytes(data)
            return parse_entity_points(path)

    def test_utf8_and_utf8_bom(self) -> None:
        for data in (DUMP.encode("utf-8"), b"\xef\xbb\xbf" + DUMP.encode("utf-8")):
            points = self._parse_bytes(data)
            self.assertEqual(len(points), 2)
            self.assertEqual(points[0].classname, "info_player_terrorist")
            self.assertEqual(points[1].place_name, "BombsiteA")

    def test_utf16_le_bom(self) -> None:
        points = self._parse_bytes(b"\xff\xfe" + DUMP.encode("utf-16-le"))
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0].origin, (-456.0, -2384.0, -156.0))
        self.assertEqual(points[1].origin, (10.0, 20.0, 30.0))


if __name__ == "__main__":
    unittest.main()
