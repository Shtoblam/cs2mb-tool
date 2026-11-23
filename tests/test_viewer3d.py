"""3DsVW data-builder tests with synthetic inputs."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nav_inspect import Area, NavMesh  # noqa: E402
from viewer3d.build import (  # noqa: E402
    build_payload,
    build_viewer3d,
    gltf_summary,
    nav_payload,
    parse_entity_blocks,
)


def square(area_id: int, x: float, y: float, z: float = 0.0) -> Area:
    return Area(
        area_id=area_id,
        attribute_flags=0,
        hull_index=0,
        corner_gravity=None,
        corners=[(x, y, z), (x + 100, y, z), (x + 100, y + 100, z), (x, y + 100, z)],
        connections=[],
        hiding_spots=0,
        ladders_above=[],
        ladders_below=[],
    )


def nav() -> NavMesh:
    a = square(1, 0, 0)
    b = square(2, 100, 0, 10)
    a.connections = [(2, 3)]
    b.connections = [(1, 1)]
    return NavMesh(
        version=36,
        sub_version=1,
        is_analyzed=True,
        places=[],
        has_unnamed_areas=False,
        areas=[a, b],
        ladders=[],
    )


def minimal_gltf(uri: str = "collision.bin") -> dict:
    return {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": 36, "uri": uri}],
        "bufferViews": [{"byteOffset": 0, "byteLength": 36, "target": 34962}],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [0, 0, 0],
                "max": [100, 100, 20],
            },
            {"bufferView": 0, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
        "materials": [{"name": "physics_group_concrete", "pbrMetallicRoughness": {}}],
        "images": [{"uri": "https://example.invalid/texture.png"}],
        "textures": [{"source": 0}],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": 0},
                        "indices": 1,
                        "material": 0,
                    }
                ]
            }
        ],
        "nodes": [
            {
                "name": "physics_group_concrete",
                "mesh": 0,
                "extras": {
                    "SurfaceProperty": "concrete",
                    "CollisionGroup": "Default",
                    "InteractAs": [],
                },
            }
        ],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }


class EntityParseTests(unittest.TestCase):
    def test_entity_blocks_are_bounded_and_typed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "entities.txt"
            path.write_text(
                '====0====\nclassname = "info_player_counterterrorist"\n'
                'origin = [ 10.0, 20.0, 30.0 ]\nangles = [ 0.0, 90.0, 0.0 ]\n'
                'targetname = "spawn_1"\n'
                '====1====\nclassname = "env_cs_place"\nplace_name = "BombsiteA"\n'
                'origin = [ 1, 2, 3 ]\n',
                encoding="utf-8",
            )
            entities = parse_entity_blocks(path)
        self.assertEqual(len(entities), 2)
        self.assertEqual(entities[0]["origin"], [10.0, 20.0, 30.0])
        self.assertEqual(entities[0]["angles"], [0.0, 90.0, 0.0])
        self.assertEqual(entities[1]["place_name"], "BombsiteA")


class GltfPayloadTests(unittest.TestCase):
    def test_summary_reads_bounds_and_clip_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scene.gltf"
            data = minimal_gltf()
            data["nodes"].append(
                {
                    "name": "physics_sky",
                    "mesh": 0,
                    "extras": {"InteractAs": ["sky"], "SurfaceProperty": "default"},
                }
            )
            path.write_text(json.dumps(data), encoding="utf-8")
            summary = gltf_summary(path)
        self.assertEqual(summary["triangles"], 2)
        self.assertEqual(summary["bounds"]["min"], [0, 0, 0])
        self.assertTrue(any(node["clip"] for node in summary["nodes"]))

    def test_nav_payload_keeps_directed_edges(self) -> None:
        payload = nav_payload(nav())
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["edges"], [[1, 2], [2, 1]])
        self.assertEqual(payload["areas"][0]["corners"][0], [0.0, 0.0, 0.0])

    def test_build_payload_reports_routes_and_bounds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scene.gltf"
            path.write_text(json.dumps(minimal_gltf()), encoding="utf-8")
            payload = build_payload(nav(), [], path, "test_map")
        self.assertEqual(payload["schema"], "cs2mb.viewer3d/1")
        self.assertEqual(payload["stats"]["nav_areas"], 2)
        self.assertEqual(payload["stats"]["collision_triangles"], 1)
        self.assertEqual(payload["routes"], [])


class BuildTests(unittest.TestCase):
    def test_bundle_scrubs_textures_and_writes_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            gltf = base / "input.gltf"
            gltf.write_text(json.dumps(minimal_gltf()), encoding="utf-8")
            (base / "collision.bin").write_bytes(b"\0" * 36)
            entities = base / "entities.txt"
            entities.write_text('classname = "worldspawn"\n', encoding="utf-8")
            out = base / "out"
            with mock.patch("viewer3d.build.parse_nav", return_value=nav()):
                result = build_viewer3d(
                    base / "map.nav", entities, gltf, out, "test_map"
                )
            scene = json.loads((out / "viewer3d" / "scene.gltf").read_text(encoding="utf-8"))
            data = json.loads((out / "viewer3d" / "data.json").read_text(encoding="utf-8"))
            self.assertTrue(result["ok"])
            self.assertNotIn("images", scene)
            self.assertNotIn("textures", scene)
            self.assertEqual(scene["bufferViews"][0]["buffer"], 0)
            self.assertEqual(scene["buffers"][0]["uri"], "scene.bin")
            self.assertTrue((out / "viewer3d" / "scene.bin").is_file())
            self.assertEqual(data["map"], "test_map")

    def test_external_buffer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            gltf = base / "input.gltf"
            gltf.write_text(
                json.dumps(minimal_gltf("https://example.invalid/evil.bin")),
                encoding="utf-8",
            )
            entities = base / "entities.txt"
            entities.write_text('classname = "worldspawn"\n', encoding="utf-8")
            with mock.patch("viewer3d.build.parse_nav", return_value=nav()):
                with self.assertRaises(ValueError):
                    build_viewer3d(base / "map.nav", entities, gltf, base / "out", "test_map")


if __name__ == "__main__":
    unittest.main()
