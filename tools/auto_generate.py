#!/usr/bin/env python3
"""One-command map analysis pipeline for user-provided CS2 files.

Inputs are already extracted resources:
  - .nav
  - entity dump text (resourceinfo)
  - world_physics physics glTF

The script runs the existing read-only checks and builds the local HTML
prototype.  It does not read the game installation and does not modify any
input file.  A manifest with paths, sizes, hashes and command status is written
next to the outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from movement.route import route_profile  # noqa: E402
from simulation.balance import time_only_balance  # noqa: E402
from nav_experiment import (  # noqa: E402
    TARGET_PLACES,
    parse_entity_points,
    resolve_area,
    route_between,
)
from nav_inspect import parse_nav, point_in_poly_xy, summarize  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str]) -> None:
    print("$ " + " ".join(str(part) for part in command), flush=True)
    subprocess.run([str(part) for part in command], cwd=ROOT, check=True)


def safe_uri(uri: str) -> str:
    """Keep a relative glTF sidecar name without private path components."""
    if not uri or uri.startswith("data:") or "://" in uri:
        return ""
    path = Path(uri)
    if path.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", uri):
        return path.name
    parts = [part for part in path.parts if part not in (".", "..")]
    return Path(*parts).as_posix() if parts else path.name


def display_output(path: Path, out_dir: Path) -> str:
    try:
        return path.resolve().relative_to(out_dir.resolve()).as_posix()
    except (OSError, ValueError):
        return f"<OUTPUT>/{path.name}"


def display_input(path: Path, group: str) -> str:
    return f"<INPUT>/{group}/{path.name}"


def display_viewer3d(info: dict, out_dir: Path) -> dict:
    result = dict(info)
    if result.get("ok"):
        result["data"] = display_output(out_dir / "viewer3d" / "data.json", out_dir)
        result["scene"] = display_output(out_dir / "viewer3d" / "scene.gltf", out_dir)
    return result


def display_command(command: list[str], input_paths: dict[str, str], out_dir: Path) -> list[str]:
    displayed = []
    for index, part in enumerate(command):
        text = str(part)
        if index == 0:
            displayed.append("<PYTHON>")
            continue
        try:
            resolved = str(Path(text).resolve())
        except OSError:
            resolved = ""
        if resolved in input_paths:
            displayed.append(input_paths[resolved])
            continue
        if not Path(text).is_absolute():
            displayed.append(text)
            continue
        try:
            displayed.append(display_output(Path(text), out_dir))
        except (OSError, ValueError):
            displayed.append(f"<PATH>/{Path(text).name}")
    return displayed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True, help="map name, e.g. de_dust2")
    parser.add_argument("--nav", required=True, type=Path)
    parser.add_argument("--entities", required=True, type=Path)
    parser.add_argument("--collision-gltf", required=True, type=Path)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--no-hash", action="store_true")
    parser.add_argument("--skip-clearance", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not re.fullmatch(r"^[A-Za-z0-9_-]{1,64}$", args.map):
        print("invalid map name", file=sys.stderr)
        return 2

    inputs = {
        "nav": args.nav,
        "entities": args.entities,
        "collision_gltf": args.collision_gltf,
    }
    missing = [str(path) for path in inputs.values() if not path.is_file()]
    if missing:
        print("missing input files: " + ", ".join(missing), file=sys.stderr)
        return 2

    out_dir = args.out_dir or ROOT / "artifacts" / "auto" / args.map
    out_dir.mkdir(parents=True, exist_ok=True)
    floor_json = out_dir / "collision_floor.json"
    connection_json = out_dir / "connection_check.json"
    clearance_json = out_dir / "clearance.json"
    viewer_html = out_dir / "viewer.html"
    manifest_path = out_dir / "manifest.json"

    input_paths: dict[str, str] = {}

    def input_record(path: Path, group: str) -> dict:
        display = display_input(path, group)
        input_paths[str(path.resolve())] = display
        record = {
            "path": display,
            "size": path.stat().st_size,
            "sha256": None if args.no_hash else sha256(path),
        }
        if path.suffix.lower() == ".gltf":
            gltf = json.loads(path.read_text(encoding="utf-8"))
            sidecars = []
            for buffer in gltf.get("buffers", []):
                uri = buffer.get("uri")
                if not uri or uri.startswith("data:"):
                    continue
                sidecar = (path.parent / uri).resolve()
                if not sidecar.is_relative_to(path.parent.resolve()):
                    continue
                if sidecar.is_file():
                    sidecar_display = display_input(sidecar, "collision")
                    input_paths[str(sidecar)] = sidecar_display
                    sidecars.append(
                        {
                            "uri": safe_uri(uri),
                            "path": sidecar_display,
                            "size": sidecar.stat().st_size,
                            "sha256": None if args.no_hash else sha256(sidecar),
                        }
                    )
            record["sidecars"] = sidecars
        return record

    manifest = {
        "schema_version": 1,
        "map": args.map,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "inputs": {
            "nav": input_record(args.nav, "nav"),
            "entities": input_record(args.entities, "entities"),
            "collision_gltf": input_record(args.collision_gltf, "collision"),
        },
        "outputs": {},
        "commands": [],
    }

    def write_manifest() -> None:
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    commands = [
        [
            sys.executable,
            "tools/collision_floor_test.py",
            str(args.collision_gltf),
            str(args.nav),
            "--json",
            str(floor_json),
        ],
        [
            sys.executable,
            "tools/collision_connection_check.py",
            str(args.collision_gltf),
            str(args.nav),
            "--json",
            str(connection_json),
        ],
    ]
    if not args.skip_clearance:
        commands.append(
            [
                sys.executable,
                "tools/collision_clearance_check.py",
                str(args.collision_gltf),
                str(args.nav),
                "--json",
                str(clearance_json),
            ]
        )
    viewer_command = [
        sys.executable,
        "prototype/dust2_viewer.py",
        str(args.nav),
        str(args.entities),
        "--collision-report",
        str(floor_json),
        "--connection-report",
        str(connection_json),
        "--collision-gltf",
        str(args.collision_gltf),
        "--title",
        f"CS2 Map Balance — {args.map}",
        "--map-name",
        args.map,
        "--out",
        str(viewer_html),
    ]
    if not args.skip_clearance:
        viewer_command.extend(["--clearance-report", str(clearance_json)])
    commands.append(viewer_command)

    if args.dry_run:
        manifest["status"] = "dry-run"
        manifest["commands"] = [
            {"command": display_command(command, input_paths, out_dir), "status": "pending"}
            for command in commands
        ]
        write_manifest()
        print(f"wrote {manifest_path}")
        return 0

    try:
        for command in commands:
            run(command)
            manifest["commands"].append(
                {"command": display_command(command, input_paths, out_dir), "status": "ok"}
            )
    except subprocess.CalledProcessError as error:
        manifest["status"] = "failed"
        manifest["error"] = {
            "returncode": error.returncode,
            "command": display_command(
                [str(part) for part in error.cmd], input_paths, out_dir
            ),
        }
        write_manifest()
        print(f"pipeline failed; manifest: {manifest_path}", file=sys.stderr)
        return error.returncode or 1

    viewer3d_info: dict = {"ok": False, "error": "not requested"}
    try:
        from viewer3d.build import build_viewer3d

        viewer3d_info = build_viewer3d(
            args.nav,
            args.entities,
            args.collision_gltf,
            out_dir,
            args.map,
        )
        print(f"wrote {out_dir / 'viewer3d' / 'data.json'}")
    except Exception as error:  # optional layer; the 2D viewer remains usable
        viewer3d_info = {"ok": False, "error": "3DsVW data generation failed"}
        print(f"3DsVW generation failed: {error}", file=sys.stderr)

    def report_summary(path: Path) -> dict:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("summary", data)

    nav = parse_nav(args.nav)
    nav_summary = summarize(nav)
    entities = parse_entity_points(args.entities)

    places: dict[str, list] = {}
    for entity in entities:
        if entity.classname == "env_cs_place" and entity.place_name:
            places.setdefault(entity.place_name, []).append(entity)
    targets = {}
    for place_name, label in TARGET_PLACES.items():
        candidates = [
            (resolve_area(nav, entity.origin), entity)
            for entity in places.get(place_name, [])
        ]
        if not candidates:
            continue
        containing = [
            (area, entity)
            for area, entity in candidates
            if point_in_poly_xy(area, entity.origin[0], entity.origin[1])
        ]
        targets[label] = max(
            containing or candidates, key=lambda item: item[0].size_2d
        )[0]

    route_metrics: dict[str, dict] = {}
    for side, classname in (
        ("T", "info_player_terrorist"),
        ("CT", "info_player_counterterrorist"),
    ):
        route_metrics[side] = {}
        spawns = [
            (resolve_area(nav, entity.origin), entity.origin)
            for entity in entities
            if entity.classname == classname
        ]
        for label in ("Mid", "A", "B"):
            target = targets.get(label)
            if target is None:
                continue
            measured = []
            for area, origin in spawns:
                _ids, cost, points = route_between(nav, area, target, origin)
                if math.isfinite(cost):
                    measured.append((cost, route_profile(points, 215.0)))
            if not measured:
                continue
            measured.sort(key=lambda item: item[0])
            cost, profile = measured[len(measured) // 2]
            route_metrics[side][label] = {
                "distance": round(cost, 1),
                "time_low": round(profile.time_low, 2),
                "time_high": round(profile.time_high, 2),
                "jump_budget": round(profile.jump_budget, 2),
                "vertical_transitions": profile.vertical_transitions,
            }

    balance = time_only_balance(route_metrics)
    summary = {
        "schema_version": 1,
        "map": args.map,
        "generated_utc": manifest["generated_utc"],
        "nav": {
            key: nav_summary.get(key)
            for key in (
                "version",
                "area_count",
                "edge_count",
                "scc_count",
                "ladder_count",
                "undirected_component_count",
                "areas_zero_size_2d",
                "area_size_2d_median",
                "z_min",
                "z_median",
                "z_max",
                "reciprocal_edge_fraction",
            )
        },
        "entities": {
            "t_spawns": sum(e.classname == "info_player_terrorist" for e in entities),
            "ct_spawns": sum(
                e.classname == "info_player_counterterrorist" for e in entities
            ),
            "callouts": sum(e.classname == "env_cs_place" for e in entities),
        },
        "collision_floor": report_summary(floor_json),
        "wall": report_summary(connection_json),
        "clearance": None
        if args.skip_clearance
        else report_summary(clearance_json),
        "routes": route_metrics,
        "balance": balance.as_dict() if balance else None,
        "viewer_html": "viewer.html",
        "viewer3d": display_viewer3d(viewer3d_info, out_dir),
        "manifest": "manifest.json",
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest["status"] = "ok"
    manifest["outputs"] = {
        "viewer_html": display_output(viewer_html, out_dir),
        "viewer3d": {
            "data_json": display_output(out_dir / "viewer3d" / "data.json", out_dir)
            if (out_dir / "viewer3d" / "data.json").is_file()
            else None,
            "scene_gltf": display_output(out_dir / "viewer3d" / "scene.gltf", out_dir)
            if (out_dir / "viewer3d" / "scene.gltf").is_file()
            else None,
        },
        "collision_floor_json": display_output(floor_json, out_dir),
        "connection_json": display_output(connection_json, out_dir),
        "clearance_json": None
        if args.skip_clearance
        else display_output(clearance_json, out_dir),
        "summary_json": display_output(summary_path, out_dir),
    }
    write_manifest()
    print(f"wrote {viewer_html}")
    print(f"wrote {summary_path}")
    print(f"wrote {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
