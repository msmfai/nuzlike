# Copyright (C) 2026 NuzLike contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
import zlib
from pathlib import Path
from typing import Any, Iterable

from .patcher import (
    PatchError,
    apply_recipe,
    load_config,
    load_recipe,
    repair_cartridge_checksum,
)


RANDOMIZER_MANIFEST_SCHEMA = 3
RANDOMIZER_ENGINE = "upr-fvx-nuzlike"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")
_SIGNED_64_MIN = -(2**63)
_SIGNED_64_MAX = 2**63 - 1
_SEMANTIC_FIELDS = {
    "starters_mode",
    "evolutions_mode",
    "movesets_mode",
    "trainers_mode",
    "trainer_levels_modified",
    "trainer_level_modifier",
    "additional_boss_pokemon",
    "additional_important_pokemon",
    "additional_regular_pokemon",
    "wild_randomized",
    "wild_zone_mode",
    "wild_type_mode",
    "wild_evolution_mode",
    "wild_levels_modified",
    "wild_level_modifier",
    "static_pokemon_mode",
    "static_levels_modified",
    "static_level_modifier",
    "tm_moves_mode",
    "tm_hm_compatibility_mode",
    "full_hm_compatibility",
    "keep_field_move_tms",
    "field_items_mode",
    "shop_items_mode",
    "balance_shop_prices",
    "cheap_rare_candies",
    "misc_tweaks",
}
_SEMANTIC_ENUMS = {
    "starters_mode": {"UNCHANGED", "CUSTOM", "COMPLETELY_RANDOM", "RANDOM_WITH_TWO_EVOLUTIONS", "RANDOM_BASIC"},
    "evolutions_mode": {"UNCHANGED", "RANDOM", "RANDOM_EVERY_LEVEL"},
    "movesets_mode": {"UNCHANGED", "RANDOM_PREFER_SAME_TYPE", "COMPLETELY_RANDOM", "METRONOME_ONLY"},
    "trainers_mode": {"UNCHANGED", "RANDOM", "DISTRIBUTED", "MAINPLAYTHROUGH", "TYPE_THEMED", "TYPE_THEMED_ELITE4_GYMS", "KEEP_THEMED", "KEEP_THEME_OR_PRIMARY"},
    "wild_zone_mode": {"NONE", "ENCOUNTER_SET", "MAP", "NAMED_LOCATION", "GAME"},
    "wild_type_mode": {"NONE", "RANDOM_THEMES", "KEEP_PRIMARY"},
    "wild_evolution_mode": {"NONE", "BASIC_ONLY", "KEEP_STAGE"},
    "static_pokemon_mode": {"UNCHANGED", "RANDOM_MATCHING", "COMPLETELY_RANDOM", "SIMILAR_STRENGTH"},
    "tm_moves_mode": {"UNCHANGED", "RANDOM"},
    "tm_hm_compatibility_mode": {"UNCHANGED", "RANDOM_PREFER_TYPE", "COMPLETELY_RANDOM", "FULL"},
    "field_items_mode": {"UNCHANGED", "SHUFFLE", "RANDOM", "RANDOM_EVEN"},
    "shop_items_mode": {"UNCHANGED", "SHUFFLE", "RANDOM"},
}
_SEMANTIC_BOOLEANS = {
    "trainer_levels_modified",
    "wild_randomized",
    "wild_levels_modified",
    "static_levels_modified",
    "full_hm_compatibility",
    "keep_field_move_tms",
    "balance_shop_prices",
    "cheap_rare_candies",
}
_SEMANTIC_INTEGERS = _SEMANTIC_FIELDS - set(_SEMANTIC_ENUMS) - _SEMANTIC_BOOLEANS


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_randomizer_manifest(
    path: str | Path,
    *,
    clean_rom: str | Path,
    randomized_rom: str | Path,
) -> dict[str, Any]:
    """Load an FVX bridge manifest and bind it to the exact supplied files."""
    manifest_path = Path(path)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PatchError(f"cannot read randomizer manifest {manifest_path}: {error}") from error
    if not isinstance(manifest, dict) or manifest.get("schema") != RANDOMIZER_MANIFEST_SCHEMA:
        raise PatchError("randomizer manifest must be an object using schema 3")

    required = {
        "schema",
        "engine",
        "engine_version",
        "upstream_base_revision",
        "seed",
        "settings",
        "input_layout",
        "semantic_settings",
        "rom_name",
        "rom_code",
        "generation",
        "default_extension",
        "input_size",
        "input_sha256",
        "randomized_size",
        "randomized_sha256",
        "randomizer_log_sha256",
        "fvx_check_value",
        "next_stage",
        "warnings",
    }
    missing = required - set(manifest)
    if missing:
        raise PatchError(
            "randomizer manifest is missing: " + ", ".join(sorted(missing))
        )
    unknown = set(manifest) - required
    if unknown:
        raise PatchError(
            "randomizer manifest has unsupported fields: " + ", ".join(sorted(unknown))
        )
    if manifest["engine"] != RANDOMIZER_ENGINE:
        raise PatchError(f"unsupported randomizer engine {manifest['engine']!r}")
    if not isinstance(manifest["engine_version"], str) or not manifest["engine_version"].startswith("FVX "):
        raise PatchError("randomizer manifest engine_version must identify FVX")
    revision = manifest["upstream_base_revision"]
    if not isinstance(revision, str) or not _REVISION.fullmatch(revision.lower()):
        raise PatchError("randomizer manifest upstream_base_revision must be a Git revision")
    seed = manifest["seed"]
    if not isinstance(seed, str):
        raise PatchError("randomizer manifest seed must be a decimal string")
    try:
        parsed_seed = int(seed, 10)
    except ValueError as error:
        raise PatchError("randomizer manifest seed must be a signed 64-bit integer") from error
    if str(parsed_seed) != seed or not _SIGNED_64_MIN <= parsed_seed <= _SIGNED_64_MAX:
        raise PatchError("randomizer manifest seed must be a canonical signed 64-bit integer")
    for field in ("settings", "rom_name", "rom_code", "default_extension"):
        if not isinstance(manifest[field], str) or not manifest[field]:
            raise PatchError(f"randomizer manifest {field} must be non-empty text")
    if manifest["generation"] not in (1, 2, 3):
        raise PatchError("randomizer manifest generation must be 1, 2, or 3")
    if manifest["input_layout"] != "vanilla":
        raise PatchError("this composition path requires an FVX vanilla input layout")
    for field in ("input_size", "randomized_size"):
        if not isinstance(manifest[field], int) or isinstance(manifest[field], bool) or manifest[field] < 0:
            raise PatchError(f"randomizer manifest {field} must be a non-negative integer")
    for field in ("input_sha256", "randomized_sha256", "randomizer_log_sha256"):
        digest = manifest[field]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest.lower()):
            raise PatchError(f"randomizer manifest {field} must be a SHA-256 digest")
    if not isinstance(manifest["fvx_check_value"], int) or isinstance(manifest["fvx_check_value"], bool):
        raise PatchError("randomizer manifest fvx_check_value must be an integer")
    if manifest["next_stage"] != "nuzlike":
        raise PatchError("randomizer manifest is not intended for the NuzLike stage")
    if not isinstance(manifest["warnings"], list) or not all(
        isinstance(warning, str) for warning in manifest["warnings"]
    ):
        raise PatchError("randomizer manifest warnings must be a list of text")
    _validate_semantic_settings(manifest["semantic_settings"])

    try:
        clean = Path(clean_rom).read_bytes()
        randomized = Path(randomized_rom).read_bytes()
    except OSError as error:
        raise PatchError(f"cannot read randomizer pipeline ROM: {error}") from error
    if len(clean) != manifest["input_size"] or _sha256(clean) != manifest["input_sha256"].lower():
        raise PatchError("randomizer manifest does not match the clean input ROM")
    if (
        len(randomized) != manifest["randomized_size"]
        or _sha256(randomized) != manifest["randomized_sha256"].lower()
    ):
        raise PatchError("randomizer manifest does not match the randomized ROM")
    if len(clean) != len(randomized):
        raise PatchError("FVX changed the ROM size; this NuzLike recipe cannot be safely composed")
    return manifest


