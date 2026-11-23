#!/usr/bin/env python3
"""Prepare CS2 map inputs from the installed game, then optionally generate.

Read-only with respect to the game.  Extracts nav, entity lump and
world_physics.vmdl_c from the map VPK, decodes the compiled entity and PHYS
resources with the internal CS2MB Source 2 engine, and can hand the four files
to the normal auto-generation pipeline.

The internal engine is the first-party ``cs2mb-source2`` executable built from
``source2/``.  No external converter binary is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from source2 import (  # noqa: E402
    Source2Error,
    convert_entities,
    convert_physics,
    resolve_source2,
    sha256,
    version,
)
from vpk_read import Vpk  # noqa: E402

MAP_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def extract_entry(vpk: Vpk, wanted: str, target: Path) -> None:
    normalized = wanted.replace("\\", "/").lower()
    for entry in vpk.entries:
        if entry.path.replace("\\", "/").lower() == normalized:
            target.write_bytes(vpk.read(entry))
            return
    raise FileNotFoundError(f"{wanted} not found in {vpk.path}")


def run(command: list[str], log_path: Path) -> None:
    """Run a project-local Python step with an argument array."""
    with log_path.open("wb") as log:
        result = subprocess.run(
            command,
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=1800,
            check=False,
        )
    if result.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-1200:]
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{tail}"
        )


def file_record(path: Path) -> dict:
    return {
        "path": str(path),
        "size": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True)
    parser.add_argument("--game", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--source2",
        type=Path,
        help="optional cs2mb-source2 executable path (default: packaged location)",
    )
    parser.add_argument("--generate-out", type=Path)
    parser.add_argument("--skip-clearance", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not MAP_RE.fullmatch(args.map):
        print("invalid map name", file=sys.stderr)
        return 2

    game = args.game.expanduser().resolve()
    maps_dir = game / "game" / "csgo" / "maps"
    gameinfo = game / "game" / "csgo" / "gameinfo.gi"
    map_vpk = maps_dir / f"{args.map}.vpk"
    for required in (maps_dir, gameinfo, map_vpk):
        if not required.exists():
            print(f"missing required path: {required}", file=sys.stderr)
            return 2

    try:
        converter = resolve_source2(args.source2)
        converter_version = version(explicit=converter)
    except Source2Error as error:
        print(str(error), file=sys.stderr)
        return 2

    out_dir = args.out_dir.expanduser().resolve()
    prepared = out_dir / "prepared"
    prepared.mkdir(parents=True, exist_ok=True)
    nav = prepared / f"{args.map}.nav"
    vents = prepared / "default_ents.vents_c"
    vmdl = prepared / "world_physics.vmdl_c"
    entities = prepared / "entities.txt"
    gltf = prepared / "world_physics_physics.gltf"
    gltf_bin = prepared / "world_physics_physics.bin"

    package = Vpk(map_vpk)
    try:
        extract_entry(package, f"maps/{args.map}.nav", nav)
        extract_entry(package, f"maps/{args.map}/entities/default_ents.vents_c", vents)
        extract_entry(package, f"maps/{args.map}/world_physics.vmdl_c", vmdl)
    except (FileNotFoundError, OSError, ValueError) as error:
        print(f"map resource extraction failed: {error}", file=sys.stderr)
        return 1

    try:
        log_lines = [
            f"converter: {converter}",
            f"version: {converter_version}",
        ]
        log_lines.append(convert_entities(vents, entities, explicit=converter))
        log_lines.append(convert_physics(vmdl, gltf, explicit=converter))
    except Source2Error as error:
        print(str(error), file=sys.stderr)
        return 1

    (prepared / "source2.log").write_text(
        "\n".join(log_lines) + "\n", encoding="utf-8"
    )

    for required in (nav, entities, gltf, gltf_bin):
        if not required.is_file():
            print(f"prepared file missing: {required}", file=sys.stderr)
            return 1

    manifest = {
        "schema_version": 2,
        "map": args.map,
        "game": str(game),
        "source2": {
            "path": str(converter),
            "version": converter_version,
            "sha256": sha256(converter),
        },
        "inputs": {
            "map_vpk": file_record(map_vpk),
            "nav": file_record(nav),
            "entities_resource": file_record(vents),
            "physics_resource": file_record(vmdl),
        },
        "prepared": {
            "nav": file_record(nav),
            "entities": file_record(entities),
            "collision_gltf": file_record(gltf),
            "collision_bin": file_record(gltf_bin),
        },
    }
    (out_dir / "prepared_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"prepared {args.map} -> {prepared}")

    if args.generate_out:
        try:
            run(
                [
                    sys.executable,
                    "tools/auto_generate.py",
                    "--map",
                    args.map,
                    "--nav",
                    str(nav),
                    "--entities",
                    str(entities),
                    "--collision-gltf",
                    str(gltf),
                    "--out-dir",
                    str(args.generate_out),
                    *(["--skip-clearance"] if args.skip_clearance else []),
                    *(["--dry-run"] if args.dry_run else []),
                ],
                prepared / "auto_generate.log",
            )
        except RuntimeError as error:
            print(str(error), file=sys.stderr)
            return 1
        print(f"generated {args.generate_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
