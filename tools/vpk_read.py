#!/usr/bin/env python3
"""Minimal read-only VPK inspector for the CS2 research prototype.

Supports VPK versions 1 and 2, including split `*_dir.vpk` packages and the
single-file map VPKs shipped by CS2. It intentionally implements only listing
and single-entry extraction; it does not write or modify packages.

The format logic follows ValvePak's Package.Read.cs (MIT):
https://github.com/ValveResourceFormat/ValvePak/blob/master/ValvePak/ValvePak/Package.Read.cs
"""

from __future__ import annotations

import argparse
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

MAGIC = 0x55AA1234
DIRECTORY_ARCHIVE = 0x7FFF
ENTRY = struct.Struct("<IHHIIH")


@dataclass(frozen=True)
class Entry:
    path: str
    crc32: int
    archive_index: int
    offset: int
    length: int
    preload: bytes

    @property
    def total_length(self) -> int:
        return len(self.preload) + self.length


class Vpk:
    def __init__(self, path: Path):
        self.path = path
        self.entries: list[Entry] = []
        with path.open("rb") as f:
            magic, version = struct.unpack("<II", f.read(8))
            if magic != MAGIC:
                raise ValueError(f"{path}: not a VPK (magic={magic:#x})")
            self.version = version
            if version == 1:
                (tree_size,) = struct.unpack("<I", f.read(4))
                self.header_size = 12
                self.file_data_size = 0
            elif version == 2:
                tree_size, self.file_data_size, _, _, _ = struct.unpack(
                    "<IIIII", f.read(20)
                )
                self.header_size = 28
            else:
                raise ValueError(f"{path}: unsupported VPK version {version}")

            tree = f.read(tree_size)
            if len(tree) != tree_size:
                raise ValueError("truncated directory tree")

        self.tree_size = tree_size
        self.data_offset = self.header_size + self.tree_size
        self.entries = self._parse_tree(tree)

    def _parse_tree(self, tree: bytes) -> list[Entry]:
        entries: list[Entry] = []
        pos = 0

        def read_cstr() -> str:
            nonlocal pos
            end = tree.find(b"\0", pos)
            if end < 0:
                raise ValueError("unterminated string in directory tree")
            raw = tree[pos:end]
            pos = end + 1
            return raw.decode("utf-8", errors="replace")

        while True:
            ext = read_cstr()
            if not ext:
                break
            while True:
                directory = read_cstr()
                if not directory:
                    break
                while True:
                    name = read_cstr()
                    if not name:
                        break
                    if len(tree) - pos < ENTRY.size:
                        raise ValueError("truncated entry metadata")
                    crc, preload_size, archive, offset, length, terminator = (
                        ENTRY.unpack_from(tree, pos)
                    )
                    pos += ENTRY.size
                    if terminator != 0xFFFF:
                        raise ValueError(f"invalid entry terminator {terminator:#x}")
                    preload = tree[pos : pos + preload_size]
                    if len(preload) != preload_size:
                        raise ValueError("truncated preload data")
                    pos += preload_size

                    stem = name
                    if ext != " ":
                        stem += "." + ext
                    full = stem if directory == " " else f"{directory}/{stem}"
                    entries.append(
                        Entry(full, crc, archive, offset, length, preload)
                    )
        return entries

    def _archive_path(self, index: int) -> Path:
        if index == DIRECTORY_ARCHIVE:
            return self.path
        stem = self.path.name
        if stem.lower().endswith("_dir.vpk"):
            stem = stem[:-8]
        else:
            stem = stem[:-4] if stem.lower().endswith(".vpk") else stem
        return self.path.with_name(f"{stem}_{index:03d}.vpk")

    def read(self, entry: Entry) -> bytes:
        chunks = [entry.preload]
        if entry.length:
            archive = self._archive_path(entry.archive_index)
            offset = entry.offset
            if entry.archive_index == DIRECTORY_ARCHIVE:
                offset += self.data_offset
            with archive.open("rb") as f:
                f.seek(offset)
                data = f.read(entry.length)
            if len(data) != entry.length:
                raise ValueError(f"{entry.path}: truncated file data")
            chunks.append(data)
        payload = b"".join(chunks)
        actual = zlib.crc32(payload) & 0xFFFFFFFF
        if actual != entry.crc32:
            raise ValueError(
                f"{entry.path}: CRC32 mismatch (expected {entry.crc32:08x}, got {actual:08x})"
            )
        return payload


def cmd_list(vpk: Vpk, needle: str | None) -> int:
    selected = [
        e for e in vpk.entries if needle is None or needle.lower() in e.path.lower()
    ]
    for e in selected:
        print(
            f"{e.path}\t{e.total_length}\t"
            f"archive={e.archive_index:#06x} offset={e.offset}"
        )
    print(
        f"\n{len(selected)} of {len(vpk.entries)} entries "
        f"(VPK v{vpk.version}, tree={vpk.tree_size}, data={vpk.file_data_size})",
        file=sys.stderr,
    )
    return 0 if selected else 1


def cmd_extract(vpk: Vpk, inner_path: str, output: Path) -> int:
    matches = [e for e in vpk.entries if e.path.lower() == inner_path.lower()]
    if len(matches) != 1:
        print(
            f"expected exactly one match for {inner_path!r}, got {len(matches)}",
            file=sys.stderr,
        )
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(vpk.read(matches[0]))
    print(f"extracted {matches[0].path} -> {output} ({matches[0].total_length} bytes)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vpk", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    p_list = sub.add_parser("list", help="list entries")
    p_list.add_argument("--filter", help="case-insensitive substring filter")
    p_extract = sub.add_parser("extract", help="extract one entry")
    p_extract.add_argument("inner_path")
    p_extract.add_argument("output", type=Path)
    args = parser.parse_args()

    package = Vpk(args.vpk)
    if args.command == "list":
        return cmd_list(package, args.filter)
    return cmd_extract(package, args.inner_path, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
