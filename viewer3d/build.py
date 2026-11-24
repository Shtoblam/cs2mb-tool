"""Build the per-map 3DsVW data bundle from existing CS2MB outputs.

The bundle contains only project-generated data: a normalized glTF copy, its
binary sidecar, NAV polygons/links, filtered entity markers and representative
routes. No game resources are read here; the caller supplies prepared files.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import sys
import tempfile
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from nav_experiment import (  # noqa: E402
    SPAWN_CLASSES,
    TARGET_PLACES,
    resolve_area,
    route_between,
)
from nav_inspect import NavMesh, parse_nav, point_in_poly_xy  # noqa: E402

SCHEMA = "cs2mb.viewer3d/1"
VERSION = "1.0.0"
MAP_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
CLIP_TOKENS = {
    "playerclip",
    "npcclip",
    "grenadeclip",
    "csgo_grenadeclip",
    "passbullets",
    "sky",
}
REPRESENTATIVE_TARGETS = ("A", "B", "Mid")
MARKER_CLASSES = {
    "point_camera",
    "prop_physics_multiplayer",
    "func_brush",
    "func_buyzone",
    "func_bomb_target",
    "skybox_reference",
}
TEXT_KEYS = ("classname", "targetname", "place_name", "model", "target")


def _decode_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le", errors="replace")
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace")
    return raw.decode("utf-8", errors="replace")


def _vec3(value: str | None) -> list[float] | None:
    if not value:
        return None
    match = re.search(r"\[\s*([^\]]+)\]", value)
    if not match:
        return None
    try:
        parts = [float(part.strip()) for part in match.group(1).split(",")]
    except ValueError:
        return None
    if len(parts) != 3 or not all(math.isfinite(part) for part in parts):
        return None
    return [round(part, 2) for part in parts]


def _text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = "".join(ch for ch in value if ch >= " " and ch != "\x7f")
    return cleaned.strip()[:160]


def parse_entity_blocks(path: Path) -> list[dict[str, Any]]:
    """Parse the line-oriented SRI entity dump into bounded dictionaries."""
    entities: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for line in _decode_text(path).splitlines():
        if line.startswith("===="):
            if current:
                entities.append(current)
                current = {}
            continue
        match = re.match(r"^\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$", line)
        if not match:
            continue
        key, raw = match.group(1), match.group(2)
        if key == "origin":
            value = _vec3(raw)
            if value:
                current["origin"] = value
        elif key == "angles":
            value = _vec3(raw)
            if value:
                current["angles"] = value
        elif key in TEXT_KEYS:
            current[key] = _text(raw.strip().strip('"'))
    if current:
        entities.append(current)
    return [entity for entity in entities if entity.get("classname")]


def _identity_matrix() -> list[list[float]]:
    return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def _multiply_matrix(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [sum(left[row][k] * right[k][column] for k in range(4)) for column in range(4)]
        for row in range(4)
    ]


def _matrix_from_gltf(values: Any) -> list[list[float]]:
    if not isinstance(values, list) or len(values) != 16 or not all(
        isinstance(value, (int, float)) and math.isfinite(value) for value in values
    ):
        raise ValueError("glTF node matrix must contain 16 finite numbers")
    return [[float(values[column * 4 + row]) for column in range(4)] for row in range(4)]


def _node_matrix(node: dict[str, Any]) -> list[list[float]]:
    if "matrix" in node:
        return _matrix_from_gltf(node["matrix"])
    translation = node.get("translation", [0.0, 0.0, 0.0])
    rotation = node.get("rotation", [0.0, 0.0, 0.0, 1.0])
    scale = node.get("scale", [1.0, 1.0, 1.0])
    if (
        not isinstance(translation, list)
        or not isinstance(scale, list)
        or not isinstance(rotation, list)
        or len(translation) != 3
        or len(scale) != 3
        or len(rotation) != 4
        or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in translation + scale + rotation)
    ):
        raise ValueError("glTF node TRS is invalid")
    tx, ty, tz = (float(value) for value in translation)
    sx, sy, sz = (float(value) for value in scale)
    x, y, z, w = (float(value) for value in rotation)
    rotation_matrix = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0.0],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0.0],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]
    scale_matrix = [[sx, 0.0, 0.0, 0.0], [0.0, sy, 0.0, 0.0], [0.0, 0.0, sz, 0.0], [0.0, 0.0, 0.0, 1.0]]
    translation_matrix = [[1.0, 0.0, 0.0, tx], [0.0, 1.0, 0.0, ty], [0.0, 0.0, 1.0, tz], [0.0, 0.0, 0.0, 1.0]]
    return _multiply_matrix(_multiply_matrix(translation_matrix, rotation_matrix), scale_matrix)


def _transform_point(matrix: list[list[float]], point: list[float]) -> list[float]:
    return [
        matrix[row][0] * point[0]
        + matrix[row][1] * point[1]
        + matrix[row][2] * point[2]
        + matrix[row][3]
        for row in range(3)
    ]


def _transform_bounds(matrix: list[list[float]], minimum: list[float], maximum: list[float]) -> dict[str, list[float]]:
    corners = [
        [minimum[0] if x == 0 else maximum[0], minimum[1] if y == 0 else maximum[1], minimum[2] if z == 0 else maximum[2]]
        for x in (0, 1)
        for y in (0, 1)
        for z in (0, 1)
    ]
    transformed = [_transform_point(matrix, corner) for corner in corners]
    return {
        "min": [min(point[axis] for point in transformed) for axis in range(3)],
        "max": [max(point[axis] for point in transformed) for axis in range(3)],
    }


def _accessor_ref(accessor_index: Any, accessors: list[dict[str, Any]], gltf: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(accessor_index, int) or accessor_index < 0 or accessor_index >= len(accessors):
        raise ValueError("glTF primitive references an invalid accessor")
    accessor = accessors[accessor_index]
    if not isinstance(accessor, dict):
        raise ValueError("glTF accessor is invalid")
    buffer_view_index = accessor.get("bufferView")
    buffer_views = gltf.get("bufferViews", [])
    if not isinstance(buffer_view_index, int) or buffer_view_index < 0 or buffer_view_index >= len(buffer_views):
        raise ValueError("glTF accessor references an invalid bufferView")
    view = buffer_views[buffer_view_index]
    buffer_index = view.get("buffer", 0)
    buffers = gltf.get("buffers", [])
    if not isinstance(buffer_index, int) or buffer_index < 0 or buffer_index >= len(buffers):
        raise ValueError("glTF bufferView references an invalid buffer")
    byte_offset = int(view.get("byteOffset", 0))
    byte_length = int(view.get("byteLength", 0))
    buffer_length = int(buffers[buffer_index].get("byteLength", 0))
    if byte_offset < 0 or byte_length <= 0 or byte_offset + byte_length > buffer_length:
        raise ValueError("glTF bufferView is outside its buffer")
    return accessor


def _position_bounds(accessor_index: Any, accessors: list[dict[str, Any]], gltf: dict[str, Any]) -> tuple[list[float], list[float]]:
    accessor = _accessor_ref(accessor_index, accessors, gltf)
    count = accessor.get("count")
    if (
        accessor.get("componentType") != 5126
        or accessor.get("type") != "VEC3"
        or not isinstance(count, int)
        or count <= 0
    ):
        raise ValueError("glTF POSITION accessor must be VEC3 float32")
    minimum = accessor.get("min")
    maximum = accessor.get("max")
    if (
        not isinstance(minimum, list)
        or not isinstance(maximum, list)
        or len(minimum) != 3
        or len(maximum) != 3
        or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in minimum + maximum)
    ):
        raise ValueError("glTF POSITION accessor has no valid bounds")
    return [float(value) for value in minimum], [float(value) for value in maximum]


def _index_count(accessor_index: Any, accessors: list[dict[str, Any]], gltf: dict[str, Any]) -> int:
    accessor = _accessor_ref(accessor_index, accessors, gltf)
    count = accessor.get("count")
    if (
        accessor.get("componentType") not in {5121, 5123, 5125}
        or accessor.get("type") != "SCALAR"
        or not isinstance(count, int)
        or count < 0
    ):
        raise ValueError("glTF index accessor must be an unsigned scalar")
    return count


def _primitive_triangles(primitive: dict[str, Any], accessors: list[dict[str, Any]], gltf: dict[str, Any]) -> int:
    mode = primitive.get("mode", 4)
    if not isinstance(mode, int) or mode not in {4, 5, 6}:
        raise ValueError(f"unsupported glTF primitive mode: {mode!r}")
    attributes = primitive.get("attributes")
    if not isinstance(attributes, dict) or "POSITION" not in attributes:
        raise ValueError("glTF primitive has no POSITION attribute")
    count = (
        _index_count(primitive["indices"], accessors, gltf)
        if primitive.get("indices") is not None
        else int(_accessor_ref(attributes["POSITION"], accessors, gltf)["count"])
    )
    if mode == 4:
        if count % 3 != 0:
            raise ValueError("indexed TRIANGLES count is not a multiple of three")
        return count // 3
    return max(0, count - 2)


def _scene_world_matrices(gltf: dict[str, Any]) -> dict[int, list[list[float]]]:
    nodes = gltf.get("nodes", [])
    scenes = gltf.get("scenes", [])
    parent_indices = set()
    for node in nodes:
        for child in node.get("children", []):
            parent_indices.add(child)
    if scenes:
        scene_index = gltf.get("scene", 0)
        if not isinstance(scene_index, int) or scene_index < 0 or scene_index >= len(scenes):
            raise ValueError("glTF scene index is invalid")
        roots = scenes[scene_index].get("nodes", [])
    else:
        roots = [index for index in range(len(nodes)) if index not in parent_indices]
    worlds: dict[int, list[list[float]]] = {}

    def walk(index: int, parent: list[list[float]], stack: set[int]) -> None:
        if not isinstance(index, int) or index < 0 or index >= len(nodes):
            raise ValueError("glTF node child index is invalid")
        if index in stack or len(stack) > 256:
            raise ValueError("glTF node hierarchy contains a cycle")
        node = nodes[index]
        world = _multiply_matrix(parent, _node_matrix(node))
        worlds[index] = world
        stack.add(index)
        for child in node.get("children", []):
            walk(child, world, stack)
        stack.remove(index)

    for root in roots:
        walk(root, _identity_matrix(), set())
    return worlds


def gltf_summary(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    accessors = data.get("accessors", [])
    meshes = data.get("meshes", [])
    materials = data.get("materials", [])
    nodes = data.get("nodes", [])
    worlds = _scene_world_matrices(data)
    node_rows: list[dict[str, Any]] = []
    collision_min = [math.inf, math.inf, math.inf]
    collision_max = [-math.inf, -math.inf, -math.inf]
    total_triangles = 0

    for node_index in sorted(worlds):
        node = nodes[node_index]
        mesh_index = node.get("mesh")
        if mesh_index is None:
            continue
        if not isinstance(mesh_index, int) or mesh_index < 0 or mesh_index >= len(meshes):
            raise ValueError("glTF node references an invalid mesh")
        mesh = meshes[mesh_index]
        extras = node.get("extras") or {}
        interact = [str(item) for item in extras.get("InteractAs") or []]
        primitives = []
        node_min = [math.inf, math.inf, math.inf]
        node_max = [-math.inf, -math.inf, -math.inf]
        node_triangles = 0
        for primitive_index, primitive in enumerate(mesh.get("primitives", [])):
            if not isinstance(primitive, dict):
                raise ValueError("glTF mesh primitive is invalid")
            attributes = primitive.get("attributes")
            if not isinstance(attributes, dict) or "POSITION" not in attributes:
                raise ValueError("glTF primitive has no POSITION attribute")
            local_min, local_max = _position_bounds(attributes["POSITION"], accessors, data)
            material_index = primitive.get("material")
            if material_index is not None and (
                not isinstance(material_index, int)
                or material_index < 0
                or material_index >= len(materials)
            ):
                raise ValueError("glTF primitive references an invalid material")
            material_name = (
                str(materials[material_index].get("name") or "")
                if material_index is not None
                else ""
            )
            is_clip = (
                bool(set(interact) & CLIP_TOKENS)
                or "clip" in material_name.lower()
                or "sky" in material_name.lower()
            )
            world_bounds = _transform_bounds(worlds[node_index], local_min, local_max)
            triangles = _primitive_triangles(primitive, accessors, data)
            primitives.append(
                {
                    "index": primitive_index,
                    "material_index": material_index,
                    "material": material_name,
                    "surface": str(extras.get("SurfaceProperty") or ""),
                    "interactAs": interact,
                    "collisionGroup": str(extras.get("CollisionGroup") or ""),
                    "mode": primitive.get("mode", 4),
                    "triangles": triangles,
                    "bounds": {
                        "min": [round(value, 2) for value in world_bounds["min"]],
                        "max": [round(value, 2) for value in world_bounds["max"]],
                    },
                    "clip": is_clip,
                }
            )
            node_min = [min(node_min[axis], world_bounds["min"][axis]) for axis in range(3)]
            node_max = [max(node_max[axis], world_bounds["max"][axis]) for axis in range(3)]
            node_triangles += triangles
            total_triangles += triangles
        if any(math.isinf(value) for value in node_min):
            continue
        collision_min = [min(collision_min[axis], node_min[axis]) for axis in range(3)]
        collision_max = [max(collision_max[axis], node_max[axis]) for axis in range(3)]
        first = primitives[0] if primitives else {}
        node_rows.append(
            {
                "node_index": node_index,
                "name": first.get("material", ""),
                "node": str(node.get("name") or ""),
                "surface": str(extras.get("SurfaceProperty") or ""),
                "interactAs": interact,
                "collisionGroup": str(extras.get("CollisionGroup") or ""),
                "triangles": node_triangles,
                "clip": bool(primitives) and all(item["clip"] for item in primitives),
                "mixed_clip": any(item["clip"] for item in primitives)
                and not all(item["clip"] for item in primitives),
                "bounds": {
                    "min": [round(value, 2) for value in node_min],
                    "max": [round(value, 2) for value in node_max],
                },
                "primitives": primitives,
            }
        )

    collision_bounds = None
    if not any(math.isinf(value) for value in collision_min):
        collision_bounds = {
            "min": [round(value, 2) for value in collision_min],
            "max": [round(value, 2) for value in collision_max],
        }
    return {
        "bounds": collision_bounds,
        "bounds_mode": "world-space transformed accessor AABB (conservative for rotation and scale)",
        "triangles": total_triangles,
        "nodes": node_rows,
        "materials": len(materials),
        "meshes": len(meshes),
    }


def nav_payload(nav: NavMesh) -> dict[str, Any]:
    areas = []
    edges = []
    all_corners: list[list[float]] = []
    for area in nav.areas:
        corners = [[round(x, 2), round(y, 2), round(z, 2)] for x, y, z in area.corners]
        all_corners.extend(corners)
        areas.append(
            {
                "id": area.area_id,
                "flags": area.attribute_flags,
                "hull": area.hull_index,
                "corners": corners,
                "center": [round(value, 2) for value in area.centroid],
            }
        )
        for destination, _edge in area.connections:
            edges.append([area.area_id, int(destination)])
    z_values = [corner[2] for corner in all_corners] or [0.0]
    nav_bounds = None
    if all_corners:
        nav_bounds = {
            "min": [round(min(corner[axis] for corner in all_corners), 2) for axis in range(3)],
            "max": [round(max(corner[axis] for corner in all_corners), 2) for axis in range(3)],
        }
    return {
        "areas": areas,
        "edges": edges,
        "bounds": nav_bounds,
        "count": len(areas),
        "edge_count": len(edges),
        "z_min": round(min(z_values), 2),
        "z_max": round(max(z_values), 2),
    }


def _select_targets(nav: NavMesh, entities: list[dict[str, Any]]) -> dict[str, Any]:
    places: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        if entity.get("classname") == "env_cs_place" and entity.get("place_name"):
            places[entity["place_name"]].append(entity)
    targets: dict[str, Any] = {}
    for place_name, label in TARGET_PLACES.items():
        candidates = []
        for entity in places.get(place_name, []):
            origin = entity.get("origin")
            if not origin:
                continue
            area = resolve_area(nav, tuple(origin))
            candidates.append((area, entity))
        if not candidates:
            continue
        containing = [
            (area, entity)
            for area, entity in candidates
            if point_in_poly_xy(area, entity["origin"][0], entity["origin"][1])
        ]
        area, entity = max(containing or candidates, key=lambda item: item[0].size_2d)
        targets[label] = {
            "label": label,
            "place_name": place_name,
            "area_id": area.area_id,
            "center": [round(value, 2) for value in area.centroid],
            "origin": entity["origin"],
        }
    return targets


def route_payload(nav: NavMesh, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spawns: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entity in entities:
        side = SPAWN_CLASSES.get(entity.get("classname", ""))
        if side and entity.get("origin"):
            spawns[side].append(entity)
    targets = _select_targets(nav, entities)
    by_id = nav.by_id()
    routes: list[dict[str, Any]] = []
    for side in ("CT", "T"):
        for label in REPRESENTATIVE_TARGETS:
            target = targets.get(label)
            if not target:
                continue
            candidates: list[tuple[float, list[tuple[float, float, float]]]] = []
            for spawn in spawns.get(side, []):
                area = resolve_area(nav, tuple(spawn["origin"]))
                _ids, cost, points = route_between(
                    nav,
                    area,
                    by_id[target["area_id"]],
                    tuple(spawn["origin"]),
                )
                if math.isfinite(cost):
                    candidates.append((cost, points))
            if not candidates:
                continue
            candidates.sort(key=lambda item: item[0])
            cost, points = candidates[len(candidates) // 2]
            routes.append(
                {
                    "side": side,
                    "target": label,
                    "distance": round(cost, 1),
                    "points": [
                        [round(x, 1), round(y, 1), round(z + 4.0, 1)] for x, y, z in points
                    ],
                }
            )
    return routes


def _bounds_payload(minimum: list[float], maximum: list[float]) -> dict[str, list[float]]:
    return {
        "min": [round(value, 2) for value in minimum],
        "max": [round(value, 2) for value in maximum],
        "center": [round((minimum[axis] + maximum[axis]) / 2, 2) for axis in range(3)],
        "size": [round(maximum[axis] - minimum[axis], 2) for axis in range(3)],
    }


def build_payload(
    nav: NavMesh,
    entities: list[dict[str, Any]],
    gltf_path: Path,
    map_name: str,
) -> dict[str, Any]:
    summary = gltf_summary(gltf_path)
    nav_data = nav_payload(nav)
    targets = _select_targets(nav, entities)
    spawns = [
        {
            "side": SPAWN_CLASSES[entity["classname"]],
            "origin": entity["origin"],
            "angles": entity.get("angles") or [0.0, 0.0, 0.0],
            "targetname": entity.get("targetname", ""),
        }
        for entity in entities
        if entity.get("classname") in SPAWN_CLASSES and entity.get("origin")
    ]
    markers = [
        {
            "classname": entity["classname"],
            "targetname": entity.get("targetname", ""),
            "origin": entity["origin"],
            "angles": entity.get("angles") or [0.0, 0.0, 0.0],
        }
        for entity in entities
        if entity.get("classname") in MARKER_CLASSES
        and entity.get("origin")
        and any(abs(value) > 0.01 for value in entity["origin"])
    ][:300]
    collision_bounds = summary.get("bounds")
    nav_bounds = nav_data.get("bounds")
    available = [value for value in (collision_bounds, nav_bounds) if value]
    if available:
        scene_min = [min(value["min"][axis] for value in available) for axis in range(3)]
        scene_max = [max(value["max"][axis] for value in available) for axis in range(3)]
    else:
        scene_min = [0.0, 0.0, 0.0]
        scene_max = [1.0, 1.0, 1.0]
    scene_bounds = _bounds_payload(scene_min, scene_max)
    bounds = {
        "collision": collision_bounds,
        "nav": nav_bounds,
        "scene": scene_bounds,
        **scene_bounds,
    }
    routes = route_payload(nav, entities)
    return {
        "schema": SCHEMA,
        "viewer_version": VERSION,
        "map": map_name,
        "source": {
            "collision": "SRI PHYS glTF",
            "navigation": "CS2 NAV",
            "entities": "SRI EntityLump",
            "note": "Collision-derived geometry. Not render world, materials or textures.",
        },
        "bounds": bounds,
        "stats": {
            "nav_areas": nav_data["count"],
            "nav_edges": nav_data["edge_count"],
            "collision_triangles": summary["triangles"],
            "collision_nodes": len(summary["nodes"]),
            "materials": summary["materials"],
            "entities": len(entities),
            "spawns": len(spawns),
            "routes": len(routes),
        },
        "nav": nav_data,
        "entities": {
            "spawns": spawns,
            "places": list(targets.values()),
            "markers": markers,
            "targets": list(targets.values()),
        },
        "routes": routes,
        "collision": {
            "scene": "scene.gltf",
            "bin": "scene.bin",
            "bounds_mode": summary.get("bounds_mode", ""),
            "nodes": summary["nodes"],
        },
    }


def _validate_bundle(bundle: Path, payload: dict[str, Any], map_name: str) -> None:
    """Validate a completed staged bundle before it can replace a valid one."""
    data_path = bundle / "data.json"
    scene_path = bundle / "scene.gltf"
    bin_path = bundle / "scene.bin"
    for path in (data_path, scene_path, bin_path):
        if not path.is_file() or path.stat().st_size <= 0:
            raise ValueError(f"viewer bundle is incomplete: {path.name}")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or data.get("map") != map_name:
        raise ValueError("viewer bundle payload is invalid")
    if data.get("collision", {}).get("scene") != "scene.gltf":
        raise ValueError("viewer bundle scene reference is invalid")
    if data.get("collision", {}).get("bin") != "scene.bin":
        raise ValueError("viewer bundle sidecar reference is invalid")
    if data.get("stats", {}).get("collision_triangles") != payload["stats"]["collision_triangles"]:
        raise ValueError("viewer bundle statistics are inconsistent")
    buffers = scene.get("buffers") or []
    if len(buffers) != 1 or buffers[0].get("uri") != "scene.bin":
        raise ValueError("viewer bundle glTF buffer is invalid")
    byte_length = int(buffers[0].get("byteLength") or 0)
    if byte_length != bin_path.stat().st_size:
        raise ValueError("viewer bundle sidecar length is inconsistent")
    for view in scene.get("bufferViews", []):
        if view.get("buffer", 0) != 0 or int(view.get("byteLength", 0)) <= 0:
            raise ValueError("viewer bundle glTF bufferView is invalid")
    if scene.get("images") or scene.get("textures"):
        raise ValueError("viewer bundle contains texture references")


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except OSError:
            pass


def _replace_bundle(staging: Path, target: Path) -> None:
    """Swap a validated bundle into place, restoring the old bundle on failure."""
    backup = target.parent / f".{target.name}.backup-{uuid.uuid4().hex}"
    moved_old = False
    try:
        if target.exists() or target.is_symlink():
            os.replace(target, backup)
            moved_old = True
        os.replace(staging, target)
    except Exception:
        if moved_old and not target.exists() and backup.exists():
            try:
                os.replace(backup, target)
            except OSError:
                # Keep the backup rather than deleting the last known-good copy.
                raise RuntimeError(
                    f"viewer replacement failed; previous bundle preserved at {backup.name}"
                )
        raise
    else:
        if moved_old:
            _remove_path(backup)


def build_viewer3d(
    nav_path: Path,
    entities_path: Path,
    gltf_path: Path,
    out_dir: Path,
    map_name: str,
) -> dict[str, Any]:
    """Write viewer3d/data.json, scene.gltf and scene.bin; return a summary."""
    if not MAP_RE.fullmatch(map_name):
        raise ValueError("invalid map name")
    nav = parse_nav(nav_path)
    entities = parse_entity_blocks(entities_path)
    if gltf_path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("glTF file is too large for the viewer")
    gltf = json.loads(gltf_path.read_text(encoding="utf-8"))
    buffers = gltf.get("buffers") or []
    if len(buffers) != 1:
        raise ValueError("glTF must contain exactly one binary buffer")
    uri = str(buffers[0].get("uri") or "")
    source_bin = (gltf_path.parent / uri).resolve()
    if (
        not uri
        or "://" in uri
        or uri.startswith(("/", "\\"))
        or not source_bin.is_file()
        or not source_bin.is_relative_to(gltf_path.parent.resolve())
    ):
        raise ValueError("glTF binary sidecar is missing or outside the input directory")
    if source_bin.stat().st_size > 220 * 1024 * 1024:
        raise ValueError("glTF binary sidecar is too large for the viewer")
    byte_length = int(buffers[0].get("byteLength") or 0)
    if byte_length > 0 and byte_length != source_bin.stat().st_size:
        raise ValueError("glTF buffer length does not match the binary sidecar")
    if len(gltf.get("nodes", [])) > 20000 or len(gltf.get("accessors", [])) > 200000:
        raise ValueError("glTF has too many nodes or accessors")
    payload = build_payload(nav, entities, gltf_path, map_name)
    if payload["stats"]["collision_triangles"] > 4000000:
        raise ValueError("collision geometry is too large for the viewer")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "viewer3d"
    staging = Path(tempfile.mkdtemp(prefix=".viewer3d-", dir=str(out_dir)))
    try:
        gltf["buffers"][0]["uri"] = "scene.bin"
        for buffer_view in gltf.get("bufferViews", []):
            buffer_view.setdefault("buffer", 0)
        # The viewer needs geometry only. Drop texture/image references so a
        # malformed or uploaded glTF cannot trigger remote or unexpected fetches.
        for key in ("images", "textures", "samplers", "animations", "skins"):
            gltf.pop(key, None)
        for node in gltf.get("nodes", []):
            node.pop("skin", None)
            node.pop("camera", None)
        if gltf.get("extensionsRequired"):
            raise ValueError("glTF requires unsupported extensions")
        gltf["materials"] = [
            {"name": str(material.get("name") or "")}
            for material in gltf.get("materials", [])
        ]
        (staging / "scene.gltf").write_text(
            json.dumps(gltf, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        shutil.copy2(source_bin, staging / "scene.bin")
        (staging / "data.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        _validate_bundle(staging, payload, map_name)
        _replace_bundle(staging, target)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)

    def display(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    return {
        "ok": True,
        "map": map_name,
        "data": display(target / "data.json"),
        "scene": display(target / "scene.gltf"),
        "bytes": (target / "data.json").stat().st_size,
        "nav_areas": payload["stats"]["nav_areas"],
        "routes": payload["stats"]["routes"],
        "triangles": payload["stats"]["collision_triangles"],
    }
