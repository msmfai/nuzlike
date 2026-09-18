#!/usr/bin/env python3
# Copyright (C) 2026 NuzLike contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Prepare private browser parity fixtures from explicitly supplied owned ROMs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from verify_randomizer_matrix import (
    GAMES, SETTINGS, SOURCE_ROOT, apply_recipe, compose_randomized_rom,
    extension, generation, parse_rom, run_fvx,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", action="append", type=parse_rom, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--java", type=Path, required=True)
    parser.add_argument("--fvx-jar", type=Path, required=True)
    args = parser.parse_args()
    roms = dict(args.rom)
    if set(roms) != set(GAMES):
        parser.error("Supply exactly all seven supported games")
    args.output.mkdir(parents=True, exist_ok=True)
    work = args.output.resolve()
    rows = []
    presets = json.loads((SOURCE_ROOT / "configs/presets/level_caps.json").read_text())["games"]
    for game in GAMES:
        rom = roms[game].resolve()
        clean_hash = hashlib.sha256(rom.read_bytes()).hexdigest()
        for mode in ("default", "configured", "debug", "header", "fvx"):
            config = json.loads((SOURCE_ROOT / f"configs/{game}.json").read_text())
            if mode == "configured":
                config["level_caps"] = presets[game]["hard"]
                config["overflow_percent"] = 23
            if mode == "debug":
                config["debug"] = {key: True for key in config["debug"]}
            config_path = work / f"{game}-{mode}.config.json"
            config_path.write_text(json.dumps(config))
            source = rom
            if mode == "header":
                source = work / f"{game}-header-input.{extension(game)}"
                source.write_bytes(bytes(512) + rom.read_bytes())
            output = work / f"{game}-{mode}.{extension(game)}"
            row = {"game": game, "mode": mode, "input": str(source)}
            recipe = SOURCE_ROOT / f"recipes/{game}.json"
            if mode == "fvx":
                randomized = work / f"{game}-randomized.{extension(game)}"
                manifest, _ = run_fvx(java=args.java, jar=args.fvx_jar.resolve(), rom=rom,
                                     output=randomized, seed="20260918", settings=SETTINGS[generation(game)])
                compose_randomized_rom(clean_rom=rom, randomized_rom=randomized, manifest_path=manifest,
                                       recipe_path=recipe, output_rom=output,
                                       output_manifest=work / f"{game}-combined.json", config_path=config_path)
                row.update(randomized=str(randomized), manifest=str(manifest))
            else:
                apply_recipe(source, recipe, output, config_path=config_path)
            row["sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
            rows.append(row)
        assert hashlib.sha256(rom.read_bytes()).hexdigest() == clean_hash
    (work / "matrix.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(f"Prepared {len(rows)} cases in {work / 'matrix.json'}")


if __name__ == "__main__":
    main()
