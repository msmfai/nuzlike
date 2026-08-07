# Copyright (C) 2026 Quicklocke contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import json
import re
import zlib
from pathlib import Path
from typing import Any, Iterable

from .patcher import PatchError, load_recipe


RANDOMIZER_MANIFEST_SCHEMA = 1
RANDOMIZER_ENGINE = "upr-fvx-quicklocke"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")
_SIGNED_64_MIN = -(2**63)
_SIGNED_64_MAX = 2**63 - 1


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
        raise PatchError("randomizer manifest must be an object using schema 1")

    required = {
        "schema",
        "engine",
        "engine_version",
        "upstream_base_revision",
        "seed",
        "settings",
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
    for field in ("input_size", "randomized_size"):
        if not isinstance(manifest[field], int) or isinstance(manifest[field], bool) or manifest[field] < 0:
            raise PatchError(f"randomizer manifest {field} must be a non-negative integer")
    for field in ("input_sha256", "randomized_sha256", "randomizer_log_sha256"):
        digest = manifest[field]
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest.lower()):
            raise PatchError(f"randomizer manifest {field} must be a SHA-256 digest")
    if not isinstance(manifest["fvx_check_value"], int) or isinstance(manifest["fvx_check_value"], bool):
        raise PatchError("randomizer manifest fvx_check_value must be an integer")
    if manifest["next_stage"] != "quicklocke":
        raise PatchError("randomizer manifest is not intended for the Quicklocke stage")
    if not isinstance(manifest["warnings"], list) or not all(
        isinstance(warning, str) for warning in manifest["warnings"]
    ):
        raise PatchError("randomizer manifest warnings must be a list of text")

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
        raise PatchError("FVX changed the ROM size; this Quicklocke recipe cannot be safely composed")
    return manifest


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
    """Resolve every byte range Quicklocke may mutate for collision checks."""
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
    quicklocke_ranges = recipe_write_ranges(recipe)
    collisions = _intersections(randomizer_ranges, quicklocke_ranges)
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
        "quicklocke_write_ranges": [
            {"start": start, "end": end} for start, end in quicklocke_ranges
        ],
        "collisions": [
            {
                "start": start,
                "end": end,
                "message": (
                    f"FVX and Quicklocke both change ROM bytes 0x{start:x}-0x{end - 1:x}; "
                    "this option combination needs an explicit composition rule"
                ),
            }
            for start, end in collisions
        ],
    }
