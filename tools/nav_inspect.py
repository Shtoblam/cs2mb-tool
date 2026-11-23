#!/usr/bin/env python3
"""Read-only inspection of Source 2 .nav files (CS2 nav version 30-36).

This is a research tool, not a production nav library. The binary layout follows
ValveResourceFormat's NavMeshFile.cs / NavMeshArea.cs (MIT) and was checked
against the nav file shipped in the installed CS2 build.

It parses the header, polygon table, areas, connections and the global ladder
table. It intentionally stops before generation parameters and bot-analysis
KV3 data, which are not needed for graph experiments.

Reference:
https://github.com/ValveResourceFormat/ValveResourceFormat/tree/master/ValveResourceFormat/NavMesh
"""

from __future__ import annotations

import argparse
import heapq
import json
import math
import struct
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

MAGIC = 0xFEEDFACE
MIN_VERSION = 30
MAX_VERSION = 36
KV3_MAGIC_PREFIX = 0x4B563300
VEC3 = tuple[float, float, float]


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def take(self, n: int) -> bytes:
        if n < 0 or self.pos + n > len(self.data):
            raise ValueError(f"unexpected end of nav data at {self.pos} (+{n})")
        out = self.data[self.pos : self.pos + n]
        self.pos += n
        return out

    def skip(self, n: int) -> None:
        self.take(n)

    def u8(self) -> int:
        return self.take(1)[0]

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def i64(self) -> int:
        return struct.unpack("<q", self.take(8))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.take(4))[0]

    def vec3(self) -> VEC3:
        return (self.f32(), self.f32(), self.f32())

    def cstr(self) -> str:
        end = self.data.find(b"\0", self.pos)
        if end < 0:
            raise ValueError("unterminated string")
        raw = self.data[self.pos : end]
        self.pos = end + 1
        return raw.decode("utf-8", errors="replace")

    def align8(self) -> None:
        self.skip((8 - self.pos % 8) % 8)


def skip_kv3(r: Reader, label: str) -> dict[str, int | str]:
    """Skip an embedded binary KV3 document and return its header summary.

    The nav file only needs to step over these documents; their payload is not
    used for the navigation graph. This follows the on-disk layout used by
    BinaryKV3 and implements the same size calculation as Awpy's nav parser.
    """
    r.align8()
    start = r.pos
    magic = r.u32()
    if magic == 0x03564B56:
        raise ValueError(f"{label}: KV3 v0 is not supported")
    version = magic & 0xFF
    if magic & 0xFFFFFF00 != KV3_MAGIC_PREFIX or not 1 <= version <= 5:
        raise ValueError(f"{label}: bad KV3 signature {magic:#010x}")
    if version == 1:
        raise ValueError(f"{label}: KV3 v1 is not supported")

    r.skip(16)  # format GUID
    method = r.u32()
    r.skip(4)  # compression dictionary id + frame size
    r.skip(16)  # countBytes1/4/8 + countTypes
    r.skip(4)  # countObjects + countArrays
    size_unc_total = r.i32()
    size_cmp_total = r.i32()
    n_blocks = r.i32()
    n_blobs = r.i32()

    size_block_compressed = 0
    if version >= 4:
        r.skip(4)  # countBytes2
        size_block_compressed = r.i32()

    if version >= 5:
        unc1, cmp1, unc2, cmp2 = r.i32(), r.i32(), r.i32(), r.i32()
        r.skip(32)  # eight trailing buffer-2 count fields
    else:
        unc1, cmp1, unc2, cmp2 = size_unc_total, size_cmp_total, 0, 0

    if method > 2:
        raise ValueError(f"{label}: unsupported KV3 compression method {method}")
    if n_blocks != 0 or n_blobs != 0:
        raise ValueError(f"{label}: KV3 block/blob data is not supported")

    def on_disk(unc: int, cmp: int) -> int:
        return unc if method == 0 else cmp

    body = on_disk(unc1, cmp1) + on_disk(unc2, cmp2) + size_block_compressed
    if body < 0:
        raise ValueError(f"{label}: negative KV3 body size")
    r.skip(body)
    return {
        "label": label,
        "offset": start,
        "version": version,
        "method": method,
        "body_bytes": body,
        "end": r.pos,
    }


@dataclass
class Area:
    area_id: int
    attribute_flags: int
    hull_index: int
    corner_gravity: list[VEC3] | None
    corners: list[VEC3]
    connections: list[tuple[int, int]]
    hiding_spots: int
    ladders_above: list[int]
    ladders_below: list[int]

    @property
    def centroid(self) -> VEC3:
        n = len(self.corners)
        if n == 0:
            return (0.0, 0.0, 0.0)
        return tuple(sum(c[i] for c in self.corners) / n for i in range(3))  # type: ignore[return-value]

    @property
    def size_2d(self) -> float:
        n = len(self.corners)
        if n < 3:
            return 0.0
        twice = 0.0
        for i in range(n):
            x1, y1, _ = self.corners[i]
            x2, y2, _ = self.corners[(i + 1) % n]
            twice += x1 * y2 - x2 * y1
        return abs(twice) / 2.0


