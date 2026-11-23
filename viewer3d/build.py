"""Build the per-map 3DsVW data bundle from existing CS2MB outputs.

The bundle contains only project-generated data: a normalized glTF copy, its
binary sidecar, NAV polygons/links, filtered entity markers and representative
routes. No game resources are read here; the caller supplies prepared files.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import sys
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


def gltf_summary(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    accessors = data.get("accessors", [])
    meshes = data.get("meshes", [])
    materials = data.get("materials", [])
    nodes = data.get("nodes", [])
    node_rows: list[dict[str, Any]] = []
    solid_min = [math.inf, math.inf, math.inf]
    solid_max = [-math.inf, -math.inf, -math.inf]
    all_min = [math.inf, math.inf, math.inf]
    all_max = [-math.inf, -math.inf, -math.inf]
    total_triangles = 0

    for node in nodes:
        mesh_index = node.get("mesh")
        if mesh_index is None or mesh_index >= len(meshes):
            continue
        mesh = meshes[mesh_index]
        extras = node.get("extras") or {}
        interact = [str(item) for item in extras.get("InteractAs") or []]
        material_name = ""
        node_min = [math.inf, math.inf, math.inf]
        node_max = [-math.inf, -math.inf, -math.inf]
        node_triangles = 0
        for primitive in mesh.get("primitives", []):
            material_index = primitive.get("material")
            if material_index is not None and material_index < len(materials):
                material_name = str(materials[material_index].get("name") or "")
            position_index = (primitive.get("attributes") or {}).get("POSITION")
            if position_index is not None and position_index < len(accessors):
                accessor = accessors[position_index]
                if accessor.get("min") and accessor.get("max"):
                    node_min = [min(a, b) for a, b in zip(node_min, accessor["min"])]
                    node_max = [max(a, b) for a, b in zip(node_max, accessor["max"])]
            index_index = primitive.get("indices")
            if index_index is not None and index_index < len(accessors):
                count = int(accessors[index_index].get("count", 0)) // 3
                node_triangles += count
                total_triangles += count
        is_clip = (
            bool(set(interact) & CLIP_TOKENS)
            or "clip" in material_name
            or "sky" in material_name
        )
        if not any(math.isinf(value) for value in node_min):
            all_min = [min(a, b) for a, b in zip(all_min, node_min)]
            all_max = [max(a, b) for a, b in zip(all_max, node_max)]
            if not is_clip:
                solid_min = [min(a, b) for a, b in zip(solid_min, node_min)]
                solid_max = [max(a, b) for a, b in zip(solid_max, node_max)]
        node_rows.append(
            {
                "name": material_name,
                "node": str(node.get("name") or ""),
                "surface": str(extras.get("SurfaceProperty") or ""),
                "interactAs": interact,
                "collisionGroup": str(extras.get("CollisionGroup") or ""),
                "triangles": node_triangles,
                "clip": is_clip,
            }
        )

    if any(math.isinf(value) for value in all_min):
        bounds_min, bounds_max = [0.0, 0.0, 0.0], [1.0, 1.0, 1.0]
    else:
        bounds_min, bounds_max = all_min, all_max
    if not any(math.isinf(value) for value in solid_min):
        bounds_min, bounds_max = solid_min, solid_max
    return {
        "bounds": {
            "min": [round(value, 2) for value in bounds_min],
            "max": [round(value, 2) for value in bounds_max],
        },
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
    return {
        "areas": areas,
        "edges": edges,
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
    bounds = summary["bounds"]
    nav_corners = [corner for area in nav_data["areas"] for corner in area["corners"]]
    if nav_corners:
        nav_min = [min(c[axis] for c in nav_corners) for axis in range(3)]
        nav_max = [max(c[axis] for c in nav_corners) for axis in range(3)]
        pad_x = max(64.0, (nav_max[0] - nav_min[0]) * 0.04)
        pad_y = max(64.0, (nav_max[1] - nav_min[1]) * 0.04)
        bounds = {
            "min": [round(nav_min[0] - pad_x, 2), round(nav_min[1] - pad_y, 2), round(nav_min[2] - 128.0, 2)],
            "max": [round(nav_max[0] + pad_x, 2), round(nav_max[1] + pad_y, 2), round(nav_max[2] + 128.0, 2)],
        }
    center = [round((bounds["min"][i] + bounds["max"][i]) / 2, 2) for i in range(3)]
    size = [round(bounds["max"][i] - bounds["min"][i], 2) for i in range(3)]
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
        "bounds": {"min": bounds["min"], "max": bounds["max"], "center": center, "size": size},
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
            "nodes": summary["nodes"],
        },
    }


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
    target = out_dir / "viewer3d"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
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
    (target / "scene.gltf").write_text(
        json.dumps(gltf, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    shutil.copy2(source_bin, target / "scene.bin")
    (target / "data.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

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
