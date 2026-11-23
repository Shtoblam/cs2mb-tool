#!/usr/bin/env python3
"""Locate and run the packaged CS2MB SRI component.

SRI is a first-party self-contained Windows x64 executable built from
``sri/`` in this repository.  It uses the MIT-licensed ValveResourceFormat
library to decode compiled PHYS and EntityLump resources.  The Python pipeline
never invokes Source2Viewer-CLI or resourceinfo.

SRI is shipped inside the complete CS2MB package.  A source checkout can also
point ``CS2MB_SRI`` at a locally built executable.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_VAR = "CS2MB_SRI"
EXE_NAME = "cs2mb-sri.exe"
DEFAULT_LOCATIONS = (
    Path("tools") / "bin" / "sri" / EXE_NAME,
    Path("tools") / "bin" / EXE_NAME,
    Path("sri") / "bin" / "win-x64" / EXE_NAME,
)


class SriError(RuntimeError):
    """Raised when the internal converter is missing or fails."""


@dataclass(frozen=True)
class SriStatus:
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

    An explicit path or CS2MB_SRI value is authoritative: a stale override
    must fail loudly instead of silently using a different executable.
    """
    if explicit is not None:
        return [explicit]
    env_value = os.environ.get(ENV_VAR)
    if env_value:
        return [Path(env_value)]
    candidates = [ROOT / location for location in DEFAULT_LOCATIONS]
    discovered = shutil.which("cs2mb-sri")
    if discovered:
        candidates.append(Path(discovered))
    return candidates


def resolve_sri(explicit: Path | None = None) -> Path:
    """Return the first existing converter path, or raise SriError."""
    for candidate in candidate_paths(explicit):
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue
        if resolved.is_file():
            return resolved
    raise SriError(
        "SRI (cs2mb-sri) was not found. Install the complete CS2MB package or put "
        f"{EXE_NAME} in tools/bin/sri/, or set {ENV_VAR}. "
        "See docs/SETUP.md. No external Source2Viewer-CLI or resourceinfo is used."
    )


def run(
    arguments: list[str],
    *,
    explicit: Path | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    """Run SRI with an argument array, never a shell string."""
    executable = resolve_sri(explicit)
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
        raise SriError(f"cs2mb-sri timed out after {timeout} s") from error
    except OSError as error:
        raise SriError(f"could not run cs2mb-sri: {error}") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        tail = "\n".join(detail.splitlines()[-8:]) if detail else "no output"
        raise SriError(
            f"cs2mb-sri failed with exit code {result.returncode}:\n{tail}"
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


def status(*, explicit: Path | None = None) -> SriStatus:
    try:
        path = resolve_sri(explicit)
    except SriError as error:
        return SriStatus("", False, "", None, str(error))
    try:
        version_text = version(explicit=path)
    except SriError as error:
        return SriStatus(str(path), False, "", sha256(path), str(error))
    return SriStatus(str(path), True, version_text, sha256(path))


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
    except SriError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
