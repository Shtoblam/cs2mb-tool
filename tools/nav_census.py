#!/usr/bin/env python3
"""Read every official map VPK's .nav in memory and print a census.

Read-only. No game files are extracted or modified.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nav_inspect import parse_nav_bytes
from vpk_read import Vpk


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--game",
        type=Path,
        default=Path(os.environ["CS2_GAME"]) if os.environ.get("CS2_GAME") else None,
        help="CS2 root (or set CS2_GAME); maps are read from game/csgo/maps",
    )
    args = parser.parse_args()
    if args.game is None:
        print("set --game <CS2_GAME> or CS2_GAME environment variable", file=sys.stderr)
        return 2
    maps = args.game / "game" / "csgo" / "maps"
    if not maps.is_dir():
        print(f"maps directory not found: {maps}", file=sys.stderr)
        return 2

    print(
        "map\tnav_version\tsub\tanalyzed\tareas\tedges\tladders\t"
        "undirected_components\tscc_count\tlargest_scc\tnav_bytes\t"
        "hull_radius\thull_height\tmax_climb\tmax_jump_up\tmax_jump_down\t"
        "dangling\tone_way\tvertical_anomalies\tconsumed_bytes\tfile_bytes"
    )
    for vpk_path in sorted(maps.glob("*.vpk")):
        try:
            package = Vpk(vpk_path)
        except Exception as exc:
            print(f"# ERROR {vpk_path.name}: {exc}", file=sys.stderr)
            continue
        navs = [e for e in package.entries if e.path.lower().endswith(".nav")]
        if not navs:
            continue
        for entry in navs:
            try:
                nav = parse_nav_bytes(package.read(entry))
            except Exception as exc:
                print(f"# ERROR {vpk_path.name}:{entry.path}: {exc}", file=sys.stderr)
                continue
            ids = {a.area_id for a in nav.areas}
            edges = sum(len(a.connections) for a in nav.areas)
            dangling = sum(1 for a in nav.areas for n, _ in a.connections if n not in ids)
            one_way = sum(
                1
                for a in nav.areas
                for n, _ in a.connections
                if n in ids and not any(m == a.area_id for m, _ in nav.by_id()[n].connections)
            )
            hull = nav.generation.hulls[0] if nav.generation and nav.generation.hulls else None
            # Local import keeps the census self-contained.
            from nav_inspect import kosaraju_scc, undirected_components

            comps = undirected_components(nav)
            scc, largest = kosaraju_scc(nav)
            anomalies = 0
            if hull:
                from nav_inspect import edge_midpoint

                by_id = nav.by_id()
                for a in nav.areas:
                    for n, edge in a.connections:
                        if n not in by_id:
                            continue
                        t = by_id[n]
                        rec = next((e for m, e in t.connections if m == a.area_id), None)
                        if rec is None:
                            continue
                        dz = edge_midpoint(t, edge)[2] - edge_midpoint(a, rec)[2]
                        if dz > hull.max_jump_up_dist or dz < -hull.max_jump_down_dist:
                            anomalies += 1
            print(
                "\t".join(
                    str(x)
                    for x in [
                        vpk_path.name,
                        nav.version,
                        nav.sub_version,
                        nav.is_analyzed,
                        len(nav.areas),
                        edges,
                        len(nav.ladders),
                        len(comps),
                        len(scc),
                        largest,
                        entry.total_length,
                        hull.radius if hull else "",
                        hull.height if hull else "",
                        hull.max_climb if hull else "",
                        hull.max_jump_up_dist if hull else "",
                        hull.max_jump_down_dist if hull else "",
                        dangling,
                        one_way,
                        anomalies,
                        nav.bytes_consumed,
                        entry.total_length,
                    ]
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
