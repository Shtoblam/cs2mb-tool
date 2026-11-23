#!/usr/bin/env python3
"""Load VRF physics glTF and build a simple 2D triangle index for floor queries.

Coordinate convention was calibrated on Dust2: glTF accessor positions are
already Hammer units with Source axes (x, y, z-up). The glTF node matrix is a
render-time conversion to meters/Y-up and must be ignored for analysis.
"""

from __future__ import annotations

import json
import math
import struct
from array import array
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

COMPONENT = {5126: ("f", 4), 5123: ("H", 2), 5125: ("I", 4)}


@dataclass
class Primitive:
    material: str
    interact_as: tuple[str, ...]
    positions: array
    indices: array
    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]


def load_gltf_primitives(path: Path) -> list[Primitive]:
    gltf = json.loads(path.read_text(encoding="utf-8"))
    buffers = []
    for buffer in gltf["buffers"]:
        uri = buffer.get("uri")
        if not uri:
            raise ValueError("embedded glTF buffers are not supported")
        buffers.append((path.parent / uri).read_bytes())
    blob = buffers[0]
    view_offset = [v.get("byteOffset", 0) for v in gltf["bufferViews"]]
    view_stride = [v.get("byteStride", 0) for v in gltf["bufferViews"]]

    def read_accessor(index: int) -> tuple[array, int]:
        acc = gltf["accessors"][index]
        comp_type = acc["componentType"]
        fmt, size = COMPONENT[comp_type]
        count = acc["count"]
        components = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
        stride = view_stride[acc["bufferView"]] or size * components
        start = view_offset[acc["bufferView"]] + acc.get("byteOffset", 0)
        values = array(fmt)
        for i in range(count):
            values.extend(struct.unpack_from("<" + fmt * components, blob, start + i * stride))
        return values, components

    primitives: list[Primitive] = []
    for node in gltf.get("nodes", []):
        mesh_index = node.get("mesh")
        if mesh_index is None:
            continue
        extras = node.get("extras", {})
        interact = tuple(extras.get("InteractAs") or [])
        for primitive in gltf["meshes"][mesh_index]["primitives"]:
            material_index = primitive.get("material")
            material = (
                gltf["materials"][material_index].get("name", "")
                if material_index is not None
                else (extras.get("SurfaceProperty") or "unknown")
            )
            pos, components = read_accessor(primitive["attributes"]["POSITION"])
            if components != 3:
                raise ValueError("POSITION is not VEC3")
            idx, _ = read_accessor(primitive["indices"])
            accessor = gltf["accessors"][primitive["attributes"]["POSITION"]]
            primitives.append(
                Primitive(
                    material=material,
                    interact_as=interact,
                    positions=pos,
                    indices=idx,
                    bounds_min=tuple(accessor["min"]),
                    bounds_max=tuple(accessor["max"]),
                )
            )
    return primitives


def wall_segments(
    primitives: list[Primitive],
    min_length: float = 12.0,
    max_abs_normal_z: float = 0.35,
    quantize: float = 2.0,
) -> set[tuple[tuple[float, float], tuple[float, float]]]:
    """Extract projected wall footprint segments from collision triangles.

    Invisible clip materials and sky are skipped. The lowest edge of each
    near-vertical triangle is used as its floor footprint; shared edges are
    deduplicated after quantizing endpoints.
    """
    segments: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    for primitive in primitives:
        if any(tag in {"sky", "csgo_grenadeclip", "npcclip", "playerclip"} for tag in primitive.interact_as):
            continue
        if "clip" in primitive.material or "sky" in primitive.material:
            continue
        positions = primitive.positions
        indices = primitive.indices
        for i in range(0, len(indices), 3):
            ia, ib, ic = indices[i], indices[i + 1], indices[i + 2]
            p1 = (positions[ia * 3], positions[ia * 3 + 1], positions[ia * 3 + 2])
            p2 = (positions[ib * 3], positions[ib * 3 + 1], positions[ib * 3 + 2])
            p3 = (positions[ic * 3], positions[ic * 3 + 1], positions[ic * 3 + 2])
            ux, uy, uz = p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]
            vx, vy, vz = p3[0] - p1[0], p3[1] - p1[1], p3[2] - p1[2]
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            if length < 1e-9 or abs(nz / length) > max_abs_normal_z:
                continue
            edges = ((p1, p2), (p2, p3), (p3, p1))
            edge = min(
                edges,
                key=lambda e: (
                    (e[0][2] + e[1][2]) / 2.0,
                    -math.hypot(e[1][0] - e[0][0], e[1][1] - e[0][1]),
                ),
            )
            a, b = edge
            if math.hypot(b[0] - a[0], b[1] - a[1]) < min_length:
                continue

            def q(p: tuple[float, float, float]) -> tuple[float, float]:
                return (
                    round(p[0] / quantize) * quantize,
                    round(p[1] / quantize) * quantize,
                )

            qa, qb = q(a), q(b)
            if qa == qb:
                continue
            if qa > qb:
                qa, qb = qb, qa
            segments.add((qa, qb))
    return segments


