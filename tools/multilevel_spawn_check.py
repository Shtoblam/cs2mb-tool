#!/usr/bin/env python3
"""Check z-aware nav point location at real spawn points on multi-level maps.

For each info_player_* origin:
  - find all nav areas containing XY;
  - choose the closest nav plane to the spawn z;
  - flag vertical ambiguity and count distinct overlapping floor bands.

This is a research/validation tool, not a movement simulator.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from nav_experiment import SPAWN_CLASSES, parse_entity_points  # noqa: E402
from nav_inspect import find_area_verbose, parse_nav, vertical_layers  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nav", type=Path)
    parser.add_argument("entities", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--ambiguity", type=float, default=64.0)
    args = parser.parse_args()

    nav = parse_nav(args.nav)
    entities = parse_entity_points(args.entities)
    rows = []
    for entity in entities:
        side = SPAWN_CLASSES.get(entity.classname)
        if not side:
            continue
        verbose = find_area_verbose(nav, entity.origin, args.ambiguity)
        bands = vertical_layers(nav, entity.origin[0], entity.origin[1])
        area = verbose["area"]
        rows.append(
            {
                "side": side,
                "origin": [round(v, 2) for v in entity.origin],
                "area_id": area.area_id if area else None,
                "nav_z": round(verbose["plane_z"], 2) if verbose["plane_z"] is not None else None,
                "dz": round(verbose["dz"], 2) if verbose["dz"] is not None else None,
                "ambiguous": verbose["ambiguous"],
                "candidates": verbose["candidates"],
                "bands": len(bands),
                "band_z": [round(band["z"], 1) for band in bands],
            }
        )

    summary = {
        "spawns": len(rows),
        "mapped": sum(1 for row in rows if row["area_id"] is not None),
        "ambiguous": sum(1 for row in rows if row["ambiguous"]),
        "multi_band": sum(1 for row in rows if row["bands"] > 1),
        "max_bands": max((row["bands"] for row in rows), default=0),
        "missing": [row for row in rows if row["area_id"] is None],
        "by_side": {
            side: {
                "spawns": sum(1 for row in rows if row["side"] == side),
                "ambiguous": sum(1 for row in rows if row["side"] == side and row["ambiguous"]),
                "multi_band": sum(1 for row in rows if row["side"] == side and row["bands"] > 1),
            }
            for side in ("T", "CT")
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print("\nexamples (multi-band/ambiguous):")
    for row in [r for r in rows if r["ambiguous"] or r["bands"] > 1][:20]:
        print(
            row["side"], row["origin"], "area", row["area_id"], "nav_z", row["nav_z"],
            "dz", row["dz"], "bands", row["band_z"], "ambiguous", row["ambiguous"],
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"summary": summary, "spawns": rows}, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"wrote {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
