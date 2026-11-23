#!/usr/bin/env python3
"""Minimal Dust II feasibility experiment on real CS2 data.

Inputs:
  - a .nav extracted from the installed map VPK
  - an `resourceinfo -all` dump of the map's .vents_c entity lump

The script:
  - extracts spawn points and env_cs_place callouts from the entity dump
  - maps them onto nav areas
  - computes edge-aware shortest routes from every spawn to Mid/A/B
  - reports distance distributions and route diagnostics
  - optionally writes an SVG overview with representative routes

Distances are Hammer units. No travel times are produced because movement
parameters for the installed CS2 build have not been measured yet.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from nav_inspect import (
    Area,
    NavMesh,
    area_plane_z,
    connection_crossing,
    dijkstra_edges,
    edge_midpoint,
    find_area,
    parse_nav,
    point_in_poly_xy,
)

SPAWN_CLASSES = {
    "info_player_terrorist": "T",
    "info_player_counterterrorist": "CT",
}
TARGET_PLACES = {
    "Middle": "Mid",
    "BombsiteA": "A",
    "BombsiteB": "B",
    "LongA": "LongA",
    "Catwalk": "Catwalk",
    "MidDoors": "MidDoors",
    "BDoors": "BDoors",
}


@dataclass
class EntityPoint:
    classname: str
    origin: tuple[float, float, float]
    place_name: str | None = None
    targetname: str | None = None


def parse_entity_points(path: Path) -> list[EntityPoint]:
    """Line-oriented parse of the resourceinfo text dump.

    resourceinfo prints each entity's values one per line; origin follows
    classname within the same keyValues3Data block. This is intentionally a
    dump parser, not a Source 2 resource parser.
    """
    points: list[EntityPoint] = []
    classname: str | None = None
    place_name: str | None = None
    targetname: str | None = None
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        text = raw[2:].decode("utf-16-le", errors="replace")
    elif raw.startswith(b"\xfe\xff"):
        text = raw[2:].decode("utf-16-be", errors="replace")
    elif raw.startswith(b"\xef\xbb\xbf"):
        text = raw.decode("utf-8-sig", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(r'classname\s*=\s*"([^"]+)"', stripped)
        if match:
            classname = match.group(1)
            continue
        match = re.match(r'place_name\s*=\s*"([^"]+)"', stripped)
        if match:
            place_name = match.group(1)
            continue
        match = re.match(r'targetname\s*=\s*"([^"]+)"', stripped)
        if match:
            targetname = match.group(1)
            continue
        match = re.match(r"origin\s*=\s*\[\s*([^\]]+)\]", stripped)
        if match and classname is not None:
            values = [float(x.strip()) for x in match.group(1).split(",")]
            if len(values) == 3:
                points.append(
                    EntityPoint(
                        classname=classname,
                        origin=(values[0], values[1], values[2]),
                        place_name=place_name,
                        targetname=targetname,
                    )
                )
            classname = None
            place_name = None
            targetname = None
    return points


def nearest_area_2d(nav: NavMesh, point: tuple[float, float, float]) -> Area:
    """Nearest area by distance to centroid, used only when point-in-poly fails."""
    return min(
        nav.areas,
        key=lambda a: math.hypot(a.centroid[0] - point[0], a.centroid[1] - point[1]),
    )


def resolve_area(nav: NavMesh, point: tuple[float, float, float]) -> Area:
    """Prefer a containing polygon at the closest height; else nearest centroid."""
    found = find_area(nav, point)
    return found if found is not None else nearest_area_2d(nav, point)


def point_on_area(area: Area, point: tuple[float, float, float]) -> tuple[float, float, float]:
    return (point[0], point[1], area_plane_z(area, point[0], point[1]))


def summarize_distribution(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(values),
        "min": round(ordered[0], 1),
        "median": round(statistics.median(ordered), 1),
        "max": round(ordered[-1], 1),
        "mean": round(statistics.fmean(ordered), 1),
        "stdev": round(statistics.pstdev(ordered), 1) if len(ordered) > 1 else 0.0,
    }


def route_between(
    nav: NavMesh,
    start: Area,
    goal: Area,
    start_point: tuple[float, float, float] | None = None,
    goal_point: tuple[float, float, float] | None = None,
) -> tuple[list[int], float, list[tuple[float, float, float]]]:
    p0 = point_on_area(start, start_point) if start_point else start.centroid
    p1 = point_on_area(goal, goal_point) if goal_point else goal.centroid
    return dijkstra_edges(nav, start.area_id, goal.area_id, p0, p1)


def nav_validation(nav: NavMesh) -> dict:
    by_id = nav.by_id()
    hull = nav.generation.hulls[0] if nav.generation and nav.generation.hulls else None
    max_climb = hull.max_climb if hull else None
    max_up = hull.max_jump_up_dist if hull else None
    max_down = hull.max_jump_down_dist if hull else None
    dangling = 0
    one_way = 0
    vertical_anomalies = []
    for area in nav.areas:
        for neighbor, edge in area.connections:
            if neighbor not in by_id:
                dangling += 1
                continue
            target = by_id[neighbor]
            if not any(n == area.area_id for n, _ in target.connections):
                one_way += 1
            if max_climb is None:
                continue
            dz = target.centroid[2] - area.centroid[2]
            # Compare at the shared boundary where possible.
            edge_dz = dz
            reciprocal_edge = next(
                (e for n, e in target.connections if n == area.area_id), None
            )
            if reciprocal_edge is not None:
                edge_dz = edge_midpoint(target, edge)[2] - edge_midpoint(area, reciprocal_edge)[2]
            if edge_dz > max_up or edge_dz < -max_down:
                vertical_anomalies.append(
                    {
                        "from": area.area_id,
                        "to": neighbor,
                        "centroid_dz": round(dz, 1),
                        "boundary_dz": round(edge_dz, 1),
                        "reciprocal": reciprocal_edge is not None,
                    }
                )
    return {
        "dangling_connections": dangling,
        "one_way_connections": one_way,
        "vertical_limit_anomalies": vertical_anomalies,
        "max_climb": max_climb,
        "max_jump_up_dist": max_up,
        "max_jump_down_dist": max_down,
    }


def svg_overview(
    nav: NavMesh,
    routes: list[tuple[str, str, list[tuple[float, float, float]]]],
    path: Path,
) -> None:
    xs = [c[0] for a in nav.areas for c in a.corners]
    ys = [c[1] for a in nav.areas for c in a.corners]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    pad = 250.0
    min_x -= pad
    max_x += pad
    min_y -= pad
    max_y += pad
    width, height = max_x - min_x, max_y - min_y
    scale = 1400.0 / max(width, height)
    out_w, out_h = width * scale, height * scale

    def sx(x: float) -> float:
        return (x - min_x) * scale

    def sy(y: float) -> float:
        return out_h - (y - min_y) * scale

    zs = [a.centroid[2] for a in nav.areas]
    z_min, z_max = min(zs), max(zs)

    def fill(z: float) -> str:
        t = (z - z_min) / (z_max - z_min) if z_max > z_min else 0.0
        return f"rgb({int(40 + 180 * t)},{int(110 + 60 * t)},{int(210 - 150 * t)})"

    colors = ["#ffd166", "#ef476f", "#06d6a0", "#118ab2", "#f78c6b", "#c77dff"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{out_w:.0f}" height="{out_h:.0f}" '
        f'viewBox="0 0 {out_w:.0f} {out_h:.0f}">',
        '<rect width="100%" height="100%" fill="#0e1318"/>',
    ]
    for area in nav.areas:
        points = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y, _ in area.corners)
        parts.append(
            f'<polygon points="{points}" fill="{fill(area.centroid[2])}" '
            f'fill-opacity="0.26" stroke="#7f93a8" stroke-width="0.5"/>'
        )
    for index, (label, _target, points) in enumerate(routes):
        color = colors[index % len(colors)]
        polyline = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y, _ in points)
        parts.append(
            f'<polyline points="{polyline}" fill="none" stroke="{color}" '
            f'stroke-width="4" stroke-linejoin="round" stroke-linecap="round" opacity="0.95"/>'
        )
        x, y, _ = points[0]
        parts.append(
            f'<circle cx="{sx(x):.2f}" cy="{sy(y):.2f}" r="5" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{sx(x) + 8:.2f}" y="{sy(y) - 8:.2f}" fill="{color}" '
            f'font-family="sans-serif" font-size="15">{label}</text>'
        )
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nav", type=Path)
    parser.add_argument("entities", type=Path, help="resourceinfo -all text dump")
    parser.add_argument("--json", type=Path, help="write experiment JSON")
    parser.add_argument("--svg", type=Path, help="write overview SVG")
    parser.add_argument("--map-name", default="de_dust2")
    args = parser.parse_args()

    nav = parse_nav(args.nav)
    entities = parse_entity_points(args.entities)

    spawns_by_side: dict[str, list[EntityPoint]] = {"T": [], "CT": []}
    places: dict[str, list[EntityPoint]] = {}
    for entity in entities:
        side = SPAWN_CLASSES.get(entity.classname)
        if side:
            spawns_by_side[side].append(entity)
        if entity.classname == "env_cs_place" and entity.place_name:
            places.setdefault(entity.place_name, []).append(entity)

    target_places = {}
    for place_name, label in TARGET_PLACES.items():
        if place_name not in places:
            continue
        candidates = []
        for entity in places[place_name]:
            area = resolve_area(nav, entity.origin)
            candidates.append((area, entity))
        # Prefer the largest containing area at the marker; this tends to be the
        # main floor rather than a small ledge or prop top.
        containing = [
            (area, entity)
            for area, entity in candidates
            if point_in_poly_xy(area, entity.origin[0], entity.origin[1])
        ]
        chosen = max(containing or candidates, key=lambda item: item[0].size_2d)
        target_places[label] = chosen[0]

    targets = {label: area for label, area in target_places.items()}
    results: dict = {
        "map": args.map_name,
        "nav": {
            "version": nav.version,
            "sub_version": nav.sub_version,
            "is_analyzed": nav.is_analyzed,
            "areas": len(nav.areas),
            "ladders": len(nav.ladders),
            "generation": None
            if nav.generation is None
            else {
                "nav_gen_version": nav.generation.nav_gen_version,
                "hulls": [
                    {
                        "radius": h.radius,
                        "height": h.height,
                        "short_height": h.short_height,
                        "max_climb": h.max_climb,
                        "max_slope": h.max_slope,
                        "max_jump_up_dist": h.max_jump_up_dist,
                        "max_jump_down_dist": h.max_jump_down_dist,
                    }
                    for h in nav.generation.hulls
                ],
            },
        },
        "entity_counts": {
            "T_spawns": len(spawns_by_side["T"]),
            "CT_spawns": len(spawns_by_side["CT"]),
            "env_cs_place": sum(len(v) for v in places.values()),
            "entities_with_origin": len(entities),
        },
        "targets": {
            label: {
                "area_id": area.area_id,
                "centroid": [round(v, 1) for v in area.centroid],
                "size_2d": round(area.size_2d, 1),
            }
            for label, area in targets.items()
        },
        "spawn_to_target": {},
        "validation": nav_validation(nav),
    }

    representative_points = {}
    for side, spawns in spawns_by_side.items():
        areas = [resolve_area(nav, spawn.origin) for spawn in spawns]
        results[f"{side}_spawn_areas"] = [a.area_id for a in areas]
        side_results = {}
        for label, target in targets.items():
            distances = []
            for spawn, area in zip(spawns, areas):
                _ids, cost, _points = route_between(nav, area, target, spawn.origin)
                if math.isfinite(cost):
                    distances.append(cost)
            side_results[label] = summarize_distribution(distances)
            if distances:
                # Store the route to the target from the spawn whose distance is
                # the median, for a representative visualization.
                order = sorted(zip(distances, spawns, areas), key=lambda x: x[0])
                _cost, spawn, area = order[len(order) // 2]
                ids, cost, points = route_between(nav, area, target, spawn.origin)
                side_results[label]["representative"] = {
                    "spawn_origin": [round(v, 1) for v in spawn.origin],
                    "start_area": area.area_id,
                    "areas": len(ids),
                    "distance": round(cost, 1),
                }
                if label in ("Mid", "A", "B"):
                    representative_points[(side, label)] = points
        results["spawn_to_target"][side] = side_results

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"wrote {args.json}")

    if args.svg and representative_points:
        routes = []
        for (side, label), points in representative_points.items():
            routes.append((f"{side} to {label}", label, points))
        svg_overview(nav, routes, args.svg)
        print(f"wrote {args.svg}")

    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
