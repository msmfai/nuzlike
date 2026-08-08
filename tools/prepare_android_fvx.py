#!/usr/bin/env python3
# Copyright (C) 2026 NuzLike contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install the pinned FVX engine into Tauri's generated Android project."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "src-tauri" / "gen" / "android" / "app"
DEPENDENCY = '    implementation(files("libs/UPR-FVX.jar"))\n'
KEEP_RULES = """\
-keep class org.nuzlike.patcher.NuzLikeFvx { *; }
-dontwarn java.awt.**
-dontwarn javax.naming.**
-dontwarn javax.print.**
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", required=True, type=Path)
    args = parser.parse_args()
    if not args.jar.is_file():
        parser.error(f"FVX JAR does not exist: {args.jar}")
    gradle = APP / "build.gradle.kts"
    if not gradle.is_file():
        parser.error("run `npm run android:init -- --ci` before preparing FVX")

    libs = APP / "libs"
    libs.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.jar, libs / "UPR-FVX.jar")

    # Tauri validates every resource declared by the shared desktop/mobile
    # configuration before compiling the Android library. Android executes FVX
    # through ART from app/libs, but these paths must still exist for validation.
    resources = ROOT / "src-tauri" / "resources"
    engine_resource = resources / "engines" / "UPR-FVX.jar"
    engine_resource.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.jar, engine_resource)
    runtime = resources / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / ".android-placeholder").write_text(
        "Android uses ART; no desktop Java runtime is required.\n",
        encoding="utf-8",
    )

    destination = APP / "src" / "main" / "java" / "org" / "nuzlike" / "patcher" / "NuzLikeFvx.kt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "src-tauri" / "android" / "NuzLikeFvx.kt", destination)

    text = gradle.read_text(encoding="utf-8")
    if DEPENDENCY.strip() not in text:
        marker = "dependencies {\n"
        if text.count(marker) != 1:
            parser.error("generated Android dependency block changed")
        text = text.replace(marker, marker + DEPENDENCY, 1)
        gradle.write_text(text, encoding="utf-8")

    proguard = APP / "proguard-rules.pro"
    rules = proguard.read_text(encoding="utf-8") if proguard.exists() else ""
    if KEEP_RULES.strip() not in rules:
        proguard.write_text(
            rules + ("\n" if rules and not rules.endswith("\n") else "") + KEEP_RULES,
            encoding="utf-8",
        )
    print(f"Installed Android FVX engine from {args.jar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
