"""3DsVW data-builder tests with synthetic inputs."""

from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
VIEWER = ROOT / "viewer3d" / "assets"
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
            data["scenes"][0]["nodes"].append(1)
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


class TransactionalBuildTests(unittest.TestCase):
    def _inputs(self, base: Path) -> tuple[Path, Path, Path]:
        gltf = base / "input.gltf"
        gltf.write_text(json.dumps(minimal_gltf()), encoding="utf-8")
        (base / "collision.bin").write_bytes(b"\0" * 36)
        entities = base / "entities.txt"
        entities.write_text('classname = "worldspawn"\n', encoding="utf-8")
        return gltf, entities, base / "map.nav"

    def test_success_replaces_old_bundle_and_leaves_no_staging(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            gltf, entities, nav_path = self._inputs(base)
            old = base / "out" / "viewer3d"
            old.mkdir(parents=True)
            (old / "old.marker").write_text("old", encoding="utf-8")
            with mock.patch("viewer3d.build.parse_nav", return_value=nav()):
                build_viewer3d(nav_path, entities, gltf, base / "out", "test_map")
            self.assertFalse((old / "old.marker").exists())
            self.assertTrue((old / "data.json").is_file())
            leftovers = [p.name for p in (base / "out").iterdir() if p.name.startswith(".viewer3d")]
            self.assertEqual(leftovers, [])

    def test_failure_before_swap_keeps_prior_bundle_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            gltf, entities, nav_path = self._inputs(base)
            old = base / "out" / "viewer3d"
            old.mkdir(parents=True)
            marker = old / "old.marker"
            marker.write_bytes(b"known-good")
            with mock.patch("viewer3d.build.parse_nav", return_value=nav()), mock.patch(
                "viewer3d.build.shutil.copy2", side_effect=OSError("copy failed")
            ):
                with self.assertRaises(OSError):
                    build_viewer3d(nav_path, entities, gltf, base / "out", "test_map")
            self.assertEqual(marker.read_bytes(), b"known-good")

    def test_validation_failure_keeps_prior_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            gltf, entities, nav_path = self._inputs(base)
            old = base / "out" / "viewer3d"
            old.mkdir(parents=True)
            marker = old / "old.marker"
            marker.write_bytes(b"known-good")
            with mock.patch("viewer3d.build.parse_nav", return_value=nav()), mock.patch(
                "viewer3d.build._validate_bundle", side_effect=ValueError("invalid bundle")
            ):
                with self.assertRaises(ValueError):
                    build_viewer3d(nav_path, entities, gltf, base / "out", "test_map")
            self.assertEqual(marker.read_bytes(), b"known-good")

    def test_failure_during_swap_restores_prior_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            gltf, entities, nav_path = self._inputs(base)
            old = base / "out" / "viewer3d"
            old.mkdir(parents=True)
            marker = old / "old.marker"
            marker.write_bytes(b"known-good")
            real_replace = __import__("os").replace

            def replace(src, dst):
                if Path(src).name.startswith(".viewer3d-") and Path(dst).name == "viewer3d":
                    raise OSError("swap failed")
                return real_replace(src, dst)

            with mock.patch("viewer3d.build.parse_nav", return_value=nav()), mock.patch(
                "viewer3d.build.os.replace", side_effect=replace
            ):
                with self.assertRaises(OSError):
                    build_viewer3d(nav_path, entities, gltf, base / "out", "test_map")
            self.assertEqual(marker.read_bytes(), b"known-good")
            leftovers = [p.name for p in (base / "out").iterdir() if p.name.startswith(".viewer3d")]
            self.assertEqual(leftovers, [])


class BoundsTests(unittest.TestCase):
    def _payload(self, nav: NavMesh, bounds_min, bounds_max):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scene.gltf"
            data = minimal_gltf()
            data["accessors"][0]["min"] = bounds_min
            data["accessors"][0]["max"] = bounds_max
            path.write_text(json.dumps(data), encoding="utf-8")
            return build_payload(nav, [], path, "test_map")

    def test_collision_bounds_extend_beyond_nav_and_are_kept_separate(self) -> None:
        payload = self._payload(nav(), [300, 300, 0], [400, 400, 20])
        self.assertEqual(payload["bounds"]["nav"]["min"], [0.0, 0.0, 0.0])
        self.assertEqual(payload["bounds"]["collision"]["min"], [300.0, 300.0, 0.0])
        self.assertEqual(payload["bounds"]["scene"]["min"], [0.0, 0.0, 0.0])
        self.assertEqual(payload["bounds"]["scene"]["max"], [400.0, 400.0, 20.0])

    def test_nav_bounds_extend_beyond_collision(self) -> None:
        payload = self._payload(nav(), [0, 0, 0], [100, 100, 20])
        self.assertEqual(payload["bounds"]["nav"]["max"], [200.0, 100.0, 10.0])
        self.assertEqual(payload["bounds"]["collision"]["max"], [100.0, 100.0, 20.0])
        self.assertEqual(payload["bounds"]["scene"]["max"], [200.0, 100.0, 20.0])

    def test_scene_bounds_are_the_union_with_correct_center_and_size(self) -> None:
        payload = self._payload(nav(), [-50, -20, 0], [50, 20, 10])
        scene = payload["bounds"]["scene"]
        self.assertEqual(scene["min"], [-50.0, -20.0, 0.0])
        self.assertEqual(scene["max"], [200.0, 100.0, 10.0])
        self.assertEqual(scene["center"], [75.0, 40.0, 5.0])
        self.assertEqual(scene["size"], [250.0, 120.0, 10.0])

    def test_missing_nav_uses_collision_only(self) -> None:
        empty = NavMesh(
            version=36,
            sub_version=1,
            is_analyzed=True,
            places=[],
            has_unnamed_areas=False,
            areas=[],
            ladders=[],
        )
        payload = self._payload(empty, [10, 20, 30], [40, 50, 60])
        self.assertIsNone(payload["bounds"]["nav"])
        self.assertEqual(payload["bounds"]["collision"]["min"], [10.0, 20.0, 30.0])
        self.assertEqual(payload["bounds"]["scene"]["min"], [10.0, 20.0, 30.0])

    def test_missing_collision_uses_nav_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scene.gltf"
            data = minimal_gltf()
            data["nodes"] = []
            data["meshes"] = []
            data["scenes"] = [{"nodes": []}]
            path.write_text(json.dumps(data), encoding="utf-8")
            payload = build_payload(nav(), [], path, "test_map")
        self.assertIsNone(payload["bounds"]["collision"])
        self.assertEqual(payload["bounds"]["nav"]["min"], [0.0, 0.0, 0.0])
        self.assertEqual(payload["bounds"]["scene"]["max"], [200.0, 100.0, 10.0])

    def test_fit_view_and_grid_use_aggregate_scene_bounds(self) -> None:
        source = (VIEWER / "viewer.js").read_text(encoding="utf-8")
        fit = source[source.index("function fitView"):source.index("function topView")]
        grid = source[source.index("function addGrid"):source.index("function buildNav")]
        self.assertIn("sceneBounds(state.data)", fit)
        self.assertIn("sceneBounds(state.data)", grid)
        self.assertNotIn("data.bounds.center", fit)


class SceneBoundsHelperTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_scene_bounds_helper_returns_aggregate_bounds(self) -> None:
        script = (
            "import { sceneBounds } from "
            + json.dumps((VIEWER / "bounds.js").as_uri())
            + ";"
            "const b=sceneBounds({bounds:{scene:{min:[-5,-6,0],max:[10,20,30],"
            "center:[2.5,7,15],size:[15,26,30]}}});"
            "console.log(JSON.stringify(b));"
        )
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["center"], [2.5, 7, 15])
        self.assertEqual(data["size"], [15, 26, 30])
        self.assertEqual(data["min"], [-5, -6, 0])


