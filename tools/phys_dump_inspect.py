#!/usr/bin/env python3
"""Extract hull bounds and attributes from a resourceinfo PHYS text dump.

This does not parse the binary PHYS block and does not reconstruct triangles.
It intentionally reads only scalar fields that resourceinfo prints in full:

  m_nCollisionAttributeIndex
  m_nSurfacePropertyIndex
  m_vCentroid
  m_vMinBounds / m_vMaxBounds
  m_flVolume

Large hex blobs (vertices/edges/faces) are ignored because the default
resourceinfo dump can truncate them. Use SRI/VRF for full collision
triangles.

Usage:
  python tools/phys_dump_inspect.py <phys_dump.txt> --json artifacts/hulls.json
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

NUM = r"\[\s*([^\]]+)\]"
RE_INT = re.compile(r"m_nCollisionAttributeIndex\s*=\s*(-?\d+)")
RE_SURF = re.compile(r"m_nSurfacePropertyIndex\s*=\s*(-?\d+)")
RE_CENTROID = re.compile(r"m_vCentroid\s*=\s*" + NUM)
RE_MIN = re.compile(r"m_vMinBounds\s*=\s*" + NUM)
RE_MAX = re.compile(r"m_vMaxBounds\s*=\s*" + NUM)
RE_VOL = re.compile(r"m_flVolume\s*=\s*([-+0-9.eE]+)")


def parse_vec(text: str) -> list[float]:
    return [float(x.strip()) for x in text.split(",")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dump", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    records: list[dict] = []
    current: dict | None = None
    lines = 0

    with args.dump.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            lines += 1
            match = RE_INT.search(line)
            if match:
                if current and "min" in current:
                    # Incomplete previous record; discard it rather than emit bad data.
                    current = None
                current = {"collision_attribute": int(match.group(1))}
                continue
            if current is None:
                continue
            match = RE_SURF.search(line)
            if match:
                current["surface_property"] = int(match.group(1))
                continue
            match = RE_CENTROID.search(line)
            if match:
                current["centroid"] = parse_vec(match.group(1))
                continue
            match = RE_MIN.search(line)
            if match:
                current["min"] = parse_vec(match.group(1))
                continue
            match = RE_MAX.search(line)
            if match:
                current["max"] = parse_vec(match.group(1))
                if "min" in current and "centroid" in current:
                    records.append(current)
                current = None
                continue
            match = RE_VOL.search(line)
            if match and current is not None:
                try:
                    current["volume"] = float(match.group(1))
                except ValueError:
                    pass

    collision_counts = Counter(r["collision_attribute"] for r in records)
    surface_counts = Counter(r.get("surface_property") for r in records)
    mins = [min(r["min"][i] for r in records) for i in range(3)] if records else []
    maxs = [max(r["max"][i] for r in records) for i in range(3)] if records else []
    zs = [r["centroid"][2] for r in records if "centroid" in r]
    volumes = [r["volume"] for r in records if "volume" in r]

    summary = {
        "dump_lines": lines,
        "hulls": len(records),
        "collision_attribute_counts": dict(sorted(collision_counts.items())),
        "surface_property_counts": dict(sorted(surface_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "bounds_min": mins,
        "bounds_max": maxs,
        "z_min": min(zs) if zs else None,
        "z_median": statistics.median(zs) if zs else None,
        "z_max": max(zs) if zs else None,
        "volume_sum": round(sum(volumes), 3) if volumes else None,
        "volume_median": round(statistics.median(volumes), 3) if volumes else None,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps({"summary": summary, "hulls": records}, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"wrote {args.json} ({args.json.stat().st_size} bytes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