@dataclass
class Ladder:
    ladder_id: int
    width: float
    length: float
    top: VEC3
    bottom: VEC3
    direction: int
    top_forward_area: int
    top_left_area: int
    top_right_area: int
    top_behind_area: int
    bottom_area: int
    bottom_left_area: int | None
    bottom_right_area: int | None


@dataclass
class HullParams:
    enabled: bool
    radius: float
    height: float
    short_height_enabled: bool
    short_height: float
    agent_crawl_enabled: bool
    agent_crawl_height: float
    max_climb: float
    max_slope: int
    max_jump_down_dist: float
    max_jump_horiz_dist_base: float
    max_jump_up_dist: float
    border_erosion: int


@dataclass
class GenerationParams:
    nav_gen_version: int
    use_project_defaults: bool
    tile_size: float
    cell_size: float
    cell_height: float
    min_region_size: int
    merged_region_size: int
    mesh_sample_distance: float
    max_sample_error: float
    max_edge_length: int
    max_edge_error: float
    verts_per_poly: int
    small_area_on_edge_removal: float | None
    hull_preset_name: str | None
    hull_definitions_file: str | None
    hulls: list[HullParams]
    gravity_follows_rotation: bool


@dataclass
class NavMesh:
    version: int
    sub_version: int
    is_analyzed: bool
    places: list[str]
    has_unnamed_areas: bool
    areas: list[Area]
    ladders: list[Ladder]
    generation: GenerationParams | None = None
    kv3_documents: list[dict[str, int | str]] = field(default_factory=list)
    bytes_consumed: int = 0

    def by_id(self) -> dict[int, Area]:
        return {a.area_id: a for a in self.areas}


def parse_nav(path: Path) -> NavMesh:
    return parse_nav_bytes(path.read_bytes())