def _validate_semantic_settings(value: object) -> None:
    if not isinstance(value, dict):
        raise PatchError("randomizer manifest semantic_settings must be an object")
    fields = set(value)
    if fields != _SEMANTIC_FIELDS:
        missing = _SEMANTIC_FIELDS - fields
        unknown = fields - _SEMANTIC_FIELDS
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if unknown:
            details.append("unsupported " + ", ".join(sorted(unknown)))
        raise PatchError("randomizer semantic_settings fields are invalid: " + "; ".join(details))
    for field, accepted in _SEMANTIC_ENUMS.items():
        if value[field] not in accepted:
            raise PatchError(f"randomizer semantic_settings {field} is unsupported")
    for field in _SEMANTIC_BOOLEANS:
        if not isinstance(value[field], bool):
            raise PatchError(f"randomizer semantic_settings {field} must be boolean")
    for field in _SEMANTIC_INTEGERS:
        if not isinstance(value[field], int) or isinstance(value[field], bool):
            raise PatchError(f"randomizer semantic_settings {field} must be an integer")
    for enabled_field, modifier_field in (
        ("trainer_levels_modified", "trainer_level_modifier"),
        ("wild_levels_modified", "wild_level_modifier"),
        ("static_levels_modified", "static_level_modifier"),
    ):
        if not value[enabled_field] and value[modifier_field] != 0:
            raise PatchError(
                f"randomizer semantic_settings {modifier_field} must be zero when disabled"
            )


