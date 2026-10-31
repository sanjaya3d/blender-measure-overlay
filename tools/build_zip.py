#!/usr/bin/env python3
"""Build installable zips for the add-on.

Creates two files in ./dist:

  measure_overlay-<version>-extension.zip   Blender 4.2+ (manifest at zip root)
  measure_overlay-<version>-legacy.zip      Blender 3.0 - 4.1 (classic add-on folder)

Usage:
    python tools/build_zip.py
    python tools/build_zip.py --tag v2.0.0     # also check the git tag matches
"""
import argparse
import ast
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "measure_overlay"
DIST = ROOT / "dist"
MANIFEST = PKG / "blender_manifest.toml"
FIXED_TIME = (2020, 1, 1, 0, 0, 0)  # fixed timestamps = reproducible zips


def read_versions():
    """Return (bl_info version, manifest version) as strings like '2.0.0'."""
    tree = ast.parse((PKG / "__init__.py").read_text(encoding="utf-8"))
    bl_info = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "bl_info" for t in node.targets
        ):
            bl_info = ast.literal_eval(node.value)
    if bl_info is None:
        raise SystemExit("error: bl_info not found in measure_overlay/__init__.py")

    match = re.search(r'^version\s*=\s*"([^"]+)"', MANIFEST.read_text(encoding="utf-8"), re.M)
    if match is None:
        raise SystemExit("error: version not found in blender_manifest.toml")

    return ".".join(str(n) for n in bl_info["version"]), match.group(1)


def package_files():
    for path in sorted(PKG.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        yield path


def write_zip(target, entries):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, arcname in entries:
            info = zipfile.ZipInfo(arcname, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", help="git tag to verify against the version, e.g. v2.0.0")
    args = parser.parse_args()

    py_version, manifest_version = read_versions()
    if py_version != manifest_version:
        sys.exit(f"error: version mismatch: bl_info={py_version}, manifest={manifest_version}")
    if args.tag and args.tag != f"v{py_version}":
        sys.exit(f"error: tag {args.tag} does not match version v{py_version}")

    DIST.mkdir(exist_ok=True)

    # Blender 4.2+ extension: manifest and __init__.py sit at the zip root
    extension = DIST / f"measure_overlay-{py_version}-extension.zip"
    write_zip(extension, [(p, p.relative_to(PKG).as_posix()) for p in package_files()])

    # Legacy add-on: a single measure_overlay/ folder, no manifest
    legacy = DIST / f"measure_overlay-{py_version}-legacy.zip"
    write_zip(legacy, [
        (p, f"measure_overlay/{p.relative_to(PKG).as_posix()}")
        for p in package_files() if p != MANIFEST
    ])

    print(f"Built {extension.relative_to(ROOT)}")
    print(f"Built {legacy.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