def parse_nav_bytes(data: bytes) -> NavMesh:
    r = Reader(data)
    magic = r.u32()
    if magic != MAGIC:
        raise ValueError(f"bad nav magic {magic:#010x}")
    version = r.u32()
    if not MIN_VERSION <= version <= MAX_VERSION:
        raise ValueError(f"unsupported nav version {version}")
    sub_version = r.u32()
    is_analyzed = r.u8() != 0

    place_count = r.u16()
    places = []
    for _ in range(place_count):
        length = r.u16()
        places.append(r.take(length).decode("utf-8", errors="replace").rstrip("\0"))
    has_unnamed_areas = r.u8() != 0

    kv3_docs: list[dict[str, int | str]] = []
    if version >= 36:
        kv3_docs.append(skip_kv3(r, "MovableMeshSettings"))

    polygons: list[tuple[list[VEC3], int]] = []
    if version >= 31:
        corner_count = r.u32()
        corners = [r.vec3() for _ in range(corner_count)]
        polygon_count = r.u32()
        for _ in range(polygon_count):
            n = r.u8()
            indices = [r.u32() for _ in range(n)]
            try:
                poly = [corners[i] for i in indices]
            except IndexError as exc:
                raise ValueError("polygon references a missing corner") from exc
            movable_mesh_id = r.u32() if version >= 35 else 0xFFFFFFFF
            polygons.append((poly, movable_mesh_id))

    if version >= 32:
        gravity_flags = r.u32()
        if gravity_flags & 1:
            gravity_count = r.u32()
            r.skip(12 * gravity_count)

    movable_meshes = []
    if version >= 35:
        movable_count = r.u32()
        for _ in range(movable_count):
            movable_meshes.append((r.cstr(), r.take(48)))

    if version >= 36:
        kv3_docs.append(skip_kv3(r, "GameData"))

    area_count = r.u32()
    areas: list[Area] = []
    for _ in range(area_count):
        area_id = r.u32()
        attribute_flags = r.i64()
        hull_index = r.u8()

        if version >= 31:
            polygon_index = r.u32()
            if polygon_index >= len(polygons):
                raise ValueError(f"area {area_id}: polygon index out of range")
            corners, _movable_mesh_id = polygons[polygon_index]
            corner_gravity = None
        else:
            corner_count = r.u32()
            corners = [r.vec3() for _ in range(corner_count)]
            corner_gravity = None

        r.skip(4)  # unused float, always zero in current files

        connections: list[tuple[int, int]] = []
        for _ in range(len(corners)):
            count = r.u32()
            for _ in range(count):
                connections.append((r.u32(), r.u32()))

        hiding_spot_count = r.u8()
        hiding_spots = []
        for _ in range(hiding_spot_count):
            spot_id = r.u32()
            spot_pos = r.vec3()
            spot_flags = r.u8()
            hiding_spots.append((spot_id, spot_pos, spot_flags))
        encounter_path_count = r.u32()
        if encounter_path_count:
            raise ValueError(f"area {area_id}: encounter paths are not supported")

        ladders_above = [r.u32() for _ in range(r.u32())]
        ladders_below = [r.u32() for _ in range(r.u32())]

        areas.append(
            Area(
                area_id=area_id,
                attribute_flags=attribute_flags,
                hull_index=hull_index,
                corner_gravity=corner_gravity,
                corners=corners,
                connections=connections,
                hiding_spots=len(hiding_spots),
                ladders_above=ladders_above,
                ladders_below=ladders_below,
            )
        )

    ladder_count = r.u32()
    ladders: list[Ladder] = []
    for _ in range(ladder_count):
        ladder_id = r.u32()
        width = r.f32()
        top = r.vec3()
        bottom = r.vec3()
        length = r.f32()
        direction = r.u32()
        top_forward = r.u32()
        top_left = r.u32()
        top_right = r.u32()
        top_behind = r.u32()
        bottom_area = r.u32()
        bottom_left = r.u32() if version >= 33 else None
        bottom_right = r.u32() if version >= 33 else None
        ladders.append(
            Ladder(
                ladder_id=ladder_id,
                width=width,
                length=length,
                top=top,
                bottom=bottom,
                direction=direction,
                top_forward_area=top_forward,
                top_left_area=top_left,
                top_right_area=top_right,
                top_behind_area=top_behind,
                bottom_area=bottom_area,
                bottom_left_area=bottom_left,
                bottom_right_area=bottom_right,
            )
        )

    # Unknown transformed bounds: count followed by 72 bytes per record.
    bounds_count = r.i32()
    r.skip(bounds_count * 72)

    generation = None
    if r.pos < len(r.data):
        nav_gen_version = r.i32()
        if nav_gen_version < 6:
            raise ValueError(f"unsupported nav generation version {nav_gen_version}")
        use_project_defaults = r.u32() != 0
        tile_size = r.f32()
        cell_size = r.f32()
        cell_height = r.f32()
        min_region_size = r.i32()
        merged_region_size = r.i32()
        mesh_sample_distance = r.f32()
        max_sample_error = r.f32()
        max_edge_length = r.i32()
        max_edge_error = r.f32()
        verts_per_poly = r.i32()
        small_area_on_edge_removal = r.f32() if nav_gen_version >= 7 else None
        hull_preset_name = r.cstr() if nav_gen_version >= 12 else None
        hull_definitions_file = r.cstr() if nav_gen_version >= 12 else None
        hull_count = r.i32()
        if nav_gen_version < 12:
            hull_count = 3
        hulls = []
        for _ in range(hull_count):
            enabled = r.u8() != 0 if nav_gen_version >= 9 else True
            radius = r.f32()
            height = r.f32()
            short_enabled = r.u8() != 0 if nav_gen_version >= 8 else False
            short_height = r.f32() if nav_gen_version >= 8 else 0.0
            crawl_enabled = r.u8() != 0 if nav_gen_version >= 13 else False
            crawl_height = r.f32() if nav_gen_version >= 13 else 0.0
            max_climb = r.f32()
            max_slope = r.i32()
            max_jump_down = r.f32()
            max_jump_horiz = r.f32()
            max_jump_up = r.f32()
            border_erosion = r.i32() if nav_gen_version >= 11 else 0
            hulls.append(
                HullParams(
                    enabled=enabled,
                    radius=radius,
                    height=height,
                    short_height_enabled=short_enabled,
                    short_height=short_height,
                    agent_crawl_enabled=crawl_enabled,
                    agent_crawl_height=crawl_height,
                    max_climb=max_climb,
                    max_slope=max_slope,
                    max_jump_down_dist=max_jump_down,
                    max_jump_horiz_dist_base=max_jump_horiz,
                    max_jump_up_dist=max_jump_up,
                    border_erosion=border_erosion,
                )
            )
        gravity_follows_rotation = r.u8() != 0 if nav_gen_version >= 10 else False
        generation = GenerationParams(
            nav_gen_version=nav_gen_version,
            use_project_defaults=use_project_defaults,
            tile_size=tile_size,
            cell_size=cell_size,
            cell_height=cell_height,
            min_region_size=min_region_size,
            merged_region_size=merged_region_size,
            mesh_sample_distance=mesh_sample_distance,
            max_sample_error=max_sample_error,
            max_edge_length=max_edge_length,
            max_edge_error=max_edge_error,
            verts_per_poly=verts_per_poly,
            small_area_on_edge_removal=small_area_on_edge_removal,
            hull_preset_name=hull_preset_name,
            hull_definitions_file=hull_definitions_file,
            hulls=hulls,
            gravity_follows_rotation=gravity_follows_rotation,
        )

        if version >= 36:
            kv3_docs.append(skip_kv3(r, "ExtraGenerationParams"))
        if sub_version > 0:
            kv3_docs.append(skip_kv3(r, "CustomData"))

    return NavMesh(
        version=version,
        sub_version=sub_version,
        is_analyzed=is_analyzed,
        places=places,
        has_unnamed_areas=has_unnamed_areas,
        areas=areas,
        ladders=ladders,
        generation=generation,
        kv3_documents=kv3_docs,
        bytes_consumed=r.pos,
    )


