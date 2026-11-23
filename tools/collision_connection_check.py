#!/usr/bin/env python3
"""Check nav connections for collision walls at player waist height.

For each directed nav connection A -> B, take the crossing point on B's edge,
build a short segment 64 units before/after the crossing along A->B, and ask
the collision index whether a triangle crosses that horizontal segment.

This is a doorway/wall sanity check. It is not a full capsule sweep and does
not model stairs, ledges or dynamic props.
"""

from __future__ import annotations

import argparse
import json
import math
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
    parser.add_argument("--offset", type=float, default=16.0)
    parser.add_argument("--height", type=float, default=24.0)
    parser.add_argument("--max-vertical", type=float, default=64.0)
    args = parser.parse_args()

    primitives = load_gltf_primitives(args.gltf)
    index = TriangleIndex(primitives, cell_size=128.0)
    nav = parse_nav(args.nav)
    by_id = nav.by_id()

    tested = 0
    skipped_vertical = 0
    blocked = []
    for source in nav.areas:
        for target_id, _edge in source.connections:
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
            p1 = (crossing[0] - ux * args.offset, crossing[1] - uy * args.offset)
            p2 = (crossing[0] + ux * args.offset, crossing[1] + uy * args.offset)
            z = max(
                area_plane_z(source, crossing[0], crossing[1]),
                area_plane_z(target, crossing[0], crossing[1]),
            ) + args.height
            materials = index.segment_blocked_2d(p1, p2, z)
            tested += 1
            if materials:
                blocked.append(
                    {
                        "from": source.area_id,
                        "to": target.area_id,
                        "dz": round(dz, 2),
                        "crossing": [round(v, 1) for v in crossing],
                        "z": round(z, 2),
                        "materials": materials,
                    }
                )

    counts = Counter(m for item in blocked for m in item["materials"])
    summary = {
        "tested": tested,
        "skipped_vertical": skipped_vertical,
        "blocked": len(blocked),
        "blocked_pct": round(100.0 * len(blocked) / tested, 3) if tested else None,
        "materials": dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "examples": blocked[:30],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
