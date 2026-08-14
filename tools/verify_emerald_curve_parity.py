#!/usr/bin/env python3
# Copyright (C) 2026 NuzLike contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prove Python/Rust Emerald curve bytes match for an owned clean ROM."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

CAP_IDS = (
    "roxanne", "brawly", "wattson", "flannery", "norman",
    "winona", "tate_and_liza", "juan", "champion",
)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nuzlike_patcher.emerald_analysis import analyse_emerald, load_emerald_template  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    parser.add_argument("--recipe", type=Path, default=ROOT / "recipes/emerald.json")
    parser.add_argument("--template", type=Path, default=ROOT / "analysis/emerald.json")
    args = parser.parse_args()
    recipe = json.loads(args.recipe.read_text(encoding="utf-8"))
    analysis = recipe["emerald_chapter_xp"]
    defaults = {row["id"]: row["default"] for row in recipe["configurable"]["level_caps"]}
    caps = tuple(defaults[name] for name in CAP_IDS)
    rom = args.rom.read_bytes()
    manifest, expected = analyse_emerald(rom, load_emerald_template(args.template), caps)
    with tempfile.TemporaryDirectory(prefix="nuzlike-emerald-parity-") as directory:
        probe = Path(directory) / "probe"
        subprocess.run([
            "rustc", "--edition=2024", str(ROOT / "tools/emerald_curve_probe.rs"),
            "-o", str(probe),
        ], check=True)
        actual = subprocess.run([
            str(probe), str(args.rom.resolve()), str(analysis["vanilla_offset"]),
            ",".join(map(str, caps)), ",".join(map(str, analysis["budgets"])),
            ";".join(",".join(map(str, groups)) for groups in analysis["family_growth_groups"]),
        ], check=True, stdout=subprocess.PIPE).stdout
    if actual != expected:
        raise SystemExit("Python and Rust generated different Emerald experience tables")
    print(json.dumps({
        "bytes": len(actual),
        "experience_tables_sha256": manifest["experience_tables_sha256"],
        "status": "identical",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
