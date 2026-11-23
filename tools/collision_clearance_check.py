#!/usr/bin/env python3
"""Check a simplified player capsule against collision at nav samples.

For every nav area sample and every nav connection crossing:
  - find the collision floor/ceiling at that XY;
  - measure the nearest wall at waist height;
  - compare with player height 71 and radius 16.

This is a point-sample approximation, not a swept capsule; it is intended to
flag low ceilings and narrow passages for manual review.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from gltf_collision import TriangleIndex, load_gltf_primitives  # noqa: E402
from nav_inspect import area_plane_z, connection_crossing, parse_nav  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gltf", type=Path)
    parser.add_argument("nav", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--player-height", type=float, default=71.0)
    parser.add_argument("--player-radius", type=float, default=16.0)
    parser.add_argument("--tolerance", type=float, default=2.0)
    parser.add_argument("--samples-per-area", type=int, default=5)
    parser.add_argument("--cell-size", type=float, default=128.0)
    args = parser.parse_args()

    primitives = load_gltf_primitives(args.gltf)
    index = TriangleIndex(primitives, cell_size=args.cell_size)
    nav = parse_nav(args.nav)

    area_rows = []
    connection_rows = []
    for area in nav.areas:
        if not area.corners:
            continue
        cx, cy, _ = area.centroid
        points = [(cx, cy)]
        if area.size_2d >= 128.0:
            for corner in area.corners[: max(0, args.samples_per_area - 1)]:
                points.append(((cx + corner[0]) / 2.0, (cy + corner[1]) / 2.0))
        for sx, sy in points:
            floor_hint = area_plane_z(area, sx, sy)
            floor_z, ceiling_z, gap = index.vertical_clearance(
                sx, sy, floor_hint, exclude_substrings={"clip"}
            )
            wall_dist, wall_material = index.horizontal_clearance(
                sx, sy, floor_hint + 36.0, max_dist=64.0
            )
            low_ceiling = gap < args.player_height - args.tolerance
            narrow = wall_dist < args.player_radius - args.tolerance
            area_rows.append(
                {
                    "area_id": area.area_id,
                    "x": round(sx, 2),
                    "y": round(sy, 2),
                    "nav_z": round(floor_hint, 2),
                    "collision_floor": round(floor_z, 2),
                    "ceiling": None if ceiling_z is None or ceiling_z == float("inf") else round(ceiling_z, 2),
                    "gap": None if gap == float("inf") else round(gap, 2),
                    "wall_dist": round(wall_dist, 2),
                    "wall_material": wall_material,
                    "low_ceiling": low_ceiling,
                    "narrow": narrow,
                }
            )

    by_id = nav.by_id()
    for source in nav.areas:
        for target_id, _edge in source.connections:
            target = by_id.get(target_id)
            if target is None:
                continue
            crossing = connection_crossing(source, target)
            floor_hint = max(
                area_plane_z(source, crossing[0], crossing[1]),
                area_plane_z(target, crossing[0], crossing[1]),
            )
            floor_z, ceiling_z, gap = index.vertical_clearance(
                crossing[0], crossing[1], floor_hint, exclude_substrings={"clip"}
            )
            wall_dist, wall_material = index.horizontal_clearance(
                crossing[0], crossing[1], floor_hint + 36.0, max_dist=64.0
            )
            connection_rows.append(
                {
                    "from": source.area_id,
                    "to": target.area_id,
                    "crossing": [round(v, 1) for v in crossing],
                    "gap": None if gap == float("inf") else round(gap, 2),
                    "wall_dist": round(wall_dist, 2),
                    "wall_material": wall_material,
                    "low_ceiling": gap < args.player_height - args.tolerance,
                    "narrow": wall_dist < args.player_radius - args.tolerance,
                }
            )

    gaps = [r["gap"] for r in area_rows if r["gap"] is not None]
    walls = [r["wall_dist"] for r in area_rows]
    low = [r for r in area_rows if r["low_ceiling"]]
    narrow = [r for r in area_rows if r["narrow"]]
    conn_low = [r for r in connection_rows if r["low_ceiling"]]
    conn_narrow = [r for r in connection_rows if r["narrow"]]
    summary = {
        "area_samples": len(area_rows),
        "areas": len(nav.areas),
        "area_low_ceiling": len(low),
        "area_narrow": len(narrow),
        "connections": len(connection_rows),
        "connection_low_ceiling": len(conn_low),
        "connection_narrow": len(conn_narrow),
        "gap_median": round(statistics.median(gaps), 2) if gaps else None,
        "gap_p05": round(sorted(gaps)[max(0, int(0.05 * (len(gaps) - 1)))], 2) if gaps else None,
        "wall_median": round(statistics.median(walls), 2) if walls else None,
        "wall_min": round(min(walls), 2) if walls else None,
        "low_examples": low[:20],
        "narrow_examples": narrow[:20],
        "connection_low_examples": conn_low[:20],
        "connection_narrow_examples": conn_narrow[:20],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {"summary": summary, "area_samples": area_rows, "connections": connection_rows},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