def semantic_composition_rules(settings: dict[str, Any]) -> list[dict[str, str]]:
    """Explain ownership for FVX settings that share a system with NuzLike."""
    rules = [
        {
            "system": "level_caps",
            "owner": "nuzlike",
            "message": "Player level caps remain the selected fixed NuzLike values and are not recalculated from randomized trainers.",
        },
        {
            "system": "encounters",
            "owner": "nuzlike-runtime",
            "message": "FVX supplies encounter species; NuzLike still enforces capture-item gating, one encounter per area, and duplicate-species exclusion.",
        },
        {
            "system": "hm_progression",
            "owner": "nuzlike-runtime",
            "message": "FVX may change TM/HM compatibility, while NuzLike preserves each HM's direct bag action and story authorization checks.",
        },
        {
            "system": "shops",
            "owner": "nuzlike-final",
            "message": "FVX randomizes ordinary shop contents first; NuzLike then guarantees Gym Passes and discounted EV items in every Poké Mart.",
        },
        {
            "system": "memorial_and_champion",
            "owner": "nuzlike-runtime",
            "message": "Memorial handling and Champion shutdown remain NuzLike rules regardless of randomized species or trainers.",
        },
    ]
    if settings["trainer_levels_modified"]:
        rules.append({
            "system": "randomized_trainer_levels",
            "owner": "fvx",
            "message": (
                f"FVX applies its {settings['trainer_level_modifier']}% trainer-level modifier; "
                "the player cap remains fixed, so this can intentionally make a gym easier or harder."
            ),
        })
    if settings["wild_levels_modified"]:
        rules.append({
            "system": "randomized_wild_levels",
            "owner": "fvx-then-nuzlike",
            "message": (
                f"FVX applies its {settings['wild_level_modifier']}% wild-level modifier, then "
                "NuzLike applies only its pre-first-badge minimum catch-level floor."
            ),
        })
    if settings["field_items_mode"] != "UNCHANGED":
        rules.append({
            "system": "capture_item_gate",
            "owner": "fvx-then-nuzlike-runtime",
            "message": "Randomized field items may change when a catching item is obtained; encounters unlock only after the player actually owns one.",
        })
    return rules


def changed_ranges(before: bytes, after: bytes) -> list[tuple[int, int]]:
    """Return compact half-open ranges containing every changed byte."""
    if len(before) != len(after):
        raise PatchError("cannot compare ROM changes across different file sizes")
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for offset, (left, right) in enumerate(zip(before, after, strict=True)):
        if left != right and start is None:
            start = offset
        elif left == right and start is not None:
            ranges.append((start, offset))
            start = None
    if start is not None:
        ranges.append((start, len(before)))
    return ranges