class TriangleIndex:
    """Uniform 2D grid over triangle XY bounds.

    Only vertical floor queries are supported: given (x, y), return the z of
    every triangle whose XY projection contains the point.
    """

    def __init__(
        self,
        primitives: list[Primitive],
        cell_size: float = 128.0,
        exclude_interact: set[str] | None = None,
    ):
        exclude_interact = exclude_interact or {"sky", "csgo_grenadeclip"}
        self.cell_size = cell_size
        self.tri_vertices = array("f")
        self.triangle_count = 0
        self.triangle_material: list[str] = []
        self.grid: dict[tuple[int, int], list[int]] = defaultdict(list)
        self.bounds_min = [float("inf")] * 3
        self.bounds_max = [float("-inf")] * 3

        for primitive in primitives:
            if exclude_interact.intersection(primitive.interact_as):
                continue
            positions = primitive.positions
            indices = primitive.indices
            for i in range(0, len(indices), 3):
                ia, ib, ic = indices[i], indices[i + 1], indices[i + 2]
                verts = (
                    positions[ia * 3], positions[ia * 3 + 1], positions[ia * 3 + 2],
                    positions[ib * 3], positions[ib * 3 + 1], positions[ib * 3 + 2],
                    positions[ic * 3], positions[ic * 3 + 1], positions[ic * 3 + 2],
                )
                self.tri_vertices.extend(verts)
                self.triangle_material.append(primitive.material)
                self.triangle_count += 1
        # Bounds must be known before the grid cell coordinates can be
        # computed; build bounds and grid in a second pass over the compact
        # triangle array.
        self.bounds_min = [float("inf")] * 3
        self.bounds_max = [float("-inf")] * 3
        for i in range(self.triangle_count):
            base = i * 9
            xs = self.tri_vertices[base : base + 9 : 3]
            ys = self.tri_vertices[base + 1 : base + 9 : 3]
            zs = self.tri_vertices[base + 2 : base + 9 : 3]
            for axis, values in enumerate((xs, ys, zs)):
                lo, hi = min(values), max(values)
                if lo < self.bounds_min[axis]:
                    self.bounds_min[axis] = lo
                if hi > self.bounds_max[axis]:
                    self.bounds_max[axis] = hi
        for i in range(self.triangle_count):
            base = i * 9
            x1, y1, _, x2, y2, _, x3, y3, _ = self.tri_vertices[base : base + 9]
            min_cx = int((min(x1, x2, x3) - self.bounds_min[0]) // cell_size)
            max_cx = int((max(x1, x2, x3) - self.bounds_min[0]) // cell_size)
            min_cy = int((min(y1, y2, y3) - self.bounds_min[1]) // cell_size)
            max_cy = int((max(y1, y2, y3) - self.bounds_min[1]) // cell_size)
            for cx in range(min_cx, max_cx + 1):
                for cy in range(min_cy, max_cy + 1):
                    self.grid[(cx, cy)].append(i)

    def hits_at(
        self,
        x: float,
        y: float,
        dedupe: float = 0.5,
        horizontal_only: bool = False,
        min_abs_normal_z: float = 0.5,
        exclude_substrings: set[str] | None = None,
    ) -> list[float]:
        if not self.triangle_count:
            return []
        cx = int((x - self.bounds_min[0]) // self.cell_size)
        cy = int((y - self.bounds_min[1]) // self.cell_size)
        candidates = self.grid.get((cx, cy))
        if not candidates:
            return []
        hits: list[float] = []
        verts = self.tri_vertices
        for tri in candidates:
            if exclude_substrings and any(
                token in self.triangle_material[tri]
                for token in exclude_substrings
            ):
                continue
            base = tri * 9
            x1, y1, z1, x2, y2, z2, x3, y3, z3 = verts[base : base + 9]
            den = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
            if abs(den) < 1e-7:
                continue
            if horizontal_only:
                ux, uy, uz = x2 - x1, y2 - y1, z2 - z1
                vx, vy, vz = x3 - x1, y3 - y1, z3 - z1
                nx = uy * vz - uz * vy
                ny = uz * vx - ux * vz
                nz = ux * vy - uy * vx
                length = math.sqrt(nx * nx + ny * ny + nz * nz)
                if length < 1e-9 or abs(nz / length) < min_abs_normal_z:
                    continue
            px, py = x - x1, y - y1
            u = (px * (y3 - y1) - (x3 - x1) * py) / den
            v = ((x2 - x1) * py - px * (y2 - y1)) / den
            if u < -1e-6 or v < -1e-6 or u + v > 1 + 1e-6:
                continue
            hits.append(z1 + u * (z2 - z1) + v * (z3 - z1))
        hits.sort()
        unique: list[float] = []
        for z in hits:
            if not unique or abs(z - unique[-1]) > dedupe:
                unique.append(z)
        return unique

    def nearest_z(
        self,
        x: float,
        y: float,
        target_z: float,
        horizontal_only: bool = False,
        min_abs_normal_z: float = 0.5,
    ) -> tuple[float, float] | None:
        hits = self.hits_at(x, y, horizontal_only=horizontal_only, min_abs_normal_z=min_abs_normal_z)
        if not hits:
            return None
        best = min(hits, key=lambda z: abs(z - target_z))
        return best, best - target_z

    @staticmethod
    def _cross(ax: float, ay: float, bx: float, by: float) -> float:
        return ax * by - ay * bx

    @staticmethod
    def _point_segment_distance(
        px: float,
        py: float,
        ax: float,
        ay: float,
        bx: float,
        by: float,
    ) -> float:
        vx, vy = bx - ax, by - ay
        length2 = vx * vx + vy * vy
        if length2 < 1e-12:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / length2))
        return math.hypot(px - (ax + t * vx), py - (ay + t * vy))

    @classmethod
    def _segment_distance_2d(
        cls,
        a: tuple[float, float],
        b: tuple[float, float],
        c: tuple[float, float],
        d: tuple[float, float],
    ) -> float:
        if cls._segments_intersect(a, b, c, d):
            return 0.0
        return min(
            cls._point_segment_distance(a[0], a[1], c[0], c[1], d[0], d[1]),
            cls._point_segment_distance(b[0], b[1], c[0], c[1], d[0], d[1]),
            cls._point_segment_distance(c[0], c[1], a[0], a[1], b[0], b[1]),
            cls._point_segment_distance(d[0], d[1], a[0], a[1], b[0], b[1]),
        )

    @classmethod
    def _segments_intersect(
        cls,
        a: tuple[float, float],
        b: tuple[float, float],
        c: tuple[float, float],
        d: tuple[float, float],
    ) -> bool:
        def orient(p, q, r):
            return cls._cross(q[0] - p[0], q[1] - p[1], r[0] - p[0], r[1] - p[1])

        o1 = orient(a, b, c)
        o2 = orient(a, b, d)
        o3 = orient(c, d, a)
        o4 = orient(c, d, b)
        eps = 1e-7
        if (o1 > eps and o2 < -eps or o1 < -eps and o2 > eps) and (
            o3 > eps and o4 < -eps or o3 < -eps and o4 > eps
        ):
            return True
        # Collinear/touching cases are treated as blocked only when the
        # candidate point lies inside the segment bounds.
        if abs(o1) <= eps and min(a[0], b[0]) - eps <= c[0] <= max(a[0], b[0]) + eps and min(a[1], b[1]) - eps <= c[1] <= max(a[1], b[1]) + eps:
            return True
        if abs(o2) <= eps and min(a[0], b[0]) - eps <= d[0] <= max(a[0], b[0]) + eps and min(a[1], b[1]) - eps <= d[1] <= max(a[1], b[1]) + eps:
            return True
        if abs(o3) <= eps and min(c[0], d[0]) - eps <= a[0] <= max(c[0], d[0]) + eps and min(c[1], d[1]) - eps <= a[1] <= max(c[1], d[1]) + eps:
            return True
        if abs(o4) <= eps and min(c[0], d[0]) - eps <= b[0] <= max(c[0], d[0]) + eps and min(c[1], d[1]) - eps <= b[1] <= max(c[1], d[1]) + eps:
            return True
        return False

    def horizontal_clearance(
        self,
        x: float,
        y: float,
        z: float,
        max_dist: float = 64.0,
    ) -> tuple[float, str | None]:
        """Nearest collision wall distance at height z (point-to-slice)."""
        if not self.triangle_count:
            return max_dist, None
        cells = int(math.ceil(max_dist / self.cell_size)) + 1
        cx = int((x - self.bounds_min[0]) // self.cell_size)
        cy = int((y - self.bounds_min[1]) // self.cell_size)
        candidates: set[int] = set()
        for ix in range(cx - cells, cx + cells + 1):
            for iy in range(cy - cells, cy + cells + 1):
                candidates.update(self.grid.get((ix, iy), ()))
        nearest = max_dist
        nearest_material = None
        verts = self.tri_vertices
        eps = 1e-6
        for tri in candidates:
            base = tri * 9
            x1, y1, z1, x2, y2, z2, x3, y3, z3 = verts[base : base + 9]
            dz = (z1 - z, z2 - z, z3 - z)
            if all(d > eps for d in dz) or all(d < -eps for d in dz):
                continue
            if all(abs(d) <= eps for d in dz):
                continue
            pts: list[tuple[float, float]] = []
            for i, (xi, yi) in enumerate(((x1, y1), (x2, y2), (x3, y3))):
                if abs(dz[i]) <= eps:
                    pts.append((xi, yi))
            for i, j in ((0, 1), (1, 2), (2, 0)):
                if (dz[i] < -eps and dz[j] > eps) or (dz[i] > eps and dz[j] < -eps):
                    t = dz[i] / (dz[i] - dz[j])
                    pts.append(
                        (
                            (x1, x2, x3)[i] + t * ((x1, x2, x3)[j] - (x1, x2, x3)[i]),
                            (y1, y2, y3)[i] + t * ((y1, y2, y3)[j] - (y1, y2, y3)[i]),
                        )
                    )
            if len(pts) < 2:
                continue
            ax, ay = pts[0]
            bx, by = pts[-1]
            vx, vy = bx - ax, by - ay
            wx, wy = x - ax, y - ay
            seg_len2 = vx * vx + vy * vy
            if seg_len2 < eps:
                dist = math.hypot(wx, wy)
            else:
                t = max(0.0, min(1.0, (wx * vx + wy * vy) / seg_len2))
                dist = math.hypot(x - (ax + t * vx), y - (ay + t * vy))
            if dist < nearest:
                nearest = dist
                nearest_material = self.triangle_material[tri]
        return nearest, nearest_material

    def vertical_clearance(
        self,
        x: float,
        y: float,
        floor_hint: float,
        floor_tolerance: float = 48.0,
        exclude_substrings: set[str] | None = None,
    ) -> tuple[float, float | None, float | None]:
        """Return (floor_z, ceiling_z, gap). Ceiling None means open above."""
        hits = self.hits_at(
            x,
            y,
            dedupe=2.0,
            horizontal_only=True,
            exclude_substrings=exclude_substrings,
        )
        if not hits:
            return floor_hint, None, math.inf
        floor_z = min(hits, key=lambda z: abs(z - floor_hint))
        if abs(floor_z - floor_hint) > floor_tolerance:
            floor_z = floor_hint
        above = [z for z in hits if z > floor_z + 1.0]
        ceiling = min(above) if above else None
        gap = (ceiling - floor_z) if ceiling is not None else math.inf
        return floor_z, ceiling, gap

    def segment_blocked_2d(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        z: float,
    ) -> list[str]:
        """Materials whose triangle crosses the horizontal segment at z.

        The segment is projected to XY; each triangle is sliced by the plane
        z=const, producing a 2D segment. This is a wall/doorway check, not a
        full player-capsule collision test.
        """
        if not self.triangle_count:
            return []
        min_x, max_x = sorted((p1[0], p2[0]))
        min_y, max_y = sorted((p1[1], p2[1]))
        cx0 = int((min_x - self.bounds_min[0]) // self.cell_size)
        cx1 = int((max_x - self.bounds_min[0]) // self.cell_size)
        cy0 = int((min_y - self.bounds_min[1]) // self.cell_size)
        cy1 = int((max_y - self.bounds_min[1]) // self.cell_size)
        candidates: set[int] = set()
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                candidates.update(self.grid.get((cx, cy), ()))
        materials: list[str] = []
        verts = self.tri_vertices
        eps = 1e-6
        for tri in candidates:
            base = tri * 9
            x1, y1, z1, x2, y2, z2, x3, y3, z3 = verts[base : base + 9]
            dz = (z1 - z, z2 - z, z3 - z)
            if all(d > eps for d in dz) or all(d < -eps for d in dz):
                continue
            if all(abs(d) <= eps for d in dz):
                continue
            pts: list[tuple[float, float]] = []
            for i, (xi, yi) in enumerate(((x1, y1), (x2, y2), (x3, y3))):
                if abs(dz[i]) <= eps:
                    pts.append((xi, yi))
            for i, j in ((0, 1), (1, 2), (2, 0)):
                if (dz[i] < -eps and dz[j] > eps) or (dz[i] > eps and dz[j] < -eps):
                    t = dz[i] / (dz[i] - dz[j])
                    pts.append(
                        (
                            (x1, x2, x3)[i] + t * ((x1, x2, x3)[j] - (x1, x2, x3)[i]),
                            (y1, y2, y3)[i] + t * ((y1, y2, y3)[j] - (y1, y2, y3)[i]),
                        )
                    )
            if len(pts) < 2:
                continue
            if self._segments_intersect(p1, p2, pts[0], pts[-1]):
                material = self.triangle_material[tri]
                if material not in materials:
                    materials.append(material)
        return materials

    def segment_capsule_clearance_2d(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        z: float,
        max_dist: float = 16.0,
        max_abs_normal_z: float = 0.5,
    ) -> tuple[float, str | None]:
        """Nearest near-vertical wall distance from a path at height ``z``.

        The path is swept in XY; this is a horizontal capsule check, not a full
        3D capsule. Sloped floors/ceilings are ignored by the normal-z filter.
        The caller must separately check vertical clearance.
        """
        if not self.triangle_count:
            return max_dist, None
        min_x, max_x = sorted((p1[0], p2[0]))
        min_y, max_y = sorted((p1[1], p2[1]))
        min_x -= max_dist
        max_x += max_dist
        min_y -= max_dist
        max_y += max_dist
        cx0 = int((min_x - self.bounds_min[0]) // self.cell_size)
        cx1 = int((max_x - self.bounds_min[0]) // self.cell_size)
        cy0 = int((min_y - self.bounds_min[1]) // self.cell_size)
        cy1 = int((max_y - self.bounds_min[1]) // self.cell_size)
        candidates: set[int] = set()
        for cx in range(cx0, cx1 + 1):
            for cy in range(cy0, cy1 + 1):
                candidates.update(self.grid.get((cx, cy), ()))
        nearest = max_dist
        nearest_material = None
        verts = self.tri_vertices
        eps = 1e-6
        for tri in candidates:
            base = tri * 9
            x1, y1, z1, x2, y2, z2, x3, y3, z3 = verts[base : base + 9]
            ux, uy, uz = x2 - x1, y2 - y1, z2 - z1
            vx, vy, vz = x3 - x1, y3 - y1, z3 - z1
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            normal_length = math.sqrt(nx * nx + ny * ny + nz * nz)
            if normal_length < 1e-9 or abs(nz / normal_length) > max_abs_normal_z:
                continue
            dz = (z1 - z, z2 - z, z3 - z)
            if all(d > eps for d in dz) or all(d < -eps for d in dz):
                continue
            if all(abs(d) <= eps for d in dz):
                continue
            pts: list[tuple[float, float]] = []
            for i, (xi, yi) in enumerate(((x1, y1), (x2, y2), (x3, y3))):
                if abs(dz[i]) <= eps:
                    pts.append((xi, yi))
            for i, j in ((0, 1), (1, 2), (2, 0)):
                if (dz[i] < -eps and dz[j] > eps) or (dz[i] > eps and dz[j] < -eps):
                    t = dz[i] / (dz[i] - dz[j])
                    pts.append(
                        (
                            (x1, x2, x3)[i] + t * ((x1, x2, x3)[j] - (x1, x2, x3)[i]),
                            (y1, y2, y3)[i] + t * ((y1, y2, y3)[j] - (y1, y2, y3)[i]),
                        )
                    )
            if len(pts) < 2:
                continue
            distance = self._segment_distance_2d(p1, p2, pts[0], pts[-1])
            if distance < nearest:
                nearest = distance
                nearest_material = self.triangle_material[tri]
        return nearest, nearest_material

    def segment_capsule_blocked_2d(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        z: float,
        radius: float = 16.0,
        max_abs_normal_z: float = 0.5,
    ) -> list[str]:
        """Return the nearest blocking material, if a wall is within radius."""
        distance, material = self.segment_capsule_clearance_2d(
            p1,
            p2,
            z,
            max_dist=radius,
            max_abs_normal_z=max_abs_normal_z,
        )
        if material is not None and distance <= radius + 1e-6:
            return [material]
        return []
