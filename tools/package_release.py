from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "VERSION"
SRI_EXE = ROOT / "tools" / "bin" / "sri" / "cs2mb-sri.exe"
SRI_SOURCE = ROOT / "sri"
SRI_NOTICES = ROOT / "sri" / "THIRD_PARTY_NOTICES.md"
DIST = ROOT / "dist"

PYTHON_VERSION = "3.13.3"
PYTHON_LICENSE = "PSF-2.0"
NUGET_LICENSES = {
    "ValveResourceFormat": "MIT",
    "ValvePak": "MIT",
    "ValveKeyValue": "MIT",
    "K4os.Compression.LZ4": "MIT",
    "ZstdSharp.Port": "MIT",
    "SharpGLTF.Core": "MIT",
    "SharpGLTF.Toolkit": "MIT",
    "SkiaSharp": "MIT",
    "KeyValues2": "MIT",
    "System.IO.Hashing": "MIT",
    "TinyBCSharp": "MIT",
    "TinyEXR.NET": "MIT",
    "Vortice.SPIRV": "MIT",
    "Vortice.SpIRVCross": "MIT",
    "Blake3": "MIT",
    "Microsoft.NET.ILLink.Tasks": "MIT",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_tree(source: Path, target: Path, *, ignore_names: set[str] | None = None) -> None:
    if not source.is_dir():
        raise SystemExit(f"missing source directory: {source}")
    ignore_names = ignore_names or set()

    def ignore(directory: str, names: list[str]) -> set[str]:
        ignored = set()
        for name in names:
            if name in ignore_names or name == "__pycache__" or name.endswith(".pyc"):
                ignored.add(name)
        return ignored

    shutil.copytree(source, target, ignore=ignore, dirs_exist_ok=True)


def read_version() -> str:
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not version or any(char not in "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ.-" for char in version):
        raise SystemExit(f"unsafe VERSION value: {version!r}")
    return version


def load_nuget_packages(lock_file: Path) -> list[dict]:
    data = json.loads(lock_file.read_text(encoding="utf-8"))
    dependencies = data.get("dependencies", {}).get("net10.0", {})
    packages = []
    for name, record in sorted(dependencies.items()):
        packages.append(
            {
                "name": name,
                "version": record.get("resolved", ""),
                "license": NUGET_LICENSES.get(name, "MIT"),
                "type": record.get("type", "Transitive"),
            }
        )
    return packages


def spdx_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in ".-" else "-" for char in value)
    return "SPDXRef-Package-" + cleaned


def build_sbom(target: Path, version: str, sri_hash: str) -> None:
    packages = [
        {
            "name": "CS2 Map Balance",
            "SPDXID": "SPDXRef-Package-CS2MB",
            "versionInfo": version,
            "downloadLocation": "https://github.com/Shtoblam/cs2mb-tool",
            "filesAnalyzed": False,
            "licenseConcluded": "MIT",
            "licenseDeclared": "MIT",
            "copyrightText": "Copyright (c) 2026 CS2 Map Balance contributors",
        },
        {
            "name": "SRI — Source Resource Inspector",
            "SPDXID": "SPDXRef-Package-SRI",
            "versionInfo": "1.0.0",
            "downloadLocation": "https://github.com/Shtoblam/cs2mb-tool",
            "filesAnalyzed": False,
            "checksums": [{"algorithm": "SHA256", "checksumValue": sri_hash}],
            "licenseConcluded": "MIT",
            "licenseDeclared": "MIT",
            "copyrightText": "Copyright (c) 2026 CS2 Map Balance contributors",
        },
        {
            "name": "three.js",
            "SPDXID": "SPDXRef-Package-three.js",
            "versionInfo": "0.160.0",
            "downloadLocation": "https://www.npmjs.com/package/three/v/0.160.0",
            "filesAnalyzed": False,
            "licenseConcluded": "MIT",
            "licenseDeclared": "MIT",
            "copyrightText": "Copyright (c) 2010-2023 three.js authors",
        },
        {
            "name": "Python",
            "SPDXID": "SPDXRef-Package-Python",
            "versionInfo": PYTHON_VERSION,
            "downloadLocation": "https://www.python.org/ftp/python/3.13.3/python-3.13.3-embed-amd64.zip",
            "filesAnalyzed": False,
            "licenseConcluded": PYTHON_LICENSE,
            "licenseDeclared": PYTHON_LICENSE,
            "copyrightText": "Copyright (c) Python Software Foundation",
        },
    ]
    for package in load_nuget_packages(SRI_SOURCE / "Cs2mb.Sri" / "packages.lock.json"):
        identifier = spdx_id(package["name"])
        packages.append(
            {
                "name": package["name"],
                "SPDXID": identifier,
                "versionInfo": package["version"],
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": package["license"],
                "licenseDeclared": package["license"],
                "copyrightText": "NOASSERTION",
            }
        )
    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"CS2MB-{version}",
        "documentNamespace": f"https://github.com/Shtoblam/cs2mb-tool/spdx/CS2MB-{version}",
        "creationInfo": {
            "created": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "creators": ["Tool: tools/package_release.py"],
        },
        "packages": packages,
        "relationships": [
            {
                "spdxElementId": "SPDXRef-DOCUMENT",
                "relationshipType": "DESCRIBES",
                "relatedSpdxElement": "SPDXRef-Package-CS2MB",
            }
        ],
    }
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def install_runtime(source: Path, target: Path) -> None:
    if source.is_file() and source.suffix.lower() == ".zip":
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            with zipfile.ZipFile(source) as archive:
                archive.extractall(temporary_path)
            copy_tree(temporary_path, target)
    elif source.is_dir():
        copy_tree(source, target)
    else:
        raise SystemExit(f"unsupported Python runtime source: {source}")
    pth = target / "python313._pth"
    if not pth.is_file():
        raise SystemExit("Python runtime does not contain python313._pth")
    pth.write_text("python313.zip\n.\n..\n", encoding="utf-8")
    license_file = target / "LICENSE.txt"
    if not license_file.is_file():
        raise SystemExit("Python runtime does not contain LICENSE.txt")