def _merge_ranges(ranges: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def recipe_write_ranges(recipe: dict[str, Any]) -> list[tuple[int, int]]:
    """Resolve every byte range NuzLike may mutate for collision checks."""
    ranges: list[tuple[int, int]] = []
    source_copy = recipe.get("source_copy")
    if source_copy is not None:
        cursor = 0
        for index, operation in enumerate(source_copy["operations"]):
            if "source_offset" in operation:
                cursor += operation["length"]
                continue
            try:
                field = "xor_b64" if "xor_b64" in operation else "xor_zlib_b64"
                delta = base64.b64decode(operation[field], validate=True)
                if field == "xor_zlib_b64":
                    delta = zlib.decompress(delta)
            except (KeyError, ValueError, zlib.error) as error:
                raise PatchError(f"invalid source_copy operation {index}: {error}") from error
            ranges.append((cursor, cursor + len(delta)))
            cursor += len(delta)
    else:
        for write in recipe["writes"]:
            start = write["offset"]
            ranges.append((start, start + len(bytes.fromhex(write["replacement_hex"]))))

    configurable = recipe.get("configurable", {})
    for cap in configurable.get("level_caps", []):
        ranges.append((cap["offset"], cap["offset"] + 1))
    for name in ("overflow_percent", "debug_flags"):
        entry = configurable.get(name)
        if entry is not None:
            ranges.append((entry["offset"], entry["offset"] + 1))
    if recipe["game"] in {"red", "blue", "yellow", "crystal"}:
        ranges.append((0x14E, 0x150))
    return _merge_ranges(ranges)


def _intersections(
    left: list[tuple[int, int]], right: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    intersections: list[tuple[int, int]] = []
    left_index = 0
    right_index = 0
    while left_index < len(left) and right_index < len(right):
        left_start, left_end = left[left_index]
        right_start, right_end = right[right_index]
        start = max(left_start, right_start)
        end = min(left_end, right_end)
        if start < end:
            intersections.append((start, end))
        if left_end <= right_end:
            left_index += 1
        else:
            right_index += 1
    return _merge_ranges(intersections)


def analyze_randomizer_compatibility(
    *,
    clean_rom: str | Path,
    randomized_rom: str | Path,
    manifest_path: str | Path,
    recipe_path: str | Path,
) -> dict[str, Any]:
    """Verify FVX provenance and report byte collisions before patching."""
    manifest = load_randomizer_manifest(
        manifest_path, clean_rom=clean_rom, randomized_rom=randomized_rom
    )
    recipe = load_recipe(recipe_path)
    clean = Path(clean_rom).read_bytes()
    randomized = Path(randomized_rom).read_bytes()
    randomizer_ranges = changed_ranges(clean, randomized)
    nuzlike_ranges = recipe_write_ranges(recipe)
    collisions = _intersections(randomizer_ranges, nuzlike_ranges)
    semantic_rules = semantic_composition_rules(manifest["semantic_settings"])
    return {
        "compatible": not collisions,
        "game": recipe["game"],
        "engine": manifest["engine"],
        "engine_version": manifest["engine_version"],
        "seed": manifest["seed"],
        "randomizer_changed_bytes": sum(end - start for start, end in randomizer_ranges),
        "randomizer_changed_ranges": [
            {"start": start, "end": end} for start, end in randomizer_ranges
        ],
        "nuzlike_write_ranges": [
            {"start": start, "end": end} for start, end in nuzlike_ranges
        ],
        "collisions": [
            {
                "start": start,
                "end": end,
                "resolution": "nuzlike-final",
                "message": (
                    f"FVX and NuzLike both change ROM bytes 0x{start:x}-0x{end - 1:x}; "
                    "this option combination needs an explicit composition rule"
                ),
            }
            for start, end in collisions
        ],
        "semantic_rules": semantic_rules,
    }


def _effective_config(
    recipe: dict[str, Any], config_path: str | Path | None
) -> dict[str, Any]:
    supplied = (
        load_config(config_path, game=recipe["game"])
        if config_path is not None
        else {"level_caps": {}, "overflow_percent": None, "debug": {}}
    )
    configurable = recipe.get("configurable", {})
    caps = {
        entry["id"]: supplied["level_caps"].get(entry["id"], entry["default"])
        for entry in configurable.get("level_caps", [])
    }
    overflow = configurable.get("overflow_percent")
    overflow_percent = supplied["overflow_percent"]
    if overflow_percent is None and overflow is not None:
        overflow_percent = overflow["default"]
    return {
        "schema": 1,
        "game": recipe["game"],
        "level_caps": caps,
        "overflow_percent": overflow_percent,
        "debug": {
            name: bool(supplied["debug"].get(name, False))
            for name in (
                "infinite_health",
                "maximum_damage",
                "disable_trainer_sight",
            )
        },
    }


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    except OSError as error:
        raise PatchError(f"cannot write output {path}: {error}") from error
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def compose_randomized_rom(
    *,
    clean_rom: str | Path,
    randomized_rom: str | Path,
    manifest_path: str | Path,
    recipe_path: str | Path,
    output_rom: str | Path,
    output_manifest: str | Path,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compose FVX then NuzLike, with NuzLike owning dual-written bytes."""
    output_path = Path(output_rom)
    combined_manifest_path = Path(output_manifest)
    if output_path.exists() or combined_manifest_path.exists():
        raise PatchError("refusing to overwrite an existing composed ROM or manifest")
    if output_path.resolve() == combined_manifest_path.resolve():
        raise PatchError("the composed ROM and manifest must use separate paths")

    compatibility = analyze_randomizer_compatibility(
        clean_rom=clean_rom,
        randomized_rom=randomized_rom,
        manifest_path=manifest_path,
        recipe_path=recipe_path,
    )
    bridge_manifest = load_randomizer_manifest(
        manifest_path, clean_rom=clean_rom, randomized_rom=randomized_rom
    )
    recipe = load_recipe(recipe_path)
    if recipe.get("randomizer_layout") != {"schema": 1, "mode": "identity"}:
        raise PatchError(
            f"{recipe['game']}: no verified FVX layout adapter is installed; "
            "refusing an unsafe offset-based composition"
        )
    clean = Path(clean_rom).read_bytes()
    randomized = Path(randomized_rom).read_bytes()
    effective_config = _effective_config(recipe, config_path)

    with tempfile.TemporaryDirectory(prefix="nuzlike-compose-") as temporary:
        nuzlike_path = Path(temporary) / f"nuzlike.{bridge_manifest['default_extension']}"
        nuzlike_report = apply_recipe(
            clean_rom, recipe_path, nuzlike_path, config_path=config_path
        )
        nuzlike_report.pop("output", None)
        composed = bytearray(nuzlike_path.read_bytes())

    for offset, (clean_byte, randomized_byte) in enumerate(zip(clean, randomized, strict=True)):
        if randomized_byte != clean_byte and composed[offset] == clean_byte:
            composed[offset] = randomized_byte
    repair_cartridge_checksum(composed, recipe["game"])
    final_sha256 = _sha256(bytes(composed))
    nuzlike_report["output_sha256"] = final_sha256
    combined = {
        "schema": 1,
        "pipeline": "upr-fvx-then-nuzlike",
        "randomizer_engine": bridge_manifest["engine"],
        "randomizer_engine_version": bridge_manifest["engine_version"],
        "randomizer_upstream_revision": bridge_manifest["upstream_base_revision"],
        "seed": bridge_manifest["seed"],
        "randomizer_settings": bridge_manifest["settings"],
        "input_sha256": bridge_manifest["input_sha256"],
        "randomized_sha256": bridge_manifest["randomized_sha256"],
        "randomizer_log_sha256": bridge_manifest["randomizer_log_sha256"],
        "fvx_check_value": bridge_manifest["fvx_check_value"],
        "nuzlike_config": effective_config,
        "nuzlike_report": nuzlike_report,
        "final_sha256": final_sha256,
        "semantic_rules": compatibility["semantic_rules"],
        "warnings": bridge_manifest["warnings"],
        "collisions": compatibility["collisions"],
    }
    manifest_bytes = (json.dumps(combined, indent=2, sort_keys=True) + "\n").encode()
    try:
        _atomic_write(output_path, bytes(composed))
        _atomic_write(combined_manifest_path, manifest_bytes)
    except PatchError:
        output_path.unlink(missing_ok=True)
        combined_manifest_path.unlink(missing_ok=True)
        raise
    return combined
