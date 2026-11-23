#!/usr/bin/env python3
"""Prepare CS2 map inputs from the installed game, then optionally generate.

Read-only with respect to the game.  Extracts nav, entity lump and
world_physics.vmdl_c from the map VPK, dumps entities with resourceinfo, exports
physics collision to glTF with Source2Viewer-CLI, and can hand the four files to
the normal auto-generation pipeline.

Source2Viewer-CLI is not bundled.  Put it in tools/bin/ or set S2V_CLI.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

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
    with log_path.open("wb") as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-1200:]
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(command)}\n{tail}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", required=True)
    parser.add_argument("--game", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--s2v-cli", type=Path)
    parser.add_argument("--generate-out", type=Path)
    parser.add_argument("--skip-clearance", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not MAP_RE.fullmatch(args.map):
        print("invalid map name", file=sys.stderr)
        return 2
    game = args.game.expanduser().resolve()
    maps_dir = game / "game" / "csgo" / "maps"
    resourceinfo = game / "game" / "bin" / "win64" / "resourceinfo.exe"
    gameinfo = game / "game" / "csgo" / "gameinfo.gi"
    map_vpk = maps_dir / f"{args.map}.vpk"
    for required in (maps_dir, resourceinfo, gameinfo, map_vpk):
        if not required.exists():
            print(f"missing required path: {required}", file=sys.stderr)
            return 2

    cli = args.s2v_cli or (
        Path(os.environ["S2V_CLI"]) if os.environ.get("S2V_CLI") else None
    )
    if cli is None:
        candidate = ROOT / "tools" / "bin" / "Source2Viewer-CLI.exe"
        if candidate.is_file():
            cli = candidate
    if cli is None or not cli.is_file():
        print(
            "Source2Viewer-CLI not found; put it in tools/bin/Source2Viewer-CLI.exe "
            "or set S2V_CLI",
            file=sys.stderr,
        )
        return 2

    out_dir = args.out_dir.expanduser().resolve()
    prepared = out_dir / "prepared"
    prepared.mkdir(parents=True, exist_ok=True)
    nav = prepared / f"{args.map}.nav"
    vents = prepared / "default_ents.vents_c"
    vmdl = prepared / "world_physics.vmdl_c"
    entities = prepared / "entities.txt"
    gltf_base = prepared / "world_physics.gltf"
    gltf = prepared / "world_physics_physics.gltf"

    package = Vpk(map_vpk)
    extract_entry(package, f"maps/{args.map}.nav", nav)
    extract_entry(package, f"maps/{args.map}/entities/default_ents.vents_c", vents)
    extract_entry(package, f"maps/{args.map}/world_physics.vmdl_c", vmdl)

    with entities.open("wb") as output:
        subprocess.run(
            [
                str(resourceinfo),
                "-game",
                str(game / "game" / "csgo"),
                "-i",
                str(vents),
                "-all",
            ],
            check=True,
            stdout=output,
            stderr=subprocess.STDOUT,
        )
    run(
        [
            str(cli),
            "-i",
            str(vmdl),
            "-o",
            str(gltf_base),
            "-d",
            "--gltf_export_format",
            "gltf",
            "--gltf_export_materials",
            "--game",
            str(gameinfo),
        ],
        prepared / "s2v.log",
    )
    for required in (nav, entities, gltf, prepared / "world_physics_physics.bin"):
        if not required.is_file():
            print(f"prepared file missing: {required}", file=sys.stderr)
            return 1

    manifest = {
        "map": args.map,
        "game": str(game),
        "prepared": {
            "nav": str(nav),
            "entities": str(entities),
            "collision_gltf": str(gltf),
            "collision_bin": str(prepared / "world_physics_physics.bin"),
        },
    }
    (out_dir / "prepared_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"prepared {args.map} -> {prepared}")

    if args.generate_out:
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
        print(f"generated {args.generate_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
