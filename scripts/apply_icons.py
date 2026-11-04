#!/usr/bin/env python3
"""Inject an app-icon pack into an apktool-decoded Hisense Vision theme APK.

How the stock launcher resolves an app icon (com.hmct.vision):

    if theme.predefined_app_pkg_list contains <package>:
        name = <package>.lower().replace('.', '_')
        drawable = theme_resources.getIdentifier(name, "mipmap", <theme package>)

So an adapted icon needs two things:

  1. a mipmap resource named <package_name_lower_with_underscores>
  2. the package name present in array/predefined_app_pkg_list

This script does both. It refuses to add packages that the launcher maps at
component level (see data/launcher_builtin_packages.txt), because the theme
array is package-level and would collapse several distinct icons into one
(e.g. the phone and contacts activities share com.android.contacts).

Supported mapping inputs:

  * ADW / Nova icon-pack appfilter.xml:
        <item component="ComponentInfo{com.foo/...}" drawable="foo.icon"/>
  * CSV (package,drawable), UTF-8, '#' comments allowed:
        com.foo.bar,foo.icon
  * --mapping can be given multiple times; CSV entries override appfilter.

Icon files are looked up as <icons-dir>/<drawable>.png. Existing resources are
overwritten in place (nodpi or xhdpi); new ones go to res/mipmap-xhdpi.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sys
import xml.sax.saxutils as saxutils
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: py -m pip install pillow")

ITEM_RE = re.compile(
    r'<item\s+component="ComponentInfo\{([^/}]+)[^}]*\}"\s+drawable="([^"]+)"'
)
RES_NAME_RE = re.compile(r"[a-z0-9_]+")
ARRAY_RE = re.compile(
    r'(<string-array name="predefined_app_pkg_list">.*?)(\s*</string-array>)', re.S
)
ITEM_RE_XML = re.compile(r"<item>([^<]+)</item>")
PKG_ATTR_RE = re.compile(r'package="[^"]+"')
THEME_NAME_RE = re.compile(r'(<string name="theme_name">)(.*?)(</string>)')


def parse_appfilter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    mapping: dict[str, str] = {}
    for pkg, drawable in ITEM_RE.findall(text):
        mapping.setdefault(pkg, drawable)
    return mapping


def parse_csv(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.reader(fh):
            if not row or row[0].strip().startswith("#"):
                continue
            if len(row) < 2:
                continue
            pkg, drawable = row[0].strip(), row[1].strip()
            if pkg and drawable:
                mapping[pkg] = drawable
    return mapping


def load_package_list(path: Path) -> set[str]:
    pkgs: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            pkgs.add(line)
    return pkgs


def resource_name(pkg: str) -> str:
    return pkg.lower().replace(".", "_")


def prepare_icon(src: Path, dst: Path, size: int) -> None:
    im = Image.open(src)
    if im.size != (size, size):
        resample = getattr(Image, "Resampling", Image).LANCZOS
        im = im.resize((size, size), resample)
    if im.mode not in ("RGBA", "LA", "L", "P"):
        im = im.convert("RGBA")
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst)


def find_target(theme: Path, name: str, density: str) -> Path:
    for folder in ("mipmap-nodpi", f"mipmap-{density}", "mipmap-xhdpi"):
        candidate = theme / "res" / folder / f"{name}.png"
        if candidate.exists():
            return candidate
    return theme / "res" / f"mipmap-{density}" / f"{name}.png"


def patch_manifest(theme: Path, package_name: str | None) -> None:
    man = theme / "AndroidManifest.xml"
    text = man.read_text(encoding="utf-8")
    if package_name:
        if not PKG_ATTR_RE.search(text):
            raise SystemExit("AndroidManifest.xml has no package attribute")
        text = PKG_ATTR_RE.sub(f'package="{package_name}"', text, count=1)
        man.write_text(text, encoding="utf-8")


def patch_theme_name(theme: Path, value: str, locale_dir: str) -> None:
    path = theme / "res" / locale_dir / "strings.xml"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    escaped = saxutils.escape(value)
    text, n = THEME_NAME_RE.subn(
        lambda m: m.group(1) + escaped + m.group(3), text, count=1
    )
    if n:
        path.write_text(text, encoding="utf-8")


def patch_version(theme: Path, version_code: int | None, version_name: str | None) -> None:
    path = theme / "apktool.yml"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if version_code is not None:
        text = re.sub(r"versionCode:\s*\d+", f"versionCode: {version_code}", text, count=1)
    if version_name:
        text = re.sub(r"versionName:\s*.*", f"versionName: {version_name}", text, count=1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theme-dir", required=True, type=Path, help="apktool-decoded theme directory")
    ap.add_argument("--icons-dir", required=True, type=Path, help="directory containing <drawable>.png")
    ap.add_argument("--appfilter", type=Path, help="icon-pack appfilter.xml")
    ap.add_argument("--mapping", type=Path, action="append", default=[], help="CSV mapping (package,drawable)")
    ap.add_argument(
        "--exclude-file",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data" / "launcher_builtin_packages.txt",
        help="packages the launcher maps at component level (default: bundled list)",
    )
    ap.add_argument("--package-name", help="new package name for the theme APK")
    ap.add_argument("--theme-name-zh", help="replace theme_name in values-zh-rCN")
    ap.add_argument("--theme-name-en", help="replace theme_name in values")
    ap.add_argument("--version-code", type=int)
    ap.add_argument("--version-name")
    ap.add_argument("--icon-size", type=int, default=156)
    ap.add_argument("--density", default="xhdpi")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    theme = args.theme_dir.resolve()
    arrays = theme / "res" / "values" / "arrays.xml"
    if not arrays.exists():
        return fail(f"{arrays} not found; is --theme-dir an apktool decode of a theme APK?")

    arrays_text = arrays.read_text(encoding="utf-8")
    block = ARRAY_RE.search(arrays_text)
    if not block:
        return fail("array/predefined_app_pkg_list not found in res/values/arrays.xml")
    stock = set(ITEM_RE_XML.findall(block.group(1)))

    mapping: dict[str, str] = {}
    if args.appfilter:
        mapping.update(parse_appfilter(args.appfilter))
    for path in args.mapping:
        mapping.update(parse_csv(path))

    if not mapping:
        return fail("no mappings found (use --appfilter and/or --mapping)")

    builtin: set[str] = set()
    if args.exclude_file and args.exclude_file.exists():
        builtin = load_package_list(args.exclude_file)
    excluded = (builtin - stock)
    if not stock:
        print("warning: stock theme has an empty predefined_app_pkg_list", file=sys.stderr)

    # Resource-name collisions after lowercasing.
    seen: dict[str, str] = {}
    for pkg in mapping:
        name = resource_name(pkg)
        if not RES_NAME_RE.fullmatch(name):
            return fail(f"invalid resource name for package {pkg!r}: {name!r}")
        if name in seen and seen[name] != pkg:
            return fail(f"resource-name collision: {seen[name]} and {pkg} -> {name}")
        seen[name] = pkg

    added_icons = overwritten = skipped_excluded = missing = 0
    new_pkgs: list[str] = []
    for pkg, drawable in sorted(mapping.items()):
        if pkg in excluded:
            skipped_excluded += 1
            continue
        src = args.icons_dir / f"{drawable}.png"
        if not src.exists():
            print(f"missing icon: {pkg} -> {drawable}.png", file=sys.stderr)
            missing += 1
            continue
        name = resource_name(pkg)
        dst = find_target(theme, name, args.density)
        existed = dst.exists()
        if args.dry_run:
            print(f"{'overwrite' if existed else 'add':9} {dst.relative_to(theme)}  ({pkg})")
        else:
            prepare_icon(src, dst, args.icon_size)
        if existed:
            overwritten += 1
        else:
            added_icons += 1
        if pkg not in stock:
            new_pkgs.append(pkg)

    if new_pkgs:
        insert = "".join(f"\n        <item>{pkg}</item>" for pkg in new_pkgs)
        arrays_text, n = ARRAY_RE.subn(
            lambda m: m.group(1) + insert + m.group(2), arrays_text, count=1
        )
        if n != 1:
            return fail("failed to update predefined_app_pkg_list")
        if not args.dry_run:
            arrays.write_text(arrays_text, encoding="utf-8")

    if not args.dry_run:
        patch_manifest(theme, args.package_name)
        if args.theme_name_zh:
            patch_theme_name(theme, args.theme_name_zh, "values-zh-rCN")
        if args.theme_name_en:
            patch_theme_name(theme, args.theme_name_en, "values")
        patch_version(theme, args.version_code, args.version_name)

    print()
    print(f"mapping entries       : {len(mapping)}")
    print(f"excluded (component)  : {skipped_excluded}")
    print(f"icons added           : {added_icons}")
    print(f"icons overwritten     : {overwritten}")
    print(f"icons missing         : {missing}")
    print(f"packages appended     : {len(new_pkgs)}")
    print(f"resulting array size  : {len(stock) + len(new_pkgs)}")
    if args.dry_run:
        print("dry run: nothing written")
    return 0


def fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