def point_in_poly_xy(area: Area, x: float, y: float) -> bool:
    inside = False
    n = len(area.corners)
    j = n - 1
    for i in range(n):
        xi, yi, _ = area.corners[i]
        xj, yj, _ = area.corners[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def area_candidates(nav: NavMesh, point: VEC3) -> list[dict]:
    """All nav areas containing (x, y), sorted by vertical distance to point.z."""
    candidates = []
    for area in nav.areas:
        if point_in_poly_xy(area, point[0], point[1]):
            plane_z = area_plane_z(area, point[0], point[1])
            candidates.append(
                {
                    "area": area,
                    "plane_z": plane_z,
                    "dz": point[2] - plane_z,
                }
            )
    candidates.sort(key=lambda item: abs(item["dz"]))
    return candidates


def find_area(nav: NavMesh, point: VEC3) -> Area | None:
    candidates = area_candidates(nav, point)
    return candidates[0]["area"] if candidates else None


def find_area_verbose(
    nav: NavMesh, point: VEC3, ambiguity: float = 64.0
) -> dict:
    """Point location with explicit vertical ambiguity information.

    A bridge over a tunnel or two stacked floors can contain the same (x, y).
    The closest plane is still returned, but the caller can inspect
    `ambiguous` and all candidates instead of silently assuming one floor.
    """
    candidates = area_candidates(nav, point)
    if not candidates:
        return {"area": None, "plane_z": None, "dz": None, "candidates": [], "ambiguous": False}
    best = candidates[0]
    ambiguous = any(
        abs(candidate["plane_z"] - point[2]) <= ambiguity
        for candidate in candidates[1:]
    )
    return {
        "area": best["area"],
        "plane_z": best["plane_z"],
        "dz": best["dz"],
        "candidates": [
            {
                "area_id": item["area"].area_id,
                "plane_z": item["plane_z"],
                "dz": item["dz"],
            }
            for item in candidates
        ],
        "ambiguous": ambiguous,
    }


def vertical_layers(
    nav: NavMesh, x: float, y: float, gap: float = 8.0
) -> list[dict]:
    """Distinct nav floor bands at an XY location, bottom to top."""
    floors = []
    for area in nav.areas:
        if point_in_poly_xy(area, x, y):
            floors.append((area_plane_z(area, x, y), area.area_id))
    floors.sort()
    layers: list[dict] = []
    for z, area_id in floors:
        if not layers or z - layers[-1]["z_max"] > gap:
            layers.append({"z_min": z, "z_max": z, "area_ids": [area_id]})
        else:
            layers[-1]["z_max"] = z
            layers[-1]["area_ids"].append(area_id)
    return [
        {
            "z": (layer["z_min"] + layer["z_max"]) / 2.0,
            "z_min": layer["z_min"],
            "z_max": layer["z_max"],
            "area_ids": layer["area_ids"],
        }
        for layer in layers
    ]


def dijkstra(nav: NavMesh, start: int, goal: int) -> tuple[list[int], float]:
    areas = nav.by_id()
    if start not in areas or goal not in areas:
        return [], math.inf
    dist: dict[int, float] = {start: 0.0}
    prev: dict[int, int] = {}
    heap: list[tuple[float, int]] = [(0.0, start)]
    while heap:
        cost, current = heapq.heappop(heap)
        if cost > dist.get(current, math.inf):
            continue
        if current == goal:
            break
        current_area = areas[current]
        for neighbor, _edge in current_area.connections:
            if neighbor not in areas:
                continue
            other = areas[neighbor]
            dx = other.centroid[0] - current_area.centroid[0]
            dy = other.centroid[1] - current_area.centroid[1]
            dz = other.centroid[2] - current_area.centroid[2]
            step = math.sqrt(dx * dx + dy * dy + dz * dz)
            new_cost = cost + step
            if new_cost < dist.get(neighbor, math.inf):
                dist[neighbor] = new_cost
                prev[neighbor] = current
                heapq.heappush(heap, (new_cost, neighbor))
    if goal not in dist:
        return [], math.inf
    path = [goal]
    while path[-1] != start:
        path.append(prev[path[-1]])
    path.reverse()
    return path, dist[goal]


def kosaraju_scc(nav: NavMesh) -> tuple[list[int], int]:
    ids = [a.area_id for a in nav.areas]
    id_set = set(ids)
    adjacency = {a.area_id: [n for n, _ in a.connections if n in id_set] for a in nav.areas}
    reverse: dict[int, list[int]] = defaultdict(list)
    for source, targets in adjacency.items():
        for target in targets:
            reverse[target].append(source)

    visited: set[int] = set()
    order: list[int] = []
    for root in ids:
        if root in visited:
            continue
        stack = [(root, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                order.append(node)
                continue
            if node in visited:
                continue
            visited.add(node)
            stack.append((node, True))
            for neighbor in adjacency.get(node, []):
                if neighbor not in visited:
                    stack.append((neighbor, False))

    visited.clear()
    sizes = []
    for root in reversed(order):
        if root in visited:
            continue
        size = 0
        stack = [root]
        visited.add(root)
        while stack:
            node = stack.pop()
            size += 1
            for neighbor in reverse.get(node, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        sizes.append(size)
    sizes.sort(reverse=True)
    return sizes, sizes[0] if sizes else 0


def undirected_components(nav: NavMesh) -> list[int]:
    areas = nav.by_id()
    adjacency: dict[int, set[int]] = {a.area_id: set() for a in nav.areas}
    for area in nav.areas:
        for neighbor, _ in area.connections:
            if neighbor in areas:
                adjacency[area.area_id].add(neighbor)
                adjacency[neighbor].add(area.area_id)
    seen: set[int] = set()
    sizes = []
    for root in adjacency:
        if root in seen:
            continue
        size = 0
        queue = [root]
        seen.add(root)
        while queue:
            node = queue.pop()
            size += 1
            for neighbor in adjacency[node]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        sizes.append(size)
    sizes.sort(reverse=True)
    return sizes


def summarize(nav: NavMesh) -> dict:
    ids = [a.area_id for a in nav.areas]
    areas = nav.by_id()
    dangling = [(a.area_id, n) for a in nav.areas for n, _ in a.connections if n not in areas]
    self_loops = [(a.area_id, n) for a in nav.areas for n, _ in a.connections if n == a.area_id]
    edge_count = sum(len(a.connections) for a in nav.areas)
    reciprocal = 0
    for area in nav.areas:
        for neighbor, _ in area.connections:
            if neighbor in areas and any(n == area.area_id for n, _ in areas[neighbor].connections):
                reciprocal += 1
    degrees = [len(a.connections) for a in nav.areas]
    sizes = sorted(a.size_2d for a in nav.areas)
    z_values = sorted(a.centroid[2] for a in nav.areas)
    components = undirected_components(nav)
    scc_sizes, largest_scc = kosaraju_scc(nav)
    ladder_ids = {l.ladder_id for l in nav.ladders}
    bad_ladder_refs = []
    for area in nav.areas:
        for lid in area.ladders_above + area.ladders_below:
            if lid not in ladder_ids:
                bad_ladder_refs.append((area.area_id, lid))
    large_vertical = [
        (a.area_id, n, round(areas[n].centroid[2] - a.centroid[2], 2))
        for a in nav.areas
        for n, _ in a.connections
        if n in areas and abs(areas[n].centroid[2] - a.centroid[2]) > 100
    ]
    return {
        "version": nav.version,
        "sub_version": nav.sub_version,
        "is_analyzed": nav.is_analyzed,
        "places": nav.places,
        "has_unnamed_areas": nav.has_unnamed_areas,
        "kv3_documents": nav.kv3_documents,
        "bytes_consumed_after_ladders": nav.bytes_consumed,
        "area_count": len(nav.areas),
        "area_id_min": min(ids),
        "area_id_max": max(ids),
        "duplicate_area_ids": [k for k, v in Counter(ids).items() if v > 1],
        "polygon_vertex_counts": dict(Counter(len(a.corners) for a in nav.areas)),
        "edge_count": edge_count,
        "distinct_edge_count": len({(a.area_id, n) for a in nav.areas for n, _ in a.connections}),
        "dangling_connections": len(dangling),
        "dangling_examples": dangling[:10],
        "self_loops": len(self_loops),
        "reciprocal_edge_fraction": round(reciprocal / edge_count, 4) if edge_count else None,
        "degree_min": min(degrees),
        "degree_max": max(degrees),
        "degree_mean": round(sum(degrees) / len(degrees), 3),
        "degree_histogram": dict(sorted(Counter(degrees).items())),
        "undirected_component_count": len(components),
        "undirected_component_sizes": components[:20],
        "scc_count": len(scc_sizes),
        "scc_sizes": scc_sizes,
        "largest_scc": largest_scc,
        "hull_index_counts": dict(sorted(Counter(a.hull_index for a in nav.areas).items())),
        "attribute_flags": dict(sorted(Counter(a.attribute_flags for a in nav.areas).items())),
        "areas_zero_size_2d": sum(1 for a in nav.areas if a.size_2d == 0.0),
        "area_size_2d_min": round(sizes[0], 3),
        "area_size_2d_median": round(sizes[len(sizes) // 2], 3),
        "area_size_2d_max": round(sizes[-1], 3),
        "z_min": round(z_values[0], 3),
        "z_median": round(z_values[len(z_values) // 2], 3),
        "z_max": round(z_values[-1], 3),
        "ladder_count": len(nav.ladders),
        "ladder_area_reference_errors": len(bad_ladder_refs),
        "areas_with_ladders_above": sum(bool(a.ladders_above) for a in nav.areas),
        "areas_with_ladders_below": sum(bool(a.ladders_below) for a in nav.areas),
        "connections_with_abs_dz_gt_100": len(large_vertical),
        "large_vertical_examples": large_vertical[:10],
        "bytes_consumed_total": nav.bytes_consumed,
        "generation": None
        if nav.generation is None
        else {
            "nav_gen_version": nav.generation.nav_gen_version,
            "use_project_defaults": nav.generation.use_project_defaults,
            "tile_size": nav.generation.tile_size,
            "cell_size": nav.generation.cell_size,
            "cell_height": nav.generation.cell_height,
            "min_region_size": nav.generation.min_region_size,
            "merged_region_size": nav.generation.merged_region_size,
            "verts_per_poly": nav.generation.verts_per_poly,
            "hull_preset_name": nav.generation.hull_preset_name,
            "hull_definitions_file": nav.generation.hull_definitions_file,
            "gravity_follows_rotation": nav.generation.gravity_follows_rotation,
            "hulls": [
                {
                    "enabled": h.enabled,
                    "radius": h.radius,
                    "height": h.height,
                    "short_height_enabled": h.short_height_enabled,
                    "short_height": h.short_height,
                    "agent_crawl_enabled": h.agent_crawl_enabled,
                    "agent_crawl_height": h.agent_crawl_height,
                    "max_climb": h.max_climb,
                    "max_slope": h.max_slope,
                    "max_jump_down_dist": h.max_jump_down_dist,
                    "max_jump_horiz_dist_base": h.max_jump_horiz_dist_base,
                    "max_jump_up_dist": h.max_jump_up_dist,
                    "border_erosion": h.border_erosion,
                }
                for h in nav.generation.hulls
            ],
        },
    }


def to_dot(nav: NavMesh) -> str:
    lines = ["digraph nav {", "  rankdir=LR;", "  node [shape=point];"]
    by_id = nav.by_id()
    for area in nav.areas:
        x, y, z = area.centroid
        lines.append(f'  a{area.area_id} [pos="{x:.1f},{y:.1f}!"];')
    for area in nav.areas:
        for neighbor, _ in area.connections:
            if neighbor in by_id:
                lines.append(f"  a{area.area_id} -> a{neighbor};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def to_svg(nav: NavMesh, path_area_ids: Iterable[int]) -> str:
    xs = [c[0] for a in nav.areas for c in a.corners]
    ys = [c[1] for a in nav.areas for c in a.corners]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    pad = 300.0
    min_x -= pad
    max_x += pad
    min_y -= pad
    max_y += pad
    width = max_x - min_x
    height = max_y - min_y
    scale = 1400.0 / max(width, height)
    out_w = width * scale
    out_h = height * scale

    def sx(x: float) -> float:
        return (x - min_x) * scale

    def sy(y: float) -> float:
        return out_h - (y - min_y) * scale

    zs = [a.centroid[2] for a in nav.areas]
    z_min, z_max = min(zs), max(zs)

    def color(z: float) -> str:
        t = (z - z_min) / (z_max - z_min) if z_max > z_min else 0.0
        # blue (low) to orange/red (high)
        r = int(40 + 200 * t)
        g = int(110 + 80 * t)
        b = int(220 - 170 * t)
        return f"rgb({r},{g},{b})"

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w:.0f}" height="{out_h:.0f}" '
        f'viewBox="0 0 {out_w:.0f} {out_h:.0f}">',
        '<rect width="100%" height="100%" fill="#101418"/>',
    ]
    for area in nav.areas:
        points = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y, _ in area.corners)
        parts.append(
            f'<polygon points="{points}" fill="{color(area.centroid[2])}" '
            f'fill-opacity="0.30" stroke="#8aa0b8" stroke-width="0.6"/>'
        )
    by_id = nav.by_id()
    path = [by_id[i] for i in path_area_ids if i in by_id]
    if path:
        points = " ".join(f"{sx(a.centroid[0]):.2f},{sy(a.centroid[1]):.2f}" for a in path)
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="#ffd166" '
            f'stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for i, area in enumerate(path):
            fill = "#ff4d4d" if i in (0, len(path) - 1) else "#ffd166"
            parts.append(
                f'<circle cx="{sx(area.centroid[0]):.2f}" cy="{sy(area.centroid[1]):.2f}" '
                f'r="5" fill="{fill}"/>'
            )
        parts.append(
            f'<text x="20" y="32" fill="#e8eef5" font-family="sans-serif" font-size="20">'
            f"{len(path)} nav areas, centroid-chain length {path_length(nav, [a.area_id for a in path]):.1f} units"
            f"</text>"
        )
    parts.append("</svg>")
    return "\n".join(parts)


def path_length(nav: NavMesh, ids: list[int]) -> float:
    """Sum of straight lines between area centroids (coarse upper estimate)."""
    by_id = nav.by_id()
    total = 0.0
    for a, b in zip(ids, ids[1:]):
        ca, cb = by_id[a].centroid, by_id[b].centroid
        total += math.sqrt(sum((ca[i] - cb[i]) ** 2 for i in range(3)))
    return total


def area_plane_z(area: Area, x: float, y: float) -> float:
    """Z of the area's best-fit plane at (x, y), with a centroid fallback."""
    nx = ny = nz = 0.0
    n = len(area.corners)
    for i, p in enumerate(area.corners):
        q = area.corners[(i + 1) % n]
        nx += (p[1] - q[1]) * (p[2] + q[2])
        ny += (p[2] - q[2]) * (p[0] + q[0])
        nz += (p[0] - q[0]) * (p[1] + q[1])
    if abs(nz) < 1e-9:
        return area.centroid[2]
    x0, y0, z0 = area.corners[0]
    return z0 - (nx * (x - x0) + ny * (y - y0)) / nz


def snap_to_area(area: Area, point: VEC3) -> VEC3:
    return (point[0], point[1], area_plane_z(area, point[0], point[1]))


def edge_midpoint(area: Area, edge_index: int) -> VEC3:
    n = len(area.corners)
    p, q = area.corners[edge_index % n], area.corners[(edge_index + 1) % n]
    return tuple((p[i] + q[i]) / 2.0 for i in range(3))  # type: ignore[return-value]


def connection_crossing(source: Area, target: Area) -> VEC3:
    """Crossing point for source -> target.

    The stored edge id belongs to the destination area, so the crossing is the
    midpoint of that destination edge. This was verified empirically on the
    installed Dust II nav: reciprocal target-edge midpoints coincide far more
    often than source-edge midpoints.
    """
    for neighbor, edge_id in source.connections:
        if neighbor == target.area_id:
            return edge_midpoint(target, edge_id)
    return target.centroid


def dijkstra_edges(
    nav: NavMesh,
    start: int,
    goal: int,
    start_point: VEC3 | None = None,
    end_point: VEC3 | None = None,
) -> tuple[list[int], float, list[VEC3]]:
    """Shortest route where the cost is the in-area broken-line distance.

    State is the directed transition (previous, current), because the cost of
    leaving an area depends on where the route entered it. This is a line-graph
    search over the nav connection graph. Crossing points use the destination
    edge midpoint.
    """
    by_id = nav.by_id()
    if start not in by_id or goal not in by_id:
        return [], math.inf, []

    first, last = by_id[start], by_id[goal]
    p0 = snap_to_area(first, start_point if start_point is not None else first.centroid)
    pn = snap_to_area(last, end_point if end_point is not None else last.centroid)

    if start == goal:
        return [start], math.dist(p0, pn), [p0, pn]

    # Cached entry point for a directed transition (previous -> current).
    entry_cache: dict[tuple[int, int], VEC3] = {}

    def entry(state: tuple[int, int]) -> VEC3:
        prev, current = state
        if prev == 0:
            return p0
        cached = entry_cache.get(state)
        if cached is None:
            cached = connection_crossing(by_id[prev], by_id[current])
            entry_cache[state] = cached
        return cached

    start_state = (0, start)
    dist: dict[tuple[int, int], float] = {start_state: 0.0}
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start_state: None}
    heap: list[tuple[float, tuple[int, int]]] = [(0.0, start_state)]
    final_state: tuple[int, int] | None = None
    final_cost = math.inf

    while heap:
        cost, state = heapq.heappop(heap)
        if cost > dist.get(state, math.inf):
            continue
        prev, current = state
        area = by_id[current]
        if current == goal:
            candidate = cost + math.dist(entry(state), pn)
            if candidate < final_cost:
                final_cost = candidate
                final_state = state
            # A later state can only be more expensive under a consistent metric.
            continue
        if cost >= final_cost:
            continue
        for neighbor, _edge_id in area.connections:
            if neighbor not in by_id:
                continue
            exit_point = connection_crossing(area, by_id[neighbor])
            step = math.dist(entry(state), exit_point)
            next_state = (current, neighbor)
            next_cost = cost + step
            if next_cost < dist.get(next_state, math.inf):
                dist[next_state] = next_cost
                previous[next_state] = state
                heapq.heappush(heap, (next_cost, next_state))

    if final_state is None:
        return [], math.inf, []

    states: list[tuple[int, int]] = []
    state: tuple[int, int] | None = final_state
    while state is not None:
        states.append(state)
        state = previous[state]
    states.reverse()

    path_ids = [states[0][1]] + [s[1] for s in states[1:]]
    points = [p0]
    for state in states[1:]:
        points.append(entry(state))
    points.append(pn)
    return path_ids, final_cost, points


def path_geometry_length(
    nav: NavMesh,
    ids: list[int],
    start_point: VEC3 | None = None,
    end_point: VEC3 | None = None,
) -> tuple[float, list[VEC3]]:
    """Length of the broken line start -> shared edges -> end.

    Convex nav areas make the straight segment between two boundary points
    stay inside the area. Using destination edge midpoints avoids the large
    overestimate produced by connecting area centroids.
    """
    by_id = nav.by_id()
    if not ids:
        return math.inf, []
    first, last = by_id[ids[0]], by_id[ids[-1]]
    p0 = start_point if start_point is not None else first.centroid
    pn = end_point if end_point is not None else last.centroid
    points = [snap_to_area(first, p0)]
    for a, b in zip(ids, ids[1:]):
        points.append(connection_crossing(by_id[a], by_id[b]))
    points.append(snap_to_area(last, pn))
    total = sum(math.dist(p, q) for p, q in zip(points, points[1:]))
    return total, points


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nav", type=Path)
    parser.add_argument("--json", action="store_true", help="print full JSON summary")
    parser.add_argument("--dot", type=Path, help="write graph as Graphviz DOT")
    parser.add_argument("--svg", type=Path, help="write nav polygons as SVG")
    parser.add_argument(
        "--route",
        nargs=6,
        type=float,
        metavar=("X1", "Y1", "Z1", "X2", "Y2", "Z2"),
        help="find the shortest area route between two world points",
    )
    parser.add_argument("--route-area", nargs=2, type=int, help="route between two area ids")
    args = parser.parse_args()

    nav = parse_nav(args.nav)
    summary = summarize(nav)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        for key, value in summary.items():
            print(f"{key}: {value}")

    path_ids: list[int] = []
    if args.route:
        p1 = tuple(args.route[:3])
        p2 = tuple(args.route[3:])
        a1 = find_area(nav, p1)  # type: ignore[arg-type]
        a2 = find_area(nav, p2)  # type: ignore[arg-type]
        if not a1 or not a2:
            print(f"route: no area at {p1 if not a1 else p2}", file=sys.stderr)
        else:
            centroid_path, centroid_cost = dijkstra(nav, a1.area_id, a2.area_id)
            path_ids, edge_cost, _ = dijkstra_edges(
                nav, a1.area_id, a2.area_id, p1, p2
            )
            print(
                f"route: {a1.area_id} -> {a2.area_id}, "
                f"{len(path_ids)} areas, centroid-path {len(centroid_path)} areas / "
                f"{centroid_cost:.2f} units, edge-optimal {edge_cost:.2f} units"
            )
    elif args.route_area:
        centroid_path, centroid_cost = dijkstra(nav, *args.route_area)
        path_ids, edge_cost, _ = dijkstra_edges(nav, *args.route_area)
        print(
            f"route: {args.route_area[0]} -> {args.route_area[1]}, "
            f"{len(path_ids)} areas, centroid-path {len(centroid_path)} areas / "
            f"{centroid_cost:.2f} units, edge-optimal {edge_cost:.2f} units"
        )
        if not path_ids:
            print("route: no path", file=sys.stderr)

    if args.dot:
        args.dot.parent.mkdir(parents=True, exist_ok=True)
        args.dot.write_text(to_dot(nav), encoding="utf-8")
        print(f"wrote {args.dot}")
    if args.svg:
        args.svg.parent.mkdir(parents=True, exist_ok=True)
        args.svg.write_text(to_svg(nav, path_ids), encoding="utf-8")
        print(f"wrote {args.svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
