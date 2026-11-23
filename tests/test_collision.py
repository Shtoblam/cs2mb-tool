"""Synthetic tests for the glTF collision floor index."""

from __future__ import annotations

import sys
import unittest
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from gltf_collision import Primitive, TriangleIndex, wall_segments  # noqa: E402


def triangle_primitive(
    z: float,
    interact: tuple[str, ...] = (),
    material: str = "test",
) -> Primitive:
    positions = array("f", [0.0, 0.0, z, 1.0, 0.0, z, 0.0, 1.0, z])
    indices = array("H", [0, 1, 2])
    return Primitive(
        material=material,
        interact_as=interact,
        positions=positions,
        indices=indices,
        bounds_min=(0.0, 0.0, z),
        bounds_max=(1.0, 1.0, z),
    )


class CollisionIndexTests(unittest.TestCase):
    def test_stacked_floors(self) -> None:
        index = TriangleIndex(
            [triangle_primitive(0.0), triangle_primitive(100.0)],
            cell_size=128.0,
        )
        self.assertEqual(index.hits_at(0.5, 0.5), [0.0, 100.0])
        self.assertEqual(index.nearest_z(0.5, 0.5, 95.0), (100.0, 5.0))
        self.assertEqual(index.nearest_z(0.5, 0.5, 5.0), (0.0, -5.0))

    def test_sky_is_excluded(self) -> None:
        index = TriangleIndex(
            [triangle_primitive(0.0), triangle_primitive(100.0, ("sky",))],
            cell_size=128.0,
        )
        self.assertEqual(index.hits_at(0.5, 0.5), [0.0])
        self.assertEqual(index.triangle_count, 1)

    def test_miss_returns_none(self) -> None:
        index = TriangleIndex([triangle_primitive(0.0)], cell_size=128.0)
        self.assertEqual(index.hits_at(2.0, 2.0), [])
        self.assertIsNone(index.nearest_z(2.0, 2.0, 0.0))

    def test_wall_blocks_segment_at_waist_height(self) -> None:
        positions = array(
            "f",
            [
                0.5, -1.0, 0.0,
                0.5, 1.0, 0.0,
                0.5, 1.0, 100.0,
            ],
        )
        wall = Primitive(
            material="wall",
            interact_as=(),
            positions=positions,
            indices=array("H", [0, 1, 2]),
            bounds_min=(0.5, -1.0, 0.0),
            bounds_max=(0.5, 1.0, 100.0),
        )
        index = TriangleIndex([wall], cell_size=128.0)
        self.assertEqual(
            index.segment_blocked_2d((0.0, 0.0), (1.0, 0.0), 50.0),
            ["wall"],
        )
        self.assertEqual(
            index.segment_blocked_2d((0.0, 0.0), (1.0, 0.0), 150.0),
            [],
        )

    def test_horizontal_clearance(self) -> None:
        positions = array(
            "f",
            [0.5, -1.0, 0.0, 0.5, 1.0, 0.0, 0.5, 1.0, 100.0],
        )
        wall = Primitive(
            material="wall",
            interact_as=(),
            positions=positions,
            indices=array("H", [0, 1, 2]),
            bounds_min=(0.5, -1.0, 0.0),
            bounds_max=(0.5, 1.0, 100.0),
        )
        index = TriangleIndex([wall], cell_size=128.0)
        distance, material = index.horizontal_clearance(0.0, 0.0, 50.0)
        self.assertAlmostEqual(distance, 0.5, places=6)
        self.assertEqual(material, "wall")

    def test_vertical_clearance_and_clip_exclusion(self) -> None:
        ceiling = Primitive(
            material="physics_npcclip_playerclip_material",
            interact_as=(),
            positions=array("f", [0.0, 0.0, 60.0, 1.0, 0.0, 60.0, 0.0, 1.0, 60.0]),
            indices=array("H", [0, 1, 2]),
            bounds_min=(0.0, 0.0, 60.0),
            bounds_max=(1.0, 1.0, 60.0),
        )
        floor = triangle_primitive(0.0)
        index = TriangleIndex([floor, ceiling], cell_size=128.0)
        floor_z, ceiling_z, gap = index.vertical_clearance(0.25, 0.25, 0.0)
        self.assertAlmostEqual(floor_z, 0.0, places=6)
        self.assertAlmostEqual(ceiling_z, 60.0, places=6)
        self.assertAlmostEqual(gap, 60.0, places=6)

        _floor_z, clip_ceiling, clip_gap = index.vertical_clearance(
            0.25, 0.25, 0.0, exclude_substrings={"clip"}
        )
        self.assertIsNone(clip_ceiling)
        self.assertEqual(clip_gap, float("inf"))

    def test_segment_capsule_radius_and_intersection(self) -> None:
        wall = Primitive(
            material="wall",
            interact_as=(),
            positions=array(
                "f",
                [0.5, -1.0, 0.0, 0.5, 1.0, 0.0, 0.5, 1.0, 100.0],
            ),
            indices=array("H", [0, 1, 2]),
            bounds_min=(0.5, -1.0, 0.0),
            bounds_max=(0.5, 1.0, 100.0),
        )
        index = TriangleIndex([wall], cell_size=128.0)
        distance, material = index.segment_capsule_clearance_2d(
            (0.0, 0.0), (0.0, 1.0), 50.0, max_dist=1.0
        )
        self.assertAlmostEqual(distance, 0.5, places=6)
        self.assertEqual(material, "wall")
        self.assertEqual(
            index.segment_capsule_blocked_2d((0.0, 0.0), (0.0, 1.0), 50.0, radius=0.6),
            ["wall"],
        )
        self.assertEqual(
            index.segment_capsule_blocked_2d((0.0, 0.0), (0.0, 1.0), 50.0, radius=0.4),
            [],
        )
        self.assertEqual(
            index.segment_capsule_blocked_2d(
                (0.5, -2.0), (0.5, 2.0), 50.0, radius=0.1
            ),
            ["wall"],
        )

    def test_wall_segments_use_lowest_edge_and_dedupe(self) -> None:
        wall_a = Primitive(
            material="wall",
            interact_as=(),
            positions=array(
                "f",
                [0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 20.0],
            ),
            indices=array("H", [0, 1, 2]),
            bounds_min=(0.0, 0.0, 0.0),
            bounds_max=(20.0, 0.0, 20.0),
        )
        wall_b = Primitive(
            material="wall",
            interact_as=(),
            positions=array(
                "f",
                [0.0, 0.0, 0.0, 20.0, 0.0, 0.0, 0.0, 0.0, 30.0],
            ),
            indices=array("H", [0, 1, 2]),
            bounds_min=(0.0, 0.0, 0.0),
            bounds_max=(20.0, 0.0, 30.0),
        )
        horizontal = triangle_primitive(0.0)
        clipped = Primitive(
            material="physics_npcclip_playerclip_material",
            interact_as=("playerclip",),
            positions=array(
                "f",
                [0.0, 5.0, 0.0, 20.0, 5.0, 0.0, 0.0, 5.0, 20.0],
            ),
            indices=array("H", [0, 1, 2]),
            bounds_min=(0.0, 5.0, 0.0),
            bounds_max=(20.0, 5.0, 20.0),
        )
        segments = wall_segments(
            [wall_a, wall_b, horizontal, clipped],
            min_length=10.0,
            quantize=1.0,
        )
        self.assertEqual(segments, {((0.0, 0.0), (20.0, 0.0))})

    def test_wall_segments_respect_min_length(self) -> None:
        wall = Primitive(
            material="wall",
            interact_as=(),
            positions=array(
                "f",
                [0.0, 0.0, 0.0, 8.0, 0.0, 0.0, 0.0, 0.0, 20.0],
            ),
            indices=array("H", [0, 1, 2]),
            bounds_min=(0.0, 0.0, 0.0),
            bounds_max=(8.0, 0.0, 20.0),
        )
        self.assertEqual(wall_segments([wall], min_length=12.0), set())


if __name__ == "__main__":
    unittest.main()
