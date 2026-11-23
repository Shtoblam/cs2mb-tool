#!/usr/bin/env python3
"""Fail if tracked files contain obvious personal paths or secret-like values.

This is a lightweight hygiene check, not a replacement for a secret scanner.
It intentionally reports only the file/line/pattern, not the full value.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = {
    "local_user_path": re.compile(r"[A-Za-z]:\\Users\\[^\\\s`\"']+", re.I),
    "steam_library_path": re.compile(r"[A-Za-z]:\\SteamLibrary", re.I),
    "api_key": re.compile(
        r"(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}|"
        r"bearer\s+[A-Za-z0-9._-]{20,})",
        re.I,
    ),
    "password_assignment": re.compile(r"(password|passwd|api[_-]?key|secret)\s*[:=]", re.I),
}
SKIP = {"artifacts/", "inputs/", ".git/"}


def tracked_files() -> list[Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        )
        return [ROOT / line for line in output.splitlines() if line]
    except Exception:
        return [
            path
            for path in ROOT.rglob("*")
            if path.is_file() and not any(part in SKIP for part in path.parts)
        ]


def main() -> int:
    findings = 0
    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if any(rel.startswith(prefix) for prefix in SKIP):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for name, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                print(f"{name}: {rel}:{line}")
                findings += 1
    if findings:
        print(f"\n{findings} finding(s)", file=sys.stderr)
        return 1
    print("security scan: no obvious personal paths or secret-like values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
