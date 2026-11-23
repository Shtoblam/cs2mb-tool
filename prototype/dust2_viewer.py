#!/usr/bin/env python3
"""Generate a self-contained local HTML/SVG prototype for de_dust2.

No web framework and no external JS/CSS. The output is a single HTML file that
can be opened directly in a browser (file://) and contains the nav polygons,
representative routes, spawns, targets, diagnostics and distance table.

The prototype uses only data already produced by the research scripts. It does
not read game files at runtime and does not claim that distances are travel
times.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from gltf_collision import load_gltf_primitives, wall_segments  # noqa: E402
from movement.route import route_profile  # noqa: E402
from movement.source import MoveProfile, simulate_straight  # noqa: E402
from simulation.scenario import rush_envelope, split_envelope  # noqa: E402
from nav_experiment import (  # noqa: E402
    SPAWN_CLASSES,
    TARGET_PLACES,
    parse_entity_points,
    resolve_area,
    route_between,
    summarize_distribution,
)
from nav_inspect import (  # noqa: E402
    Area,
    NavMesh,
    kosaraju_scc,
    parse_nav,
    point_in_poly_xy,
    undirected_components,
    vertical_layers,
)

ROUTE_COLORS = {
    ("T", "Mid"): "#ff9f1c",
    ("T", "A"): "#ffbf69",
    ("T", "B"): "#f4a261",
    ("CT", "Mid"): "#4cc9f0",
    ("CT", "A"): "#4895ef",
    ("CT", "B"): "#b5179e",
}


def select_targets(
    nav: NavMesh, entities: list
) -> tuple[dict[str, Area], dict[str, list]]:
    places: dict[str, list] = {}
    for entity in entities:
        if entity.classname == "env_cs_place" and entity.place_name:
            places.setdefault(entity.place_name, []).append(entity)

    targets: dict[str, Area] = {}
    for place_name, label in TARGET_PLACES.items():
        if place_name not in places:
            continue
        candidates = [(resolve_area(nav, e.origin), e) for e in places[place_name]]
        containing = [
            (area, entity)
            for area, entity in candidates
            if point_in_poly_xy(area, entity.origin[0], entity.origin[1])
        ]
        chosen = max(containing or candidates, key=lambda item: item[0].size_2d)
        targets[label] = chosen[0]
    return targets, places


def nav_bounds(nav: NavMesh) -> tuple[float, float, float, float]:
    xs = [c[0] for area in nav.areas for c in area.corners]
    ys = [c[1] for area in nav.areas for c in area.corners]
    return min(xs), max(xs), min(ys), max(ys)


def svg_map(
    nav: NavMesh,
    routes: list[dict],
    spawns: dict[str, list],
    targets: dict[str, Area],
    walls: set[tuple[tuple[float, float], tuple[float, float]]] | None = None,
    all_routes: list[dict] | None = None,
    map_name: str = "map",
) -> tuple[str, float, float]:
    min_x, max_x, min_y, max_y = nav_bounds(nav)
    pad = 300.0
    min_x -= pad
    max_x += pad
    min_y -= pad
    max_y += pad
    width = max_x - min_x
    height = max_y - min_y
    scale = 1400.0 / max(width, height)
    out_w = width * scale
    out_h = height * scale

    def sx(x: float) -> float:
        return (x - min_x) * scale

    def sy(y: float) -> float:
        return out_h - (y - min_y) * scale

    zs = [a.centroid[2] for a in nav.areas]
    z_min, z_max = min(zs), max(zs)

    def fill(z: float) -> str:
        t = (z - z_min) / (z_max - z_min) if z_max > z_min else 0.0
        return f"rgb({int(38 + 185 * t)},{int(105 + 75 * t)},{int(215 - 160 * t)})"

    parts = [
        f'<svg id="map" viewBox="0 0 {out_w:.2f} {out_h:.2f}" '
        f'preserveAspectRatio="xMidYMid meet" aria-label="{html.escape(map_name)} nav map">',
        '<rect x="0" y="0" width="100%" height="100%" fill="#0c1116"/>',
        '<g id="nav-layer">',
    ]
    for area in nav.areas:
        points = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y, _ in area.corners)
        parts.append(
            f'<polygon class="nav" data-id="{area.area_id}" '
            f'data-z="{area.centroid[2]:.1f}" data-flags="{area.attribute_flags}" '
            f'data-degree="{len(area.connections)}" '
            f'points="{points}" fill="{fill(area.centroid[2])}" '
            f'fill-opacity="0.27" stroke="#8396a8" stroke-width="0.55"/>'
        )
    parts.append("</g>")

    if walls:
        wall_path = " ".join(
            f"M {sx(a[0]):.1f},{sy(a[1]):.1f} L {sx(b[0]):.1f},{sy(b[1]):.1f}"
            for a, b in sorted(walls)
        )
        parts.append(
            f'<g id="wall-layer"><path d="{wall_path}" fill="none" '
            f'stroke="#ffffff" stroke-width="0.70" stroke-opacity="0.38" '
            f'stroke-linecap="round" vector-effect="non-scaling-stroke"/></g>'
        )

    if all_routes:
        parts.append(
            '<g id="all-routes-layer" class="all-routes-layer" style="display:none">'
        )
        for route in all_routes:
            points = " ".join(
                f"{sx(x):.2f},{sy(y):.2f}" for x, y, _ in route["points"]
            )
            parts.append(
                f'<polyline class="all-route" data-side="{route["side"]}" '
                f'data-target="{route["target"]}" points="{points}" fill="none" '
                f'stroke="{route["color"]}" stroke-width="1.1" '
                f'stroke-opacity="0.18" vector-effect="non-scaling-stroke"/>'
            )
        parts.append("</g>")

    for route in routes:
        points = " ".join(f"{sx(x):.2f},{sy(y):.2f}" for x, y, _ in route["points"])
        parts.append(
            f'<g class="route" data-route="{route["id"]}" '
            f'data-side="{route["side"]}" data-target="{route["target"]}">'
            f'<polyline points="{points}" fill="none" stroke="#05080b" '
            f'stroke-width="8" stroke-linejoin="round" stroke-linecap="round" '
            f'opacity="0.65" vector-effect="non-scaling-stroke"/>'
            f'<polyline points="{points}" fill="none" stroke="{route["color"]}" '
            f'stroke-width="4" stroke-linejoin="round" stroke-linecap="round" '
            f'vector-effect="non-scaling-stroke"/>'
            f"</g>"
        )

    for side, items in spawns.items():
        color = "#ff9f1c" if side == "T" else "#4cc9f0"
        parts.append(f'<g id="spawns-{side}" class="spawn-layer">')
        for index, item in enumerate(items):
            area, origin = item
            x, y = sx(origin[0]), sy(origin[1])
            parts.append(
                f'<circle class="spawn" data-side="{side}" data-area="{area.area_id}" '
                f'data-x="{origin[0]:.1f}" data-y="{origin[1]:.1f}" '
                f'data-z="{origin[2]:.1f}" cx="{x:.2f}" cy="{y:.2f}" r="5.2" '
                f'fill="{color}" stroke="#071014" stroke-width="1.4">'
                f"<title>{side} spawn {index + 1}, area {area.area_id}</title></circle>"
            )
        parts.append("</g>")

    parts.append('<g id="target-layer">')
    for label, area in targets.items():
        x, y = sx(area.centroid[0]), sy(area.centroid[1])
        label_text = html.escape(label)
        if label in ("A", "B", "Mid"):
            # Main sites get a dark pill below the marker so the label stays
            # readable over routes and near the top map toolbar.
            width = 22 + 12 * len(label)
            parts.append(
                f'<g class="target" data-label="{label_text}">'
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="9.5" fill="#f8f9fa" '
                f'stroke="#111" stroke-width="2"/>'
                f'<rect x="{x + 10:.2f}" y="{y + 4:.2f}" width="{width}" height="24" '
                f'rx="3" fill="#0b1015" fill-opacity="0.88" stroke="#555"/>'
                f'<text x="{x + 16:.2f}" y="{y + 22:.2f}" fill="#f8f9fa" '
                f'font-family="system-ui, sans-serif" font-size="18" font-weight="700">'
                f"{label_text}</text></g>"
            )
        else:
            parts.append(
                f'<g class="target" data-label="{label_text}">'
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7.5" fill="#f8f9fa" '
                f'stroke="#111" stroke-width="2"/>'
                f'<text x="{x + 12:.2f}" y="{y - 9:.2f}" fill="#f8f9fa" '
                f'font-family="system-ui, sans-serif" font-size="16" font-weight="600" '
                f'stroke="#0b1015" stroke-width="4" paint-order="stroke">'
                f"{label_text}</text></g>"
            )
    parts.append("</g></svg>")
    return "\n".join(parts), out_w, out_h


def route_payload(nav: NavMesh, spawns: dict, targets: dict[str, Area]):
    routes = []
    catalog: list[dict] = []
    table: dict[str, dict] = {}
    rush: dict[str, dict] = {}
    split: dict[str, object] = {}
    move_profile = MoveProfile.from_file()
    for side, items in spawns.items():
        table[side] = {}
        rush[side] = {}
        spawn_time_rows: list[dict[str, tuple[float, float]]] = [
            {} for _ in items
        ]
        for label in ("Mid", "A", "B"):
            if label not in targets:
                continue
            target = targets[label]
            measured = []
            time_lows: list[float] = []
            time_highs: list[float] = []
            for spawn_index, (area, origin) in enumerate(items):
                ids, cost, points = route_between(nav, area, target, origin)
                if math.isfinite(cost):
                    measured.append((cost, area, origin, ids, points))
                    spawn_profile = route_profile(points, 215.0, move_profile)
                    time_lows.append(spawn_profile.time_low)
                    time_highs.append(spawn_profile.time_high)
                    spawn_time_rows[spawn_index][label] = (
                        spawn_profile.time_low,
                        spawn_profile.time_high,
                    )
                    catalog.append(
                        {
                            "id": f"{side}-{label}-{spawn_index}",
                            "side": side,
                            "target": label,
                            "color": ROUTE_COLORS.get((side, label), "#ffffff"),
                            "distance": round(cost, 1),
                            "spawn": [round(v, 1) for v in origin],
                            "points": [[round(v, 1) for v in p] for p in points],
                            "time_low": round(spawn_profile.time_low, 2),
                            "time_high": round(spawn_profile.time_high, 2),
                            "vertical_transitions": spawn_profile.vertical_transitions,
                            "jump_budget": round(spawn_profile.jump_budget, 2),
                        }
                    )
            table[side][label] = summarize_distribution([m[0] for m in measured])
            table[side][label]["time_low"] = summarize_distribution(time_lows)
            table[side][label]["time_high"] = summarize_distribution(time_highs)
            if len(time_lows) >= 5:
                rush[side][label] = rush_envelope(time_lows, time_highs, team_size=5)
            if not measured:
                continue
            measured.sort(key=lambda item: item[0])
            cost, area, origin, ids, points = measured[len(measured) // 2]
            vertical = route_profile(points, 215.0, move_profile)
            routes.append(
                {
                    "id": f"{side}-{label}",
                    "side": side,
                    "target": label,
                    "color": ROUTE_COLORS.get((side, label), "#ffffff"),
                    "distance": cost,
                    "areas": len(ids),
                    "start_area": area.area_id,
                    "spawn": [round(v, 1) for v in origin],
                    "points": [[round(v, 1) for v in p] for p in points],
                    "vertical_transitions": vertical.vertical_transitions,
                    "vertical_up": round(vertical.vertical_up, 1),
                    "vertical_down": round(vertical.vertical_down, 1),
                    "max_rise": round(vertical.max_rise, 1),
                    "max_drop": round(vertical.max_drop, 1),
                    "jump_up_candidates": vertical.jump_up_candidates,
                    "ramp_rises": vertical.ramp_rises,
                    "jump_budget": round(vertical.jump_budget, 2),
                    "time_high_with_jumps": round(vertical.time_high_with_jumps, 2),
                    "turn_count": vertical.turn_count,
                    "max_turn_deg": round(vertical.max_turn_deg, 1),
                    "ideal_time": round(vertical.ideal_time, 3),
                    "stop_go_time": round(vertical.stop_go_time, 3),
                    "time_low": round(vertical.time_low, 3),
                    "time_high": round(vertical.time_high, 3),
                    "table": table[side][label],
                }
            )
        standard_split = (
            len(spawn_time_rows) >= 5
            and all(label in targets for label in ("Mid", "A", "B"))
            and all(
                all(label in row for label in ("Mid", "A", "B"))
                for row in spawn_time_rows
            )
        )
        if standard_split:
            quotas = {"Mid": 1, "A": 2, "B": 2}
            split[side] = {
                "optimal": split_envelope(
                    spawn_time_rows,
                    quotas,
                    policy="optimal",
                ),
                "random": split_envelope(
                    spawn_time_rows,
                    quotas,
                    policy="random",
                    seed=1,
                    samples_per_team=8,
                ),
                "softmax": split_envelope(
                    spawn_time_rows,
                    quotas,
                    policy="softmax",
                    seed=1,
                    samples_per_team=8,
                    temperature=5.0,
                ),
            }
        else:
            split[side] = {}
    return routes, table, rush, split, catalog


def table_html(
    table: dict,
    rush: dict | None = None,
    split: dict | None = None,
) -> str:
    profile = MoveProfile.from_file()
    rows = []
    for side in ("T", "CT"):
        for label in ("Mid", "A", "B"):
            data = table.get(side, {}).get(label)
            if not data:
                continue
            low = data.get("time_low")
            high = data.get("time_high")
            if low and high:
                ak_range = f"{low['median']:.1f}–{high['median']:.1f}"
            else:
                ak_range = f"{simulate_straight(data['median'], 215.0, profile).time:.1f}"
            rows.append(
                f"<tr><td class='{side.lower()}'>{side}</td><td>{label}</td>"
                f"<td>{data['min']:.0f}</td><td>{data['median']:.0f}</td>"
                f"<td>{data['max']:.0f}</td><td>{ak_range}</td></tr>"
            )
    distance_table = (
        "<table><thead><tr><th>Side</th><th>Target</th><th>min</th>"
        "<th>median</th><th>max</th><th>AK range s</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    html = distance_table
    if rush:
        rush_rows = []
        for side in ("T", "CT"):
            for label in ("Mid", "A", "B"):
                envelope = rush.get(side, {}).get(label)
                if envelope is None:
                    continue
                rush_rows.append(
                    f"<tr><td class='{side.lower()}'>{side}</td><td>{label}</td>"
                    f"<td>{envelope.low_p10:.1f}</td><td>{envelope.low_median:.1f}</td>"
                    f"<td>{envelope.low_p90:.1f}</td><td>{envelope.high_median:.1f}</td>"
                    f"<td>{envelope.high_p90:.1f}</td></tr>"
                )
        html += (
            "<h3>5-man rush envelope</h3>"
            + "<p class='help'>Все 5 игроков идут на одну цель; 5 различных "
            "спавнов из 15. Это не split 5v5, не combat и не балансный вывод.</p>"
            + "<table><thead><tr><th>Side</th><th>Target</th>"
            + "<th>P10 low</th><th>med low</th><th>P90 low</th>"
            + "<th>med high</th><th>P90 high</th></tr></thead><tbody>"
            + "".join(rush_rows)
            + "</tbody></table>"
        )
    if split:
        split_rows = []
        for side in ("T", "CT"):
            policies = split.get(side)
            if not policies:
                continue
            for label in ("Mid", "A", "B"):
                optimal = policies["optimal"].targets.get(label)
                random_policy = policies["random"].targets.get(label)
                softmax = policies["softmax"].targets.get(label)
                if optimal is None or random_policy is None or softmax is None:
                    continue
                split_rows.append(
                    f"<tr><td class='{side.lower()}'>{side}</td><td>{label}</td>"
                    f"<td>{optimal.low_median:.1f}</td>"
                    f"<td>{random_policy.low_median:.1f}</td>"
                    f"<td>{softmax.low_median:.1f}</td>"
                    f"<td>{optimal.high_median:.1f}</td></tr>"
                )
        html += (
            "<h3>5v5 split — assignment policies</h3>"
            + "<p class='help'>2 A / 2 B / 1 Mid, все C(15,5); optimal — "
            "best-case, random — uniform seed=1, softmax — τ=5 s seed=1, "
            "8 samples/team. Softmax — только proxy, не модель человека; "
            "combat не входит.</p>"
            + "<table><thead><tr><th>Side</th><th>Target</th>"
            + "<th>opt low</th><th>rand low</th><th>soft low</th>"
            + "<th>opt high</th></tr></thead><tbody>"
            + "".join(split_rows)
            + "</tbody></table>"
        )
    return html


def diagnostics_html(nav: NavMesh) -> str:
    ids = {a.area_id for a in nav.areas}
    edges = sum(len(a.connections) for a in nav.areas)
    one_way = sum(
        1
        for a in nav.areas
        for n, _ in a.connections
        if n in ids and not any(m == a.area_id for m, _ in nav.by_id()[n].connections)
    )
    scc, largest = kosaraju_scc(nav)
    comps = undirected_components(nav)
    crouch = sum(1 for a in nav.areas if a.attribute_flags & 0x10000)
    zero = sum(1 for a in nav.areas if a.size_2d == 0)
    hull = nav.generation.hulls[0] if nav.generation and nav.generation.hulls else None
    stacked = 0
    sampled = 0
    max_bands = 0
    for area in nav.areas[::4]:
        bands = vertical_layers(nav, area.centroid[0], area.centroid[1])
        sampled += 1
        if len(bands) > 1:
            stacked += 1
            max_bands = max(max_bands, len(bands))
    items = [
        ("Areas", f"{len(nav.areas):,}".replace(",", " ")),
        ("Edges", f"{edges:,}".replace(",", " ")),
        ("Undirected components", str(len(comps))),
        ("SCC", f"{len(scc)} (largest {largest})"),
        ("One-way edges", str(one_way)),
        ("CrouchHeight areas", str(crouch)),
        ("Zero-area polygons", str(zero)),
        ("Stacked XY samples", f"{stacked}/{sampled} (max {max_bands} bands)"),
        ("Ladders", str(len(nav.ladders))),
    ]
    if hull:
        items.extend(
            [
                ("Agent hull", f"r={hull.radius:g}, h={hull.height:g}"),
                ("Max climb / slope", f"{hull.max_climb:g} / {hull.max_slope}°"),
                ("Jump up / down", f"{hull.max_jump_up_dist:g} / {hull.max_jump_down_dist:g}"),
            ]
        )
    return "".join(
        f"<div class='diag'><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>"
        for k, v in items
    )


def collision_html(
    report: dict | None,
    connection: dict | None = None,
    clearance: dict | None = None,
) -> str:
    if not report:
        return "<div class='help'>Collision report не передан.</div>"
    summary = report.get("summary", report)
    pct = float(summary.get("matched_pct") or 0.0)
    quality_class = "quality-good" if pct >= 95.0 else "quality-warn"
    quality = (
        f"<div class='quality {quality_class}'><b>{pct:.1f}%</b>"
        f"<span>floor match ≤16 u</span></div>"
    )
    items = [
        ("Median |Δz|", f"{summary.get('median_abs_dz')} u"),
        ("P95 |Δz|", f"{summary.get('p95_abs_dz')} u"),
        ("Missing samples", f"{summary.get('missing')}"),
        ("Samples", f"{summary.get('samples')}"),
    ]
    if connection:
        conn = connection.get("summary", connection)
        items.append(
            ("Wall flags", f"{conn.get('blocked')}/{conn.get('tested')} connections")
        )
    if clearance:
        clear = clearance.get("summary", clearance)
        items.append(("Low ceilings", f"{clear.get('area_low_ceiling')} samples"))
        items.append(("Narrow", f"{clear.get('area_narrow')} samples"))
    return quality + "".join(
        f"<div class='diag'><span>{html.escape(str(k))}</span><b>{html.escape(str(v))}</b></div>"
        for k, v in items
    )


def build_html(
    title: str,
    svg: str,
    routes: list[dict],
    table: str,
    diagnostics: str,
    nav: NavMesh,
    map_name: str,
    collision: str = "",
) -> str:
    profile = MoveProfile.from_file()
    route_controls = []
    for side in ("T", "CT"):
        route_controls.append(
            f'<div class="route-group-label">'
            f'{"TERRORISTS" if side == "T" else "COUNTER-TERRORISTS"}</div>'
        )
        for label in ("Mid", "A", "B"):
            route = next((r for r in routes if r["side"] == side and r["target"] == label), None)
            if not route:
                continue
            ideal = route.get("ideal_time")
            if ideal is None:
                ideal = simulate_straight(route["distance"], 215.0, profile).time
            time_low = route.get("time_low", ideal)
            time_high = route.get("time_high", time_low)
            if time_high > time_low + 0.05:
                time_text = f"{time_low:.1f}–{time_high:.1f} s"
            else:
                time_text = f"{time_low:.1f} s"
            vertical_count = route.get("vertical_transitions", 0)
            vertical_badge = ""
            if vertical_count:
                vertical_badge = (
                    f'<span class="route-vert" title="Вертикальных переходов: '
                    f'{vertical_count}; вверх +{route.get("vertical_up", 0):.0f}, '
                    f'вниз -{route.get("vertical_down", 0):.0f}. '
                    f'AK range не включает прыжки/box jumps.">↑{vertical_count}</span>'
                )
            jump_budget = route.get("jump_budget", 0.0)
            jump_badge = ""
            if jump_budget > 0.01:
                jump_badge = (
                    f'<span class="route-jump" title="Jump budget: '
                    f'+{jump_budget:.1f} s для {route.get("jump_up_candidates", 0)} '
                    f'up-candidates; одна полная airtime на кандидат. '
                    f'high + budget ≈ {route.get("time_high_with_jumps", 0):.1f} s; '
                    f'это не измеренное время маршрута.">J+{jump_budget:.1f}</span>'
                )
            route_controls.append(
                f'<label class="route-card {side.lower()}">'
                f'<input type="checkbox" data-route="{route["id"]}" checked>'
                f'<span class="swatch" style="background:{route["color"]}"></span>'
                f'<span class="route-main"><b>{side} → {label}</b>'
                f'<small title="Нижняя граница — непрерывный ground run; '
                f'верхняя — остановка на каждом nav crossing. J+ — отдельный '
                f'jump budget, не входит в AK range.">'
                f'{route["distance"]:.0f} u · AK {time_text} '
                f'{vertical_badge} {jump_badge}</small></span>'
                f'<span class="route-state">ON</span></label>'
            )
    payload = {
        "map": map_name,
        "nav_version": nav.version,
        "area_count": len(nav.areas),
        "route_count": len(routes),
    }
    template = (ROOT / "prototype" / "ui_template.html").read_text(encoding="utf-8")

    return (
        template.replace("__TITLE__", html.escape(title))
        .replace("__MAP_NAME__", html.escape(map_name))
        .replace("__NAV_VERSION__", str(nav.version))
        .replace("__AREA_COUNT__", f"{len(nav.areas):,}".replace(",", " "))
        .replace("__ROUTE_CONTROLS__", "".join(route_controls))
        .replace("__TABLE__", table)
        .replace("__DIAGNOSTICS__", diagnostics)
        .replace("__COLLISION__", collision)
        .replace("__SVG__", svg)
        .replace("__PAYLOAD__", json.dumps(payload, ensure_ascii=False))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("nav", type=Path)
    parser.add_argument("entities", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts" / "dust2_viewer.html")
    parser.add_argument("--title", default="CS2 Map Balance")
    parser.add_argument("--map-name", default="de_dust2")
    parser.add_argument("--collision-report", type=Path)
    parser.add_argument("--connection-report", type=Path)
    parser.add_argument("--clearance-report", type=Path)
    parser.add_argument("--collision-gltf", type=Path)
    args = parser.parse_args()

    nav = parse_nav(args.nav)
    entities = parse_entity_points(args.entities)
    report = None
    connection = None
    clearance = None
    if args.collision_report:
        report = json.loads(args.collision_report.read_text(encoding="utf-8"))
    if args.connection_report:
        connection = json.loads(args.connection_report.read_text(encoding="utf-8"))
    if args.clearance_report:
        clearance = json.loads(args.clearance_report.read_text(encoding="utf-8"))
    walls = None
    if args.collision_gltf:
        walls = wall_segments(load_gltf_primitives(args.collision_gltf))
    targets, _places = select_targets(nav, entities)

    spawns: dict[str, list] = {"T": [], "CT": []}
    for entity in entities:
        side = SPAWN_CLASSES.get(entity.classname)
        if side:
            spawns[side].append((resolve_area(nav, entity.origin), entity.origin))

    routes, table, rush, split, catalog = route_payload(nav, spawns, targets)
    svg, _w, _h = svg_map(
        nav, routes, spawns, targets, walls, catalog, map_name=args.map_name
    )
    html_text = build_html(
        args.title,
        svg,
        routes,
        table_html(table, rush, split),
        diagnostics_html(nav),
        nav,
        args.map_name,
        collision_html(report, connection, clearance),
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_text, encoding="utf-8")
    print(f"wrote {args.out} ({args.out.stat().st_size} bytes)")
    print(
        f"areas={len(nav.areas)} routes={len(routes)} "
        f"catalog={len(catalog)} "
        f"spawns={sum(len(v) for v in spawns.values())} "
        f"wall_segments={len(walls) if walls else 0}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
