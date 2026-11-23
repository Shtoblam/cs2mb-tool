#!/usr/bin/env python3
"""Sweep a simplified player capsule through nav connections.

For every directed nav connection, a short path is built around the shared
edge crossing.  The collision index checks whether any near-vertical wall is
closer than the capsule radius at waist and head height.  Vertical clearance
and floor mismatch are checked at three points along the path.

This is a horizontal capsule sweep at two heights plus pointwise vertical
checks.  It is not a full 3D capsule sweep: stairs, ramps, dynamic props and
the rounded capsule top/bottom are not modelled.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from gltf_collision import TriangleIndex, load_gltf_primitives  # noqa: E402
from nav_inspect import area_plane_z, connection_crossing, parse_nav  # noqa: E402

CROUCH_HEIGHT_FLAG = 1 << 16


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gltf", type=Path)
    parser.add_argument("nav", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--offset", type=float, default=8.0)
    parser.add_argument("--radius", type=float, default=16.0)
    parser.add_argument("--height", type=float, default=71.0)
    parser.add_argument("--tolerance", type=float, default=2.0)
    parser.add_argument("--waist-height", type=float, default=24.0)
    parser.add_argument("--head-height", type=float, default=55.0)
    parser.add_argument("--max-vertical", type=float, default=64.0)
    parser.add_argument("--max-floor-step", type=float, default=24.0)
    parser.add_argument("--limit", type=int, default=0, help="debug: check only N connections")
    args = parser.parse_args()

    primitives = load_gltf_primitives(args.gltf)
    index = TriangleIndex(primitives, cell_size=128.0)
    nav = parse_nav(args.nav)
    by_id = nav.by_id()

    tested = 0
    skipped_vertical = 0
    wall_blocked: list[dict] = []
    low_ceiling: list[dict] = []
    floor_mismatch: list[dict] = []
    for source in nav.areas:
        for target_id, _edge in source.connections:
            if args.limit and tested >= args.limit:
                break
            target = by_id.get(target_id)
            if target is None:
                continue
            dz = target.centroid[2] - source.centroid[2]
            if abs(dz) > args.max_vertical:
                skipped_vertical += 1
                continue
            crossing = connection_crossing(source, target)
            dx = target.centroid[0] - source.centroid[0]
            dy = target.centroid[1] - source.centroid[1]
            length = math.hypot(dx, dy)
            if length < 1e-6:
                continue
            ux, uy = dx / length, dy / length
            before = (crossing[0] - ux * args.offset, crossing[1] - uy * args.offset)
            after = (crossing[0] + ux * args.offset, crossing[1] + uy * args.offset)
            floor_before = area_plane_z(source, before[0], before[1])
            floor_crossing = max(
                area_plane_z(source, crossing[0], crossing[1]),
                area_plane_z(target, crossing[0], crossing[1]),
            )
            floor_after = area_plane_z(target, after[0], after[1])
            source_waist_z = floor_before + args.waist_height
            source_head_z = floor_before + min(args.head_height, args.height - 2.0)
            target_waist_z = floor_after + args.waist_height
            target_head_z = floor_after + min(args.head_height, args.height - 2.0)

            wall_materials: list[str] = []
            wall_distance = args.radius
            wall_material = None
            effective_radius = args.radius - args.tolerance
            for p1, p2, waist_z, head_z in (
                (before, crossing, source_waist_z, source_head_z),
                (crossing, after, target_waist_z, target_head_z),
            ):
                for z in (waist_z, head_z):
                    distance, material = index.segment_capsule_clearance_2d(
                        p1, p2, z, max_dist=args.radius
                    )
                    if distance < wall_distance:
                        wall_distance = distance
                        wall_material = material
                    if distance < effective_radius and material not in wall_materials:
                        wall_materials.append(material)

            gaps = []
            floor_deltas = []
            for x, y, hint in (
                (before[0], before[1], floor_before),
                (crossing[0], crossing[1], floor_crossing),
                (after[0], after[1], floor_after),
            ):
                floor_z, _ceiling_z, gap = index.vertical_clearance(
                    x, y, hint, exclude_substrings={"clip"}
                )
                gaps.append(gap)
                floor_deltas.append(abs(floor_z - hint))
            min_gap = min(gaps)
            max_floor_delta = max(floor_deltas)
            low = min_gap < args.height - args.tolerance
            step_issue = max_floor_delta > args.max_floor_step
            crouch_expected = bool(
                source.attribute_flags & CROUCH_HEIGHT_FLAG
                or target.attribute_flags & CROUCH_HEIGHT_FLAG
            )
            row = {
                "from": source.area_id,
                "to": target.area_id,
                "dz": round(dz, 2),
                "crossing": [round(v, 1) for v in crossing],
                "path": [[round(v, 1) for v in before], [round(v, 1) for v in after]],
                "source_waist_z": round(source_waist_z, 2),
                "source_head_z": round(source_head_z, 2),
                "target_waist_z": round(target_waist_z, 2),
                "target_head_z": round(target_head_z, 2),
                "wall_distance": round(wall_distance, 2),
                "wall_material": wall_material,
                "materials": wall_materials,
                "gap": None if min_gap == float("inf") else round(min_gap, 2),
                "floor_delta": round(max_floor_delta, 2),
                "low_ceiling": low,
                "floor_mismatch": step_issue,
                "crouch_expected": crouch_expected,
            }
            tested += 1
            if wall_materials:
                wall_blocked.append(row)
            if low:
                low_ceiling.append(row)
            if step_issue:
                floor_mismatch.append(row)

    materials = Counter(
        material for row in wall_blocked for material in row["materials"]
    )
    strict: dict[tuple[int, int], dict] = {}
    for row in wall_blocked + low_ceiling:
        if row["materials"] or not row["crouch_expected"]:
            strict[(row["from"], row["to"])] = row
    nonclip_walls = [
        row
        for row in wall_blocked
        if any("clip" not in material for material in row["materials"])
    ]
    summary = {
        "tested": tested,
        "skipped_vertical": skipped_vertical,
        "wall_blocked": len(wall_blocked),
        "wall_blocked_nonclip": len(nonclip_walls),
        "wall_blocked_playerclip_only": len(wall_blocked) - len(nonclip_walls),
        "low_ceiling": len(low_ceiling),
        "low_ceiling_crouch_expected": sum(
            1 for row in low_ceiling if row["crouch_expected"]
        ),
        "floor_mismatch": len(floor_mismatch),
        "strict_blocked": len(strict),
        "wall_blocked_pct": round(100.0 * len(wall_blocked) / tested, 3) if tested else None,
        "wall_intersection": sum(
            1 for row in wall_blocked if row["wall_distance"] <= 1e-6
        ),
        "wall_near": sum(
            1 for row in wall_blocked if row["wall_distance"] > 1e-6
        ),
        "severe_wall": sum(1 for row in wall_blocked if row["wall_distance"] < args.radius / 2.0),
        "wall_distance_min": round(min((row["wall_distance"] for row in wall_blocked), default=args.radius), 2),
        "wall_distance_median": round(
            statistics.median(row["wall_distance"] for row in wall_blocked), 2
        ) if wall_blocked else None,
        "materials": dict(sorted(materials.items(), key=lambda kv: (-kv[1], kv[0]))),
        "wall_examples": wall_blocked[:20],
        "low_ceiling_examples": low_ceiling[:20],
        "floor_mismatch_examples": floor_mismatch[:20],
        "strict_examples": list(strict.values())[:20],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "summary": summary,
                    "wall_blocked": wall_blocked,
                    "low_ceiling": low_ceiling,
                    "floor_mismatch": floor_mismatch,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