class GltfSummaryCorrectnessTests(unittest.TestCase):
    def _summary(self, data: dict) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scene.gltf"
            path.write_text(json.dumps(data), encoding="utf-8")
            return gltf_summary(path)

    def _fixture(self) -> dict:
        return minimal_gltf()

    def test_multiple_primitives_keep_material_identity_and_clip(self) -> None:
        data = self._fixture()
        data["materials"] = [{"name": "solid_concrete"}, {"name": "physics_sky"}]
        data["accessors"].append(dict(data["accessors"][0]))
        data["accessors"].append(dict(data["accessors"][1]))
        data["meshes"][0]["primitives"] = [
            {"attributes": {"POSITION": 0}, "indices": 1, "material": 0},
            {"attributes": {"POSITION": 2}, "indices": 3, "material": 1},
        ]
        summary = self._summary(data)
        node = summary["nodes"][0]
        self.assertEqual(len(node["primitives"]), 2)
        self.assertEqual(
            [item["material"] for item in node["primitives"]],
            ["solid_concrete", "physics_sky"],
        )
        self.assertEqual(
            [item["material_index"] for item in node["primitives"]], [0, 1]
        )
        self.assertEqual([item["clip"] for item in node["primitives"]], [False, True])
        self.assertFalse(node["clip"])
        self.assertTrue(node["mixed_clip"])
        self.assertEqual(node["triangles"], 2)

    def test_translation_rotation_and_non_uniform_scale_are_applied_once(self) -> None:
        data = self._fixture()
        data["accessors"][0]["min"] = [0.0, 0.0, 0.0]
        data["accessors"][0]["max"] = [1.0, 2.0, 3.0]
        data["nodes"][0]["translation"] = [10.0, 20.0, 30.0]
        data["nodes"][0]["scale"] = [2.0, 3.0, 4.0]
        half = math.sin(math.pi / 4)
        data["nodes"][0]["rotation"] = [0.0, 0.0, half, half]
        node = self._summary(data)["nodes"][0]
        self.assertEqual(node["bounds"]["min"], [4.0, 20.0, 30.0])
        self.assertEqual(node["bounds"]["max"], [10.0, 22.0, 42.0])

    def test_nested_parent_child_transforms_are_composed(self) -> None:
        data = self._fixture()
        data["nodes"][0].pop("mesh")
        data["nodes"][0]["children"] = [1]
        data["nodes"][0]["translation"] = [10.0, 0.0, 0.0]
        data["nodes"].append(
            {
                "name": "child",
                "mesh": 0,
                "translation": [0.0, 20.0, 0.0],
            }
        )
        data["scenes"][0]["nodes"] = [0]
        node = self._summary(data)["nodes"][0]
        self.assertEqual(node["bounds"]["min"], [10.0, 20.0, 0.0])
        self.assertEqual(node["bounds"]["max"], [110.0, 120.0, 20.0])

    def test_explicit_matrix_is_used(self) -> None:
        data = self._fixture()
        data["nodes"][0]["matrix"] = [
            1, 0, 0, 0,
            0, 1, 0, 0,
            0, 0, 1, 0,
            5, 6, 7, 1,
        ]
        node = self._summary(data)["nodes"][0]
        self.assertEqual(node["bounds"]["min"], [5.0, 6.0, 7.0])
        self.assertEqual(node["bounds"]["max"], [105.0, 106.0, 27.0])

    def test_indexed_and_non_indexed_triangle_counts(self) -> None:
        indexed = self._summary(self._fixture())
        self.assertEqual(indexed["triangles"], 1)

        non_indexed = self._fixture()
        del non_indexed["meshes"][0]["primitives"][0]["indices"]
        summary = self._summary(non_indexed)
        self.assertEqual(summary["triangles"], 1)
        self.assertEqual(summary["nodes"][0]["primitives"][0]["mode"], 4)

    def test_invalid_accessor_and_index_references_are_rejected(self) -> None:
        invalid_index = self._fixture()
        invalid_index["meshes"][0]["primitives"][0]["indices"] = 99
        with self.assertRaisesRegex(ValueError, "accessor"):
            self._summary(invalid_index)

        missing_position = self._fixture()
        missing_position["meshes"][0]["primitives"][0]["attributes"] = {}
        with self.assertRaisesRegex(ValueError, "POSITION"):
            self._summary(missing_position)

        invalid_view = self._fixture()
        invalid_view["accessors"][0]["bufferView"] = 99
        with self.assertRaisesRegex(ValueError, "bufferView"):
            self._summary(invalid_view)

    def test_unsupported_primitive_mode_is_rejected(self) -> None:
        data = self._fixture()
        data["meshes"][0]["primitives"][0]["mode"] = 1
        with self.assertRaisesRegex(ValueError, "unsupported"):
            self._summary(data)

    def test_duplicate_node_names_keep_distinct_identities(self) -> None:
        data = self._fixture()
        data["nodes"].append({"name": "physics_group_concrete", "mesh": 0})
        data["scenes"][0]["nodes"] = [0, 1]
        summary = self._summary(data)
        self.assertEqual(len(summary["nodes"]), 2)
        self.assertEqual(
            [node["node_index"] for node in summary["nodes"]], [0, 1]
        )
        self.assertEqual(
            [node["node"] for node in summary["nodes"]],
            ["physics_group_concrete", "physics_group_concrete"],
        )


if __name__ == "__main__":
    unittest.main()
