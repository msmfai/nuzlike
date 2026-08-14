# Copyright (C) 2026 NuzLike contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import zlib
from pathlib import Path
from typing import Any

from .emerald_analysis import EmeraldAnalysisError, analyse_emerald, load_emerald_template


class PatchError(ValueError):
    """A recipe or input failed a safety check."""


COPIER_HEADER_SIZE = 512


def _digest(algorithm: str, data: bytes) -> str:
    return hashlib.new(algorithm, data).hexdigest()


def _hex(value: Any, field: str) -> bytes:
    if not isinstance(value, str) or len(value) % 2:
        raise PatchError(f"{field} must be an even-length hexadecimal string")
    try:
        return bytes.fromhex(value)
    except ValueError as error:
        raise PatchError(f"{field} is not valid hexadecimal") from error


def _offset(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise PatchError(f"{field} must be a non-negative integer")
    return value


def load_recipe(path: str | Path) -> dict[str, Any]:
    recipe_path = Path(path)
    try:
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PatchError(f"cannot read recipe {recipe_path}: {error}") from error
    if not isinstance(recipe, dict) or recipe.get("schema") != 1:
        raise PatchError("recipe must be an object using schema 1")
    for field in ("id", "game", "accepted_sha1", "fingerprints", "writes"):
        if field not in recipe:
            raise PatchError(f"recipe is missing {field}")
    if not isinstance(recipe["id"], str) or not recipe["id"]:
        raise PatchError("recipe id must be a non-empty string")
    if not isinstance(recipe["game"], str) or not recipe["game"]:
        raise PatchError("recipe game must be a non-empty string")
    if not isinstance(recipe["accepted_sha1"], list) or not all(
        isinstance(item, str) and len(item) == 40 for item in recipe["accepted_sha1"]
    ):
        raise PatchError("accepted_sha1 must be a list of SHA-1 strings")
    if not isinstance(recipe["fingerprints"], list):
        raise PatchError("fingerprints must be a list")
    if not isinstance(recipe["writes"], list):
        raise PatchError("writes must be a list")
    source_copy = recipe.get("source_copy")
    if source_copy is not None:
        if not isinstance(source_copy, dict):
            raise PatchError("source_copy must be an object")
        if set(source_copy) != {"encoding", "output_size", "literal_bytes", "operations"}:
            raise PatchError("source_copy has unsupported or missing fields")
        if source_copy["encoding"] != "source-copy-v1":
            raise PatchError("source_copy encoding must be source-copy-v1")
        _offset(source_copy["output_size"], "source_copy.output_size")
        _offset(source_copy["literal_bytes"], "source_copy.literal_bytes")
        if not isinstance(source_copy["operations"], list) or not source_copy["operations"]:
            raise PatchError("source_copy.operations must be a non-empty list")
    if not recipe["writes"] and source_copy is None:
        raise PatchError("recipe must contain writes or source_copy")
    if recipe["writes"] and source_copy is not None:
        raise PatchError("recipe cannot combine writes and source_copy")
    configurable = recipe.get("configurable", {})
    if not isinstance(configurable, dict):
        raise PatchError("configurable must be an object")
    unknown_configurable = set(configurable) - {"level_caps", "overflow_percent", "debug_flags"}
    if unknown_configurable:
        raise PatchError(
            "unsupported configurable fields: " + ", ".join(sorted(unknown_configurable))
        )
    level_caps = configurable.get("level_caps", [])
    if not isinstance(level_caps, list):
        raise PatchError("configurable.level_caps must be a list")
    seen_cap_ids: set[str] = set()
    seen_configurable_offsets: set[int] = set()
    for index, cap in enumerate(level_caps):
        label = f"configurable.level_caps[{index}]"
        if not isinstance(cap, dict):
            raise PatchError(f"{label} must be an object")
        cap_id = cap.get("id")
        if not isinstance(cap_id, str) or not cap_id:
            raise PatchError(f"{label}.id must be a non-empty string")
        if cap_id in seen_cap_ids:
            raise PatchError(f"duplicate configurable cap id {cap_id}")
        offset = _offset(cap.get("offset"), f"{label}.offset")
        if offset in seen_configurable_offsets:
            raise PatchError(f"duplicate configurable cap offset 0x{offset:x}")
        default = cap.get("default")
        if not isinstance(default, int) or isinstance(default, bool) or not 1 <= default <= 100:
            raise PatchError(f"{label}.default must be an integer from 1 to 100")
        seen_cap_ids.add(cap_id)
        seen_configurable_offsets.add(offset)
    overflow_percent = configurable.get("overflow_percent")
    if overflow_percent is not None:
        if not isinstance(overflow_percent, dict):
            raise PatchError("configurable.overflow_percent must be an object")
        if set(overflow_percent) != {"offset", "default", "minimum", "maximum"}:
            raise PatchError("configurable.overflow_percent has unsupported or missing fields")
        overflow_offset = _offset(
            overflow_percent.get("offset"), "configurable.overflow_percent.offset"
        )
        if overflow_offset in seen_configurable_offsets:
            raise PatchError(f"duplicate configurable offset 0x{overflow_offset:x}")
        seen_configurable_offsets.add(overflow_offset)
        minimum = overflow_percent.get("minimum")
        maximum = overflow_percent.get("maximum")
        default = overflow_percent.get("default")
        if (minimum, maximum) != (0, 100):
            raise PatchError("configurable.overflow_percent range must be 0 through 100")
        if not isinstance(default, int) or isinstance(default, bool) or not minimum <= default <= maximum:
            raise PatchError("configurable.overflow_percent.default must be from 0 through 100")
    debug_flags = configurable.get("debug_flags")
    if debug_flags is not None:
        if not isinstance(debug_flags, dict) or set(debug_flags) != {"offset", "default", "flags"}:
            raise PatchError("configurable.debug_flags has unsupported or missing fields")
        debug_offset = _offset(debug_flags.get("offset"), "configurable.debug_flags.offset")
        if debug_offset in seen_configurable_offsets:
            raise PatchError(f"duplicate configurable offset 0x{debug_offset:x}")
        expected_flags = {
            "infinite_health": 1,
            "maximum_damage": 2,
            "disable_trainer_sight": 4,
        }
        if debug_flags.get("default") != 0 or debug_flags.get("flags") != expected_flags:
            raise PatchError("configurable.debug_flags must declare the supported flags with default 0")
    debug_variant = recipe.get("debug_variant")
    if debug_variant is not None:
        if not isinstance(debug_variant, dict):
            raise PatchError("debug_variant must be an object")
        allowed = {"writes", "source_copy", "configurable", "canonical_output_sha256"}
        if set(debug_variant) - allowed or not {"writes", "configurable"} <= set(debug_variant):
            raise PatchError("debug_variant has unsupported or missing fields")
        if not isinstance(debug_variant["writes"], list):
            raise PatchError("debug_variant.writes must be a list")
        variant_source_copy = debug_variant.get("source_copy")
        if variant_source_copy is not None:
            if (
                not isinstance(variant_source_copy, dict)
                or set(variant_source_copy) != {"encoding", "output_size", "literal_bytes", "operations"}
                or variant_source_copy.get("encoding") != "source-copy-v1"
                or not isinstance(variant_source_copy.get("operations"), list)
                or not variant_source_copy["operations"]
            ):
                raise PatchError("debug_variant.source_copy is invalid")
            _offset(variant_source_copy.get("output_size"), "debug_variant.source_copy.output_size")
            _offset(variant_source_copy.get("literal_bytes"), "debug_variant.source_copy.literal_bytes")
        if bool(debug_variant["writes"]) == bool(variant_source_copy):
            raise PatchError("debug_variant must contain writes or source_copy, but not both")
        if not isinstance(debug_variant["configurable"], dict):
            raise PatchError("debug_variant.configurable must be an object")
        variant_debug = debug_variant["configurable"].get("debug_flags")
        if (
            not isinstance(variant_debug, dict)
            or variant_debug.get("default") != 0
            or variant_debug.get("flags") != expected_flags
        ):
            raise PatchError("debug_variant must declare the supported debug flags")
        canonical_hash = debug_variant.get("canonical_output_sha256")
        if not isinstance(canonical_hash, str) or len(canonical_hash) != 64:
            raise PatchError("debug_variant.canonical_output_sha256 must be a SHA-256 string")
    chapter_xp = recipe.get("emerald_chapter_xp")
    if chapter_xp is not None:
        expected = {
            "schema", "template", "production_offset", "debug_offset",
            "vanilla_offset", "budgets", "family_growth_groups",
        }
        if recipe["game"] != "emerald" or not isinstance(chapter_xp, dict) or set(chapter_xp) != expected:
            raise PatchError("emerald_chapter_xp has unsupported or missing fields")
        if chapter_xp.get("schema") != 1 or not isinstance(chapter_xp.get("template"), str):
            raise PatchError("emerald_chapter_xp must use schema 1 and name a template")
        _offset(chapter_xp.get("production_offset"), "emerald_chapter_xp.production_offset")
        _offset(chapter_xp.get("debug_offset"), "emerald_chapter_xp.debug_offset")
        _offset(chapter_xp.get("vanilla_offset"), "emerald_chapter_xp.vanilla_offset")
        if (
            not isinstance(chapter_xp.get("budgets"), list)
            or len(chapter_xp["budgets"]) != 9
            or not isinstance(chapter_xp.get("family_growth_groups"), list)
            or len(chapter_xp["family_growth_groups"]) != 9
        ):
            raise PatchError("emerald_chapter_xp must contain nine analysis inputs")
    return recipe


def load_config(path: str | Path, *, game: str) -> dict[str, Any]:
    config_path = Path(path)
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PatchError(f"cannot read config {config_path}: {error}") from error
    if not isinstance(config, dict) or config.get("schema") != 1:
        raise PatchError("config must be an object using schema 1")
    unknown = set(config) - {"schema", "game", "level_caps", "overflow_percent", "debug"}
    if unknown:
        raise PatchError("unsupported config fields: " + ", ".join(sorted(unknown)))
    if config.get("game") != game:
        raise PatchError(f"config game must be {game!r}")
    caps = config.get("level_caps", {})
    if not isinstance(caps, dict):
        raise PatchError("config level_caps must be an object")
    for cap_id, level in caps.items():
        if not isinstance(cap_id, str) or not cap_id:
            raise PatchError("config cap ids must be non-empty strings")
        if not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 100:
            raise PatchError(f"config level_caps.{cap_id} must be an integer from 1 to 100")
    overflow_percent = config.get("overflow_percent")
    if (
        overflow_percent is not None
        and (
            not isinstance(overflow_percent, int)
            or isinstance(overflow_percent, bool)
            or not 0 <= overflow_percent <= 100
        )
    ):
        raise PatchError("config overflow_percent must be an integer from 0 through 100")
    debug = config.get("debug", {})
    expected_debug = {"infinite_health", "maximum_damage", "disable_trainer_sight"}
    if not isinstance(debug, dict) or set(debug) - expected_debug:
        raise PatchError("config debug must contain only supported debug toggles")
    if any(not isinstance(value, bool) for value in debug.values()):
        raise PatchError("config debug toggles must be booleans")
    return {
        "level_caps": caps,
        "overflow_percent": overflow_percent,
        "debug": {name: debug.get(name, False) for name in sorted(expected_debug)},
    }


def inspect_input(path: str | Path) -> dict[str, Any]:
    input_path = Path(path)
    try:
        data = input_path.read_bytes()
    except OSError as error:
        raise PatchError(f"cannot read input {input_path}: {error}") from error
    return {
        "path": str(input_path),
        "size": len(data),
        "sha1": _digest("sha1", data),
        "sha256": _digest("sha256", data),
    }


def _check_region(data: bytes, entry: dict[str, Any], label: str) -> tuple[int, bytes]:
    if not isinstance(entry, dict):
        raise PatchError(f"{label} must be an object")
    offset = _offset(entry.get("offset"), f"{label}.offset")
    expected = _hex(entry.get("expected_hex"), f"{label}.expected_hex")
    end = offset + len(expected)
    if end > len(data):
        raise PatchError(f"{label} extends beyond the input")
    if data[offset:end] != expected:
        actual = data[offset:end].hex()
        raise PatchError(
            f"{label} mismatch at 0x{offset:x}: expected {expected.hex()}, got {actual}"
        )
    return offset, expected


def _apply_source_copy(original: bytes, patch: dict[str, Any]) -> bytearray:
    output_size = _offset(patch["output_size"], "source_copy.output_size")
    if output_size != len(original):
        raise PatchError("source_copy must preserve the input size")
    output = bytearray()
    transformed = 0
    for index, operation in enumerate(patch["operations"]):
        label = f"source_copy.operations[{index}]"
        if not isinstance(operation, dict):
            raise PatchError(f"{label} must be an object")
        if set(operation) == {"source_offset", "length"}:
            offset = _offset(operation["source_offset"], f"{label}.source_offset")
            length = _offset(operation["length"], f"{label}.length")
            if length == 0 or offset + length > len(original):
                raise PatchError(f"{label} has an invalid source range")
            output.extend(original[offset:offset + length])
        elif set(operation) in ({"xor_b64"}, {"xor_zlib_b64", "length"}):
            field = "xor_b64" if "xor_b64" in operation else "xor_zlib_b64"
            encoded = operation[field]
            if not isinstance(encoded, str):
                raise PatchError(f"{label}.{field} must be base64 text")
            try:
                delta = base64.b64decode(encoded, validate=True)
                if field == "xor_zlib_b64":
                    delta = zlib.decompress(delta)
            except (ValueError, zlib.error) as error:
                raise PatchError(f"{label}.{field} is invalid: {error}") from error
            if field == "xor_zlib_b64":
                length = _offset(operation["length"], f"{label}.length")
                if len(delta) != length:
                    raise PatchError(f"{label} expands to the wrong length")
            start = len(output)
            end = start + len(delta)
            if end > len(original):
                raise PatchError(f"{label} extends beyond the input")
            output.extend(
                value ^ change
                for value, change in zip(original[start:end], delta, strict=True)
            )
            transformed += len(delta)
        else:
            raise PatchError(f"{label} has an unsupported operation shape")
        if len(output) > output_size:
            raise PatchError("source_copy exceeds its declared output size")
    if len(output) != output_size:
        raise PatchError("source_copy does not fill its declared output size")
    if transformed != patch["literal_bytes"]:
        raise PatchError("source_copy transformed-byte count does not match its declaration")
    return output


def _repair_cartridge_checksum(output: bytearray, game: str) -> None:
    if game not in {"red", "blue", "yellow", "crystal"}:
        return
    if len(output) < 0x150:
        return
    checksum = (sum(output[:0x14E]) + sum(output[0x150:])) & 0xFFFF
    output[0x14E:0x150] = checksum.to_bytes(2, "big")


def repair_cartridge_checksum(output: bytearray, game: str) -> None:
    """Repair the platform checksum after composing independent transformations."""
    _repair_cartridge_checksum(output, game)


def _fingerprints_match(data: bytes, recipe: dict[str, Any]) -> bool:
    try:
        for index, fingerprint in enumerate(recipe["fingerprints"]):
            _check_region(data, fingerprint, f"fingerprints[{index}]")
    except PatchError:
        return False
    return True


def _supported_input(data: bytes, recipe: dict[str, Any]) -> bool:
    input_sha1 = _digest("sha1", data).lower()
    canonical = input_sha1 in {item.lower() for item in recipe["accepted_sha1"]}
    return canonical or (
        recipe.get("allow_modified_input") is True
        and bool(recipe["fingerprints"])
        and _fingerprints_match(data, recipe)
    )


def _normalize_input(data: bytes, recipe: dict[str, Any]) -> tuple[bytes, str]:
    if _supported_input(data, recipe):
        return data, "none"
    if len(data) > COPIER_HEADER_SIZE:
        without_header = data[COPIER_HEADER_SIZE:]
        if _supported_input(without_header, recipe):
            return without_header, "removed-512-byte-copier-header"
    return data, "none"


def apply_recipe(
    input_path: str | Path,
    recipe_path: str | Path,
    output_path: str | Path,
    *,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(input_path)
    destination = Path(output_path)
    try:
        if source.resolve() == destination.resolve():
            raise PatchError("refusing to overwrite the input; choose a separate output")
        supplied = source.read_bytes()
    except OSError as error:
        raise PatchError(f"cannot read input {source}: {error}") from error

    recipe = load_recipe(recipe_path)
    original, input_normalization = _normalize_input(supplied, recipe)
    config = (
        load_config(config_path, game=recipe["game"])
        if config_path
        else {"level_caps": {}, "overflow_percent": None, "debug": {
            "infinite_health": False,
            "maximum_damage": False,
            "disable_trainer_sight": False,
        }}
    )
    cap_overrides = config["level_caps"]
    declared_caps = {
        entry["id"]: entry for entry in recipe.get("configurable", {}).get("level_caps", [])
    }
    unknown_caps = set(cap_overrides) - set(declared_caps)
    if unknown_caps:
        raise PatchError(
            "config contains caps not declared by this recipe: "
            + ", ".join(sorted(unknown_caps))
        )
    overflow_entry = recipe.get("configurable", {}).get("overflow_percent")
    if config["overflow_percent"] is not None and overflow_entry is None:
        raise PatchError("config contains overflow_percent but this recipe does not declare it")
    debug_entry = recipe.get("configurable", {}).get("debug_flags")
    enabled_debug = [name for name, enabled in config["debug"].items() if enabled]
    if enabled_debug and debug_entry is None:
        raise PatchError("config enables debug toggles but this recipe does not declare them")
    patch = recipe.get("debug_variant") if enabled_debug else recipe
    if enabled_debug and patch is None:
        raise PatchError("this recipe has no opt-in debug patch variant")
    patch_configurable = patch.get("configurable", {})
    declared_caps = {
        entry["id"]: entry for entry in patch_configurable.get("level_caps", [])
    }
    unknown_caps = set(cap_overrides) - set(declared_caps)
    if unknown_caps:
        raise PatchError(
            "config contains caps not declared by the selected patch variant: "
            + ", ".join(sorted(unknown_caps))
        )
    overflow_entry = patch_configurable.get("overflow_percent")
    debug_entry = patch_configurable.get("debug_flags")
    input_sha1 = _digest("sha1", original)
    canonical = input_sha1.lower() in {item.lower() for item in recipe["accepted_sha1"]}
    modified_allowed = recipe.get("allow_modified_input") is True
    if not canonical and not modified_allowed:
        raise PatchError(f"unsupported input SHA-1: {input_sha1}")
    if not canonical and not recipe["fingerprints"]:
        raise PatchError("modified-input mode requires at least one invariant fingerprint")

    for index, fingerprint in enumerate(recipe["fingerprints"]):
        _check_region(original, fingerprint, f"fingerprints[{index}]")

    source_copy = patch.get("source_copy")
    output = _apply_source_copy(original, source_copy) if source_copy else bytearray(original)
    occupied: list[tuple[int, int]] = []
    for index, write in enumerate(patch["writes"]):
        offset, expected = _check_region(original, write, f"writes[{index}]")
        replacement = _hex(write.get("replacement_hex"), f"writes[{index}].replacement_hex")
        if len(replacement) != len(expected):
            raise PatchError(f"writes[{index}] changes file length")
        end = offset + len(expected)
        if any(offset < prior_end and prior_offset < end for prior_offset, prior_end in occupied):
            raise PatchError(f"writes[{index}] overlaps another write")
        occupied.append((offset, end))
        output[offset:end] = replacement

    effective_overrides: dict[str, int] = {}
    for cap_id, entry in declared_caps.items():
        offset = entry["offset"]
        if offset >= len(output):
            raise PatchError(f"configurable cap {cap_id} extends beyond the output")
        if output[offset] != entry["default"]:
            raise PatchError(
                f"configurable cap {cap_id} expected generated default "
                f"{entry['default']} at 0x{offset:x}, got {output[offset]}"
            )
        configured = cap_overrides.get(cap_id, entry["default"])
        output[offset] = configured
        if configured != entry["default"]:
            effective_overrides[cap_id] = configured

    configured_overflow_percent: int | None = None
    overflow_percent_changed = False
    if overflow_entry is not None:
        overflow_offset = overflow_entry["offset"]
        if overflow_offset >= len(output):
            raise PatchError("configurable overflow percent extends beyond the output")
        default_overflow_percent = overflow_entry["default"]
        if output[overflow_offset] != default_overflow_percent:
            raise PatchError(
                "configurable overflow percent expected generated default "
                f"{default_overflow_percent} at 0x{overflow_offset:x}, "
                f"got {output[overflow_offset]}"
            )
        configured_overflow_percent = (
            config["overflow_percent"]
            if config["overflow_percent"] is not None
            else default_overflow_percent
        )
        output[overflow_offset] = configured_overflow_percent
        overflow_percent_changed = configured_overflow_percent != default_overflow_percent

    configured_debug = {name: bool(config["debug"].get(name, False)) for name in (
        "infinite_health", "maximum_damage", "disable_trainer_sight"
    )}
    debug_flags_changed = False
    if debug_entry is not None:
        debug_offset = debug_entry["offset"]
        if debug_offset >= len(output):
            raise PatchError("configurable debug flags extend beyond the output")
        if output[debug_offset] != debug_entry["default"]:
            raise PatchError(
                "configurable debug flags expected generated default "
                f"{debug_entry['default']} at 0x{debug_offset:x}, got {output[debug_offset]}"
            )
        mask = sum(debug_entry["flags"][name] for name, enabled in configured_debug.items() if enabled)
        output[debug_offset] = mask
        debug_flags_changed = mask != debug_entry["default"]

    analysis_manifest: dict[str, Any] | None = None
    chapter_xp = recipe.get("emerald_chapter_xp")
    if chapter_xp is not None:
        cap_ids = (
            "roxanne", "brawly", "wattson", "flannery", "norman",
            "winona", "tate_and_liza", "juan", "champion",
        )
        try:
            cap_values = tuple(
                cap_overrides.get(cap_id, declared_caps[cap_id]["default"])
                for cap_id in cap_ids
            )
        except KeyError as error:
            raise PatchError(f"Emerald chapter-XP recipe is missing cap {error.args[0]}") from error
        template_path = Path(recipe_path).resolve().parent / chapter_xp["template"]
        try:
            template = load_emerald_template(template_path)
            analysis_manifest, experience_tables = analyse_emerald(original, template, cap_values)
        except EmeraldAnalysisError as error:
            raise PatchError(f"Emerald chapter-XP analysis failed: {error}") from error
        expected_budgets = [chapter["trainer_xp"] for chapter in analysis_manifest["chapters"]]
        expected_growths = [
            [family["growth_group"] for family in chapter["families"]]
            for chapter in analysis_manifest["chapters"]
        ]
        if expected_budgets != chapter_xp["budgets"] or expected_growths != chapter_xp["family_growth_groups"]:
            raise PatchError("Emerald chapter-XP recipe analysis inputs are stale")
        experience_offset = chapter_xp["debug_offset" if enabled_debug else "production_offset"]
        experience_end = experience_offset + len(experience_tables)
        if experience_end > len(output):
            raise PatchError("generated Emerald experience tables extend beyond the output")
        output[experience_offset:experience_end] = experience_tables

    _repair_cartridge_checksum(output, recipe["game"])

    result = bytes(output)
    output_sha256 = _digest("sha256", result)
    canonical_expected = patch.get("canonical_output_sha256")
    if (
        canonical
        and canonical_expected
        and not effective_overrides
        and not overflow_percent_changed
        and not debug_flags_changed
        and output_sha256.lower() != canonical_expected.lower()
    ):
        raise PatchError(
            "canonical output verification failed: "
            f"expected {canonical_expected}, got {output_sha256}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", dir=destination.parent
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(result)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, destination)
        temporary_name = None
    except OSError as error:
        raise PatchError(f"cannot write output {destination}: {error}") from error
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)

    analysis_output: str | None = None
    if analysis_manifest is not None:
        analysis_path = destination.with_suffix(destination.suffix + ".analysis.json")
        analysis_path.write_text(
            json.dumps(analysis_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        analysis_output = str(analysis_path)

    return {
        "recipe": recipe["id"],
        "game": recipe["game"],
        "input_sha1": input_sha1,
        "input_kind": "canonical" if canonical else "compatible-modified",
        "input_normalization": input_normalization,
        "output_sha256": output_sha256,
        "writes": len(patch["writes"]) if source_copy is None else len(source_copy["operations"]),
        "level_cap_overrides": effective_overrides,
        "overflow_percent": configured_overflow_percent,
        "debug": configured_debug,
        "analysis": analysis_output,
        "experience_tables_sha256": (
            analysis_manifest["experience_tables_sha256"] if analysis_manifest else None
        ),
        "output": str(destination),
    }
