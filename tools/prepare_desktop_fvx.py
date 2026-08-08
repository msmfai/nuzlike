#!/usr/bin/env python3
# Copyright (C) 2026 Quicklocke contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Bundle the pinned FVX engine and a minimal Java 17 runtime for desktop."""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "src-tauri" / "resources"
MODULES = "java.base,java.desktop,java.logging,java.naming"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", required=True, type=Path)
    parser.add_argument("--jlink", default="jlink")
    args = parser.parse_args()
    if not args.jar.is_file():
        parser.error(f"FVX JAR does not exist: {args.jar}")

    engines = RESOURCES / "engines"
    runtime = RESOURCES / "runtime"
    engines.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.jar, engines / "UPR-FVX.jar")
    if runtime.exists():
        shutil.rmtree(runtime)
    subprocess.run(
        [
            args.jlink,
            "--add-modules",
            MODULES,
            "--strip-debug",
            "--no-header-files",
            "--no-man-pages",
            "--output",
            str(runtime),
        ],
        check=True,
    )
    print(f"Installed desktop FVX engine and Java runtime in {RESOURCES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
