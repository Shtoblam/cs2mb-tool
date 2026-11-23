#!/usr/bin/env python3
"""Compare nav floor heights with exported physics collision floors.

The glTF is produced by Source2Viewer from maps/<map>/world_physics.vmdl_c.
Coordinates are Hammer units, Source axes; the glTF node matrix is ignored.

For every nav area, sample the centroid and midpoints toward its corners,
cast a vertical query into the collision triangle index, and compare the
nearest collision surface with the nav plane height.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from gltf_collision import TriangleIndex, load_gltf_primitives  # noqa: E402
from nav_inspect import area_plane_z, parse_nav  # noqa: E402


def percentile(values: list[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[index]


def cluster_hits(hits: list[float], gap: float) -> list[float]:
    """Merge nearly coplanar triangle hits into distinct surfaces."""
    if not hits:
        return []
    clusters = [hits[0]]
    for z in hits[1:]:
        if z - clusters[-1] > gap:
            clusters.append(z)
    return clusters


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gltf", type=Path)
    parser.add_argument("nav", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--tolerance", type=float, default=16.0)
    parser.add_argument("--cell-size", type=float, default=128.0)
    parser.add_argument("--samples-per-area", type=int, default=5)
    parser.add_argument("--cluster-gap", type=float, default=4.0)
    parser.add_argument("--level-window", type=float, default=200.0)
    parser.add_argument("--min-normal-z", type=float, default=0.5)
    parser.add_argument("--min-area-for-corners", type=float, default=128.0)
    args = parser.parse_args()

    primitives = load_gltf_primitives(args.gltf)
    index = TriangleIndex(primitives, cell_size=args.cell_size)
    nav = parse_nav(args.nav)
    print(
        f"primitives={len(primitives)} vertices={sum(len(p.positions)//3 for p in primitives)} "
        f"triangles={sum(len(p.indices)//3 for p in primitives)} "
        f"indexed_triangles={index.triangle_count}"
    )
    print(f"index_bounds_min={index.bounds_min} max={index.bounds_max}")

    samples = []
    per_area = []
    for area in nav.areas:
        if not area.corners:
            continue
        cx, cy, _ = area.centroid
        points = [(cx, cy)]
        # Tiny edge slivers produce misleading boundary samples; keep the
        # centroid sample and skip corner midpoints for small polygons.
        if area.size_2d >= args.min_area_for_corners:
            for corner in area.corners[: max(0, args.samples_per_area - 1)]:
                points.append(((cx + corner[0]) / 2.0, (cy + corner[1]) / 2.0))
        nav_z = area_plane_z(area, cx, cy)
        area_dz = []
        area_near_ambiguous = 0
        area_other_levels = 0
        for sample_index, (x, y) in enumerate(points):
            hits = index.hits_at(
                x,
                y,
                horizontal_only=True,
                min_abs_normal_z=args.min_normal_z,
            )
            clusters = cluster_hits(hits, args.cluster_gap)
            near = [z for z in clusters if abs(z - nav_z) <= args.tolerance]
            above = [
                z for z in clusters
                if nav_z + 32.0 <= z <= nav_z + args.level_window
            ]
            below = [
                z for z in clusters
                if nav_z - args.level_window <= z <= nav_z - 32.0
            ]
            nearest = min(clusters, key=lambda z: abs(z - nav_z)) if clusters else None
            record = {
                "area_id": area.area_id,
                "sample": sample_index,
                "x": round(x, 2),
                "y": round(y, 2),
                "nav_z": round(nav_z, 2),
                "hits": [round(z, 2) for z in hits],
                "clusters": [round(z, 2) for z in clusters],
                "near_count": len(near),
                "above": [round(z, 2) for z in above],
                "below": [round(z, 2) for z in below],
            }
            if len(near) > 1:
                area_near_ambiguous += 1
            if above or below:
                area_other_levels += 1
            if nearest is None:
                record["collision_z"] = None
                record["dz"] = None
            else:
                dz = nearest - nav_z
                record["collision_z"] = round(nearest, 2)
                record["dz"] = round(dz, 2)
                area_dz.append(dz)
            samples.append(record)
        if area_dz:
            per_area.append(
                {
                    "area_id": area.area_id,
                    "median_dz": round(statistics.median(area_dz), 2),
                    "max_abs_dz": round(max(abs(d) for d in area_dz), 2),
                    "near_ambiguous_samples": area_near_ambiguous,
                    "other_level_samples": area_other_levels,
                }
            )

    dzz = [s["dz"] for s in samples if s["dz"] is not None]
    absdzz = [abs(d) for d in dzz]
    matched = sum(1 for d in absdzz if d <= args.tolerance)
    missing = sum(1 for s in samples if s["dz"] is None)
    summary = {
        "areas": len(per_area),
        "samples": len(samples),
        "matched": matched,
        "matched_pct": round(100.0 * matched / len(samples), 2) if samples else None,
        "missing": missing,
        "missing_pct": round(100.0 * missing / len(samples), 2) if samples else None,
        "median_abs_dz": round(statistics.median(absdzz), 2) if absdzz else None,
        "p95_abs_dz": round(percentile(absdzz, 0.95), 2) if absdzz else None,
        "max_abs_dz": round(max(absdzz), 2) if absdzz else None,
        "near_ambiguous_samples": sum(1 for s in samples if s["near_count"] > 1),
        "samples_with_other_levels": sum(1 for s in samples if s["above"] or s["below"]),
        "areas_with_near_ambiguity": sum(
            1 for a in per_area if a["near_ambiguous_samples"] > 0
        ),
        "areas_with_other_levels": sum(
            1 for a in per_area if a["other_level_samples"] > 0
        ),
        "worst_areas": sorted(per_area, key=lambda a: a["max_abs_dz"], reverse=True)[:20],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {"summary": summary, "per_area": per_area, "samples": samples},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"wrote {args.json} ({args.json.stat().st_size} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
