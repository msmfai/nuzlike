#!/usr/bin/env python3
# Copyright (C) 2026 NuzLike contributors
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

from nuzlike_patcher import PatchError, apply_recipe, compose_randomized_rom, load_recipe


GAMES = ("red", "blue", "yellow", "crystal", "emerald", "firered", "leafgreen")
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


def discover_roms(directory: Path, accepted: dict[str, str]) -> dict[str, Path]:
    """Identify canonical inputs by content without trusting their filenames."""
    by_sha1 = {digest.lower(): game for game, digest in accepted.items()}
    discovered: dict[str, Path] = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        candidates = [hashlib.sha1(data).hexdigest()]
        if len(data) > 512:
            candidates.append(hashlib.sha1(data[512:]).hexdigest())
        game = next((by_sha1[value] for value in candidates if value in by_sha1), None)
        if game is None:
            continue
        if game in discovered:
            raise PatchError(
                f"multiple canonical inputs found for {game}: "
                f"{discovered[game]} and {path}"
            )
        discovered[game] = path
    return discovered


def generation(game: str) -> int:
    if game in {"red", "blue", "yellow"}:
        return 1
    if game == "crystal":
        return 2
    return 3


def extension(game: str) -> str:
    return "gba" if generation(game) == 3 else "gbc"


def run_fvx(
    *, java: Path, jar: Path, rom: Path, output: Path, seed: str, settings: str
) -> tuple[Path, Path]:
    manifest = output.with_suffix(".fvx.json")
    log = output.with_suffix(".fvx.log")
    result = subprocess.run(
        [
            str(java), "-jar", str(jar), "nuzlike",
            "-i", str(rom), "-o", str(output), "-S", settings, "-z", seed,
            "--manifest", str(manifest), "--log", str(log),
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
    supplied = rom.read_bytes()
    accepted = {value.lower() for value in recipe["accepted_sha1"]}
    supplied_sha1 = hashlib.sha1(supplied).hexdigest()
    normalization = "none"
    if supplied_sha1 not in accepted and len(supplied) > 512:
        normalized = supplied[512:]
        normalized_sha1 = hashlib.sha1(normalized).hexdigest()
        if normalized_sha1 in accepted:
            supplied = normalized
            supplied_sha1 = normalized_sha1
            normalization = "removed-512-byte-copier-header"
    if supplied_sha1 not in accepted:
        raise PatchError(f"{game}: clean ROM SHA-1 is not accepted by its public recipe")

    with tempfile.TemporaryDirectory(prefix=f"nuzlike-{game}-") as temporary:
        work = Path(temporary)
        clean = work / f"{game}-clean.{extension(game)}"
        clean.write_bytes(supplied)
        nuzlike = work / f"{game}-nuzlike.{extension(game)}"
        apply_recipe(clean, recipe_path, nuzlike)
        randomized_runs: list[tuple[Path, Path, Path, Path, Path]] = []
        for run in ("a", "b"):
            randomized = work / f"{game}-{run}-randomized.{extension(game)}"
            manifest, log = run_fvx(
                java=java,
                jar=jar,
                rom=clean,
                output=randomized,
                seed=seed,
                settings=SETTINGS[generation(game)],
            )
            combined = work / f"{game}-{run}-combined.{extension(game)}"
            combined_manifest = work / f"{game}-{run}-combined.json"
            compose_randomized_rom(
                clean_rom=rom,
                randomized_rom=randomized,
                manifest_path=manifest,
                recipe_path=recipe_path,
                output_rom=combined,
                output_manifest=combined_manifest,
            )
            randomized_runs.append((randomized, manifest, log, combined, combined_manifest))

        compared = [
            ("FVX ROM", randomized_runs[0][0], randomized_runs[1][0]),
            ("FVX manifest", randomized_runs[0][1], randomized_runs[1][1]),
            ("FVX log", randomized_runs[0][2], randomized_runs[1][2]),
            ("combined ROM", randomized_runs[0][3], randomized_runs[1][3]),
            ("combined manifest", randomized_runs[0][4], randomized_runs[1][4]),
        ]
        for label, first, second in compared:
            if first.read_bytes() != second.read_bytes():
                raise PatchError(f"{game}: {label} is not deterministic")
        bridge_data = json.loads(randomized_runs[0][1].read_text(encoding="utf-8"))
        if bridge_data["input_layout"] != "vanilla" or bridge_data["next_stage"] != "nuzlike":
            raise PatchError(f"{game}: FVX manifest does not describe the vanilla composition stage")
        nuzlike_bytes = nuzlike.read_bytes()
        combined_bytes = randomized_runs[0][3].read_bytes()
        configurable = recipe.get("configurable", {})
        protected_offsets = [entry["offset"] for entry in configurable.get("level_caps", [])]
        protected_offsets.extend(
            entry["offset"]
            for name in ("overflow_percent", "debug_flags")
            if (entry := configurable.get(name)) is not None
        )
        if any(nuzlike_bytes[offset] != combined_bytes[offset] for offset in protected_offsets):
            raise PatchError(f"{game}: composition changed a NuzLike configuration byte")
        return {
            "game": game,
            "clean_sha1": supplied_sha1,
            "input_normalization": normalization,
            "fvx_sha256": digest(randomized_runs[0][0]),
            "nuzlike_sha256": digest(nuzlike),
            "combined_sha256": digest(randomized_runs[0][3]),
            "input_layout": "vanilla-identity-rebase",
            "deterministic": True,
        }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--java", type=Path, default=Path("java"))
    result.add_argument("--fvx-jar", required=True, type=Path)
    result.add_argument("--seed", default="42")
    result.add_argument("--require-all", action="store_true")
    result.add_argument(
        "--rom-dir", type=Path,
        help="discover supported clean ROMs by content beneath this private directory",
    )
    result.add_argument(
        "--rom", action="append", default=[], type=parse_rom,
        metavar="GAME=PATH", help="repeat once for each supported clean owned ROM",
    )
    return result


def main() -> int:
    argument_parser = parser()
    arguments = argument_parser.parse_args()
    root = SOURCE_ROOT
    supplied = dict(arguments.rom)
    try:
        if arguments.rom_dir is not None:
            manifest = json.loads((root / "recipes/manifest.json").read_text(encoding="utf-8"))
            for game, path in discover_roms(
                arguments.rom_dir, manifest["canonical_inputs"]
            ).items():
                if game in supplied:
                    argument_parser.error(
                        f"{game} was supplied both explicitly and through --rom-dir"
                    )
                supplied[game] = path
    except (OSError, PatchError, json.JSONDecodeError) as error:
        print(f"randomizer input discovery failed: {error}", file=sys.stderr)
        return 2
    requested = set(supplied)
    if arguments.require_all and requested != set(GAMES):
        argument_parser.error("--require-all needs one ROM for every supported game")
    if not requested:
        argument_parser.error("supply at least one --rom or --rom-dir")
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
