#!/usr/bin/env python3
"""Build an apktool project, zipalign it, and optionally sign it.

Passwords are never taken from the command line. Set the environment variables
named by --ks-pass-env / --key-pass-env (defaults: KS_PASS and KEY_PASS).

Example (Git Bash):
    export KS_PASS='***'
    export KEY_PASS='***'
    py scripts/build_apk.py --theme-dir theme --apktool apktool.jar \\
        --build-tools "$ANDROID_HOME/build-tools/36.0.0" \\
        --keystore key.jks --ks-alias mykey --out theme-signed.apk

Without --keystore the aligned, unsigned APK is produced.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    if os.name == "nt" and cmd and str(cmd[0]).lower().endswith(".bat"):
        cmd = ["cmd", "/c", *cmd]
    print("+ " + subprocess.list2cmdline([str(c) for c in cmd]))
    subprocess.run([str(c) for c in cmd], check=True)


def find_tool(build_tools: Path | None, name: str) -> str:
    if build_tools:
        for ext in (".exe", ".bat", ""):
            candidate = build_tools / f"{name}{ext}"
            if candidate.exists():
                return str(candidate)
    found = shutil.which(name)
    if not found:
        raise SystemExit(f"error: {name} not found; pass --build-tools")
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theme-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--apktool", default="apktool.jar", type=Path)
    ap.add_argument("--build-tools", type=Path)
    ap.add_argument("--java", default="java")
    ap.add_argument("--keystore", type=Path)
    ap.add_argument("--ks-alias")
    ap.add_argument("--ks-pass-env", default="KS_PASS")
    ap.add_argument("--key-pass-env", default="KEY_PASS")
    ap.add_argument("--no-v1", action="store_true")
    ap.add_argument("--no-v2", action="store_true")
    ap.add_argument("--no-v3", action="store_true")
    args = ap.parse_args()

    theme = args.theme_dir.resolve()
    if not (theme / "apktool.yml").exists():
        raise SystemExit(f"error: {theme} is not an apktool project")

    unsigned = args.out.with_name(args.out.stem + "-unsigned.apk")
    aligned = args.out.with_name(args.out.stem + "-aligned.apk")

    run([args.java, "-jar", str(args.apktool), "b", str(theme), "-o", str(unsigned)])

    zipalign = find_tool(args.build_tools, "zipalign")
    run([zipalign, "-f", "-p", "4", str(unsigned), str(aligned)])

    if not args.keystore:
        print(f"\nunsigned APK: {aligned}")
        return 0

    if not args.ks_alias:
        raise SystemExit("error: --ks-alias is required when signing")
    ks_pass = os.environ.get(args.ks_pass_env)
    key_pass = os.environ.get(args.key_pass_env) or ks_pass
    if not ks_pass:
        raise SystemExit(f"error: environment variable {args.ks_pass_env} is empty")

    apksigner = find_tool(args.build_tools, "apksigner")
    cmd = [
        apksigner, "sign",
        "--ks", str(args.keystore),
        "--ks-key-alias", args.ks_alias,
        "--ks-pass", f"env:{args.ks_pass_env}",
        "--key-pass", f"env:{args.key_pass_env}",
        "--v1-signing-enabled", "false" if args.no_v1 else "true",
        "--v2-signing-enabled", "false" if args.no_v2 else "true",
        "--v3-signing-enabled", "false" if args.no_v3 else "true",
        "--out", str(args.out), str(aligned),
    ]
    run(cmd)
    run([apksigner, "verify", "--print-certs", str(args.out)])
    print(f"\nsigned APK: {args.out}")
    print("note: a system-installed theme with a different signature cannot be")
    print("      updated in place; use a renamed package or a Magisk overlay.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
