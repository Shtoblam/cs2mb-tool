#!/usr/bin/env python3
"""Locate and run the packaged CS2MB Source 2 converter.

The converter is a first-party self-contained Windows x64 executable built from
``source2/`` in this repository.  It uses the MIT-licensed ValveResourceFormat
library to decode compiled PHYS and EntityLump resources.  The Python pipeline
never invokes Source2Viewer-CLI or resourceinfo.

The executable is intentionally not committed.  Install the release asset in
one of the documented locations or point ``CS2MB_SOURCE2`` at it.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_VAR = "CS2MB_SOURCE2"
EXE_NAME = "cs2mb-source2.exe"
DEFAULT_LOCATIONS = (
    Path("tools") / "bin" / "source2" / EXE_NAME,
    Path("tools") / "bin" / EXE_NAME,
    Path("source2") / "bin" / "win-x64" / EXE_NAME,
)


class Source2Error(RuntimeError):
    """Raised when the internal converter is missing or fails."""


@dataclass(frozen=True)
class Source2Status:
    path: str
    ready: bool
    version: str
    sha256: str | None
    error: str | None = None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def candidate_paths(explicit: Path | None = None) -> list[Path]:
    """Return candidates in priority order.

    An explicit path or CS2MB_SOURCE2 value is authoritative: a stale override
    must fail loudly instead of silently using a different executable.
    """
    if explicit is not None:
        return [explicit]
    env_value = os.environ.get(ENV_VAR)
    if env_value:
        return [Path(env_value)]
    candidates = [ROOT / location for location in DEFAULT_LOCATIONS]
    discovered = shutil.which("cs2mb-source2")
    if discovered:
        candidates.append(Path(discovered))
    return candidates


def resolve_source2(explicit: Path | None = None) -> Path:
    """Return the first existing converter path, or raise Source2Error."""
    for candidate in candidate_paths(explicit):
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved
    raise Source2Error(
        "cs2mb-source2 was not found. Install the CS2MB Source 2 engine asset "
        f"in tools/bin/source2/{EXE_NAME}, or set {ENV_VAR}. "
        "See docs/SETUP.md; no Source2Viewer-CLI or resourceinfo is required."
    )


def run(
    arguments: list[str],
    *,
    explicit: Path | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    """Run the converter with an argument array, never a shell string."""
    executable = resolve_source2(explicit)
    command = [str(executable), *arguments]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise Source2Error(f"cs2mb-source2 timed out after {timeout} s") from error
    except OSError as error:
        raise Source2Error(f"could not run cs2mb-source2: {error}") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        tail = "\n".join(detail.splitlines()[-8:]) if detail else "no output"
        raise Source2Error(
            f"cs2mb-source2 failed with exit code {result.returncode}:\n{tail}"
        )
    return result


def version(*, explicit: Path | None = None) -> str:
    result = run(["--version"], explicit=explicit, timeout=30)
    return result.stdout.strip()


def convert_physics(
    source: Path,
    output: Path,
    *,
    explicit: Path | None = None,
    timeout: int = 900,
) -> str:
    """Convert world_physics.vmdl_c to a CS2MB-compatible glTF + .bin pair."""
    result = run(
        ["phys", "--input", str(source), "--output", str(output)],
        explicit=explicit,
        timeout=timeout,
    )
    return result.stdout.strip()


def convert_entities(
    source: Path,
    output: Path,
    *,
    explicit: Path | None = None,
    timeout: int = 600,
) -> str:
    """Convert default_ents.vents_c to the project's entity dump text format."""
    result = run(
        ["entities", "--input", str(source), "--output", str(output)],
        explicit=explicit,
        timeout=timeout,
    )
    return result.stdout.strip()


def status(*, explicit: Path | None = None) -> Source2Status:
    try:
        path = resolve_source2(explicit)
    except Source2Error as error:
        return Source2Status("", False, "", None, str(error))
    try:
        version_text = version(explicit=path)
    except Source2Error as error:
        return Source2Status(str(path), False, "", sha256(path), str(error))
    return Source2Status(str(path), True, version_text, sha256(path))


def main() -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="store_true", help="print component version")
    parser.add_argument("--status", action="store_true", help="print JSON status")
    parser.add_argument("--explicit", type=Path, help="override converter path")
    args = parser.parse_args()
    if args.status:
        import json

        payload = status(explicit=args.explicit)
        print(json.dumps(payload.__dict__, indent=2, ensure_ascii=False))
        return 0 if payload.ready else 1
    try:
        print(version(explicit=args.explicit))
    except Source2Error as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
