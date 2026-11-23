#!/usr/bin/env python3
"""Probe a VRF-exported physics glTF and calibrate its axis convention.

This is a research tool. It loads only POSITION and index accessors from glTF,
then tests candidate mappings from glTF local coordinates to Source/Hammer
coordinates by comparing vertical collision hits with nav floor heights.

It does not build a BVH; it is intended for a handful of probe points, not
mass queries. Use a spatial index for the full floor test.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from array import array
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from nav_inspect import area_plane_z, find_area, parse_nav  # noqa: E402

COMPONENT = {5126: ("f", 4), 5123: ("H", 2), 5125: ("I", 4)}
CONVENTIONS = {
    "yxz": lambda x, y, z: (y, x, z),
    "ynegxz": lambda x, y, z: (y, -x, z),
    "xyz": lambda x, y, z: (x, y, z),
    "negyxz": lambda x, y, z: (-y, x, z),
    "negxy": lambda x, y, z: (-x, y, z),
}


@dataclass
class Primitive:
    material: str
    interact_as: tuple[str, ...]
    positions: array
    indices: array
    bounds_min: tuple[float, float, float]
    bounds_max: tuple[float, float, float]


def load_gltf(path: Path) -> list[Primitive]:
    gltf = json.loads(path.read_text(encoding="utf-8"))
    buffers = []
    for buffer in gltf["buffers"]:
        uri = buffer.get("uri")
        if not uri:
            raise ValueError("embedded glTF buffers are not supported")
        buffers.append((path.parent / uri).read_bytes())
    buffer = buffers[0]
    view_offset = [v.get("byteOffset", 0) for v in gltf["bufferViews"]]
    view_stride = [v.get("byteStride", 0) for v in gltf["bufferViews"]]

    def read_accessor(index: int) -> tuple[array, int]:
        acc = gltf["accessors"][index]
        bv = gltf["bufferViews"][acc["bufferView"]]
        comp_type = acc["componentType"]
        fmt, size = COMPONENT[comp_type]
        count = acc["count"]
        components = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[acc["type"]]
        stride = view_stride[acc["bufferView"]] or size * components
        start = view_offset[acc["bufferView"]] + acc.get("byteOffset", 0)
        values = array(fmt)
        for i in range(count):
            values.extend(struct.unpack_from("<" + fmt * components, buffer, start + i * stride))
        return values, components

    nodes = gltf.get("nodes", [])
    primitives: list[Primitive] = []
    for node in nodes:
        mesh_index = node.get("mesh")
        if mesh_index is None:
            continue
        mesh = gltf["meshes"][mesh_index]
        extras = node.get("extras", {})
        material_index = mesh["primitives"][0].get("material")
        material = (
            gltf["materials"][material_index].get("name", "")
            if material_index is not None
            else (extras.get("SurfaceProperty") or "unknown")
        )
        interact = tuple(extras.get("InteractAs") or [])
        for primitive in mesh["primitives"]:
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


def hits_at(
    primitives: list[Primitive],
    hammer_x: float,
    hammer_y: float,
    convention,
) -> list[tuple[float, str, tuple[str, ...]]]:
    hits: list[tuple[float, str, tuple[str, ...]]] = []
    for primitive in primitives:
        positions = primitive.positions
        indices = primitive.indices
        for i in range(0, len(indices), 3):
            ia, ib, ic = indices[i], indices[i + 1], indices[i + 2]
            pa = convention(positions[ia * 3], positions[ia * 3 + 1], positions[ia * 3 + 2])
            pb = convention(positions[ib * 3], positions[ib * 3 + 1], positions[ib * 3 + 2])
            pc = convention(positions[ic * 3], positions[ic * 3 + 1], positions[ic * 3 + 2])
            # 2D barycentric point-in-triangle in Hammer XY.
            v0x, v0y = pb[0] - pa[0], pb[1] - pa[1]
            v1x, v1y = pc[0] - pa[0], pc[1] - pa[1]
            den = v0x * v1y - v1x * v0y
            if abs(den) < 1e-7:
                continue
            px, py = hammer_x - pa[0], hammer_y - pa[1]
            u = (px * v1y - v1x * py) / den
            v = (v0x * py - px * v0y) / den
            if u < -1e-6 or v < -1e-6 or u + v > 1 + 1e-6:
                continue
            z = pa[2] + u * (pb[2] - pa[2]) + v * (pc[2] - pa[2])
            hits.append((z, primitive.material, primitive.interact_as))
    # Deduplicate nearly identical surfaces from adjacent triangles.
    hits.sort(key=lambda h: h[0])
    unique: list[tuple[float, str, tuple[str, ...]]] = []
    for hit in hits:
        if not unique or abs(hit[0] - unique[-1][0]) > 0.5:
            unique.append(hit)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gltf", type=Path)
    parser.add_argument("nav", type=Path)
    parser.add_argument("--point", nargs=3, type=float, action="append", required=True)
    parser.add_argument("--window", type=float, default=160.0)
    parser.add_argument(
        "--conventions",
        default="all",
        help="comma-separated convention names, or all",
    )
    args = parser.parse_args()

    primitives = load_gltf(args.gltf)
    print(f"primitives={len(primitives)} vertices={sum(len(p.positions)//3 for p in primitives)} "
          f"triangles={sum(len(p.indices)//3 for p in primitives)}")
    nav = parse_nav(args.nav)
    if args.conventions == "all":
        selected = CONVENTIONS
    else:
        selected = {name: CONVENTIONS[name] for name in args.conventions.split(",")}

    for point in args.point:
        area = find_area(nav, tuple(point))
        expected = area_plane_z(area, point[0], point[1]) if area else None
        print(f"\nPOINT {point} nav_area={area.area_id if area else None} nav_z={expected}")
        for name, convention in selected.items():
            hits = hits_at(primitives, point[0], point[1], convention)
            near = [h for h in hits if expected is not None and abs(h[0] - expected) <= args.window]
            print(f"  {name}: hits={len(hits)} near={len(near)}")
            for z, mat, interact in near[:8]:
                print(f"    z={z:8.2f} dz={z - expected:+7.2f} {mat} {interact}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
