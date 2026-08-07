#!/usr/bin/env python3
# Copyright (C) 2026 Quicklocke contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""ROM-backed determinism check for the complete supported randomizer matrix."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE_ROOT))

from quickloke_patcher import PatchError, apply_recipe, load_recipe


GAMES = ("red", "blue", "yellow", "crystal", "emerald", "firered", "leafgreen")
INSTALLED_LAYOUTS = {"emerald", "firered", "leafgreen"}
SETTINGS = {
    1: "321WRIEAQIZAIUAAACRAAKeBgMECQEAFAABCQAOAgAAAAAAAAho5ATkAQAICTIGBQMyAAIYElBva2Vtb24gWWVsbG93IChVKVXr5SHjwziK",
    2: "321WRIEATIZAIUAAACRAAKeBhsESQEACQAKCQAuAgAAAAAAABgI5ATkAQAICTIGBQMyAAIYF1Bva2Vtb24gQ3J5c3RhbCAoVSAxLjEpW+h5e+PDOIo=",
    3: "427WRIEEjL8AP8AAgGRAALkBAARAAQJAQAJAAIJAC4S/wAAAAAAAAAWBBYBgAgJ5AYEAuQABRgBAAFBAAAAAAAJDAABKAEAC0VtZXJhbGQgKFUpS9JY7wAAAAA=",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_rom(value: str) -> tuple[str, Path]:
    game, separator, path = value.partition("=")
    if not separator or game not in GAMES or not path:
        raise argparse.ArgumentTypeError("ROM must be supplied as supported-game=/path/to/rom")
    return game, Path(path)


def generation(game: str) -> int:
    if game in {"red", "blue", "yellow"}:
        return 1
    if game == "crystal":
        return 2
    return 3


def extension(game: str) -> str:
    return "gba" if generation(game) == 3 else "gbc"


def run_fvx(
    *, java: Path, jar: Path, rom: Path, output: Path, seed: str, settings: str, layout: str
) -> tuple[Path, Path]:
    manifest = output.with_suffix(".fvx.json")
    log = output.with_suffix(".fvx.log")
    result = subprocess.run(
        [
            str(java), "-jar", str(jar), "quicklocke",
            "-i", str(rom), "-o", str(output), "-S", settings, "-z", seed,
            "--manifest", str(manifest), "--log", str(log),
            "--layout", layout,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise PatchError(f"FVX exited {result.returncode}: {detail}")
    return manifest, log


def verify_game(
    *, root: Path, java: Path, jar: Path, game: str, rom: Path, seed: str
) -> dict[str, object]:
    recipe_path = root / "recipes" / f"{game}.json"
    recipe = load_recipe(recipe_path)
    supplied_sha1 = hashlib.sha1(rom.read_bytes()).hexdigest()
    if supplied_sha1 not in {value.lower() for value in recipe["accepted_sha1"]}:
        raise PatchError(f"{game}: clean ROM SHA-1 is not accepted by its public recipe")

    with tempfile.TemporaryDirectory(prefix=f"quicklocke-{game}-") as temporary:
        work = Path(temporary)
        quicklocke = work / f"{game}-quicklocke.{extension(game)}"
        apply_recipe(rom, recipe_path, quicklocke)
        randomized_runs: list[tuple[Path, Path, Path]] = []
        for run in ("a", "b"):
            randomized = work / f"{game}-{run}-randomized.{extension(game)}"
            manifest, log = run_fvx(
                java=java,
                jar=jar,
                rom=quicklocke,
                output=randomized,
                seed=seed,
                settings=SETTINGS[generation(game)],
                layout=f"quicklocke-{game}",
            )
            randomized_runs.append((randomized, manifest, log))

        compared = [
            ("FVX ROM", randomized_runs[0][0], randomized_runs[1][0]),
            ("FVX manifest", randomized_runs[0][1], randomized_runs[1][1]),
            ("FVX log", randomized_runs[0][2], randomized_runs[1][2]),
        ]
        for label, first, second in compared:
            if first.read_bytes() != second.read_bytes():
                raise PatchError(f"{game}: {label} is not deterministic")
        bridge_data = json.loads(randomized_runs[0][1].read_text(encoding="utf-8"))
        if bridge_data["input_layout"] != f"quicklocke-{game}" or bridge_data["next_stage"] != "complete":
            raise PatchError(f"{game}: FVX manifest does not describe a completed layout-aware pipeline")
        quicklocke_bytes = quicklocke.read_bytes()
        randomized_bytes = randomized_runs[0][0].read_bytes()
        configurable = recipe.get("configurable", {})
        protected_offsets = [entry["offset"] for entry in configurable.get("level_caps", [])]
        protected_offsets.extend(
            entry["offset"]
            for name in ("overflow_percent", "debug_flags")
            if (entry := configurable.get(name)) is not None
        )
        if any(quicklocke_bytes[offset] != randomized_bytes[offset] for offset in protected_offsets):
            raise PatchError(f"{game}: FVX changed a Quicklocke configuration byte")
        return {
            "game": game,
            "clean_sha1": supplied_sha1,
            "fvx_sha256": digest(randomized_runs[0][0]),
            "quicklocke_sha256": digest(quicklocke),
            "combined_sha256": digest(randomized_runs[0][0]),
            "input_layout": bridge_data["input_layout"],
            "deterministic": True,
        }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--java", type=Path, default=Path("java"))
    result.add_argument("--fvx-jar", required=True, type=Path)
    result.add_argument("--seed", default="42")
    result.add_argument("--require-all", action="store_true")
    result.add_argument(
        "--rom", action="append", required=True, type=parse_rom,
        metavar="GAME=PATH", help="repeat once for each supported clean owned ROM",
    )
    return result


def main() -> int:
    arguments = parser().parse_args()
    root = SOURCE_ROOT
    supplied = dict(arguments.rom)
    requested = set(supplied)
    unavailable = requested - INSTALLED_LAYOUTS
    if unavailable:
        parser().error("layout adapters are not installed for: " + ", ".join(sorted(unavailable)))
    if arguments.require_all and requested != set(GAMES):
        parser().error("--require-all needs one ROM for every supported game")
    if not requested:
        parser().error("at least one --rom is required")
    try:
        reports = [
            verify_game(
                root=root,
                java=arguments.java,
                jar=arguments.fvx_jar,
                game=game,
                rom=supplied[game],
                seed=arguments.seed,
            )
            for game in GAMES if game in requested
        ]
    except (OSError, PatchError, subprocess.CalledProcessError) as error:
        print(f"randomizer matrix failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"schema": 1, "games": reports}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