def write_notices(target: Path) -> None:
    notices = SRI_NOTICES.read_text(encoding="utf-8")
    notices += """

## Three.js
3DsVW bundles three.js 0.160.0 and its GLTFLoader, OrbitControls and
BufferGeometryUtils addons under `viewer3d/assets/vendor/`. The files are
vendored locally; only module import paths were adjusted to remove bare
specifiers. License: MIT. The upstream license text is included at
`viewer3d/assets/vendor/LICENSE-three.txt`.
Source: https://www.npmjs.com/package/three/v/0.160.0
SHA-256 (package archive): 1ee2f935c4f555814b388e87b5ef78a44856bd2e9d0feb88643a6e193fb42856

## Python runtime

The complete Windows package includes Python 3.13.3 from the official
`python-3.13.3-embed-amd64.zip` distribution, used under the Python Software
Foundation License. The license text is included at `runtime/LICENSE.txt`.

Source: https://www.python.org/ftp/python/3.13.3/python-3.13.3-embed-amd64.zip
SHA-256: 59ff76e16e6597de47474fb22be69e7191a89116910d728ab735079b078e52db
"""
    target.write_text(notices, encoding="utf-8")


def write_checksums(package: Path) -> None:
    sums = []
    for file in sorted(package.rglob("*")):
        if not file.is_file() or file.name == "SHA256SUMS.txt":
            continue
        sums.append(f"{sha256(file)}  {file.relative_to(package).as_posix()}")
    (package / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the complete CS2MB Windows x64 package.")
    parser.add_argument("--python-runtime", required=True, type=Path, help="Extracted Python runtime or official embeddable zip")
    parser.add_argument("--sri", type=Path, default=SRI_EXE)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--keep-staging", action="store_true")
    args = parser.parse_args()

    version = read_version()
    if not args.sri.is_file():
        raise SystemExit(f"SRI executable not found: {args.sri}")
    sri_hash = sha256(args.sri)
    package_name = f"CS2MB-{version}-win-x64"
    output = args.output or DIST / f"{package_name}.zip"
    staging = DIST / "CS2MB"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    DIST.mkdir(parents=True, exist_ok=True)

    for directory in ("app", "movement", "simulation", "prototype", "config", "docs", "viewer3d"):
        copy_tree(ROOT / directory, staging / directory)
    copy_tree(ROOT / "tools", staging / "tools", ignore_names={"bin"})
    (staging / "tools" / "bin" / "sri").mkdir(parents=True)
    shutil.copy2(args.sri, staging / "tools" / "bin" / "sri" / "cs2mb-sri.exe")
    if (ROOT / "tools" / "bin" / "README.md").is_file():
        shutil.copy2(ROOT / "tools" / "bin" / "README.md", staging / "tools" / "bin" / "README.md")
    copy_tree(
        SRI_SOURCE,
        staging / "sri",
        ignore_names={"bin", "obj", "dist", "publish"},
    )
    copy_tree(ROOT / "packaging", staging)

    for name in (
        "LICENSE",
        "VERSION",
        "README.md",
        "README.ru.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "AGENTS.md",
        "logo.png",
    ):
        source = ROOT / name
        if not source.is_file():
            raise SystemExit(f"missing release file: {source}")
        shutil.copy2(source, staging / name)
    shutil.copy2(ROOT / "docs" / "SECURITY.md", staging / "SECURITY.md")
    shutil.copy2(ROOT / "docs" / "SECURITY.ru.md", staging / "SECURITY.ru.md")
    if (ROOT / "inputs" / "README.md").is_file():
        (staging / "inputs").mkdir(exist_ok=True)
        shutil.copy2(ROOT / "inputs" / "README.md", staging / "inputs" / "README.md")

    install_runtime(args.python_runtime.expanduser().resolve(), staging / "runtime")
    write_notices(staging / "THIRD_PARTY_NOTICES.md")
    build_sbom(staging / "SBOM.spdx.json", version, sri_hash)
    write_checksums(staging)

    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(staging.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(staging.parent))

    print(f"package: {output}")
    print(f"size: {output.stat().st_size}")
    print(f"sha256: {sha256(output)}")
    if not args.keep_staging:
        shutil.rmtree(staging)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
