from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


class PatchError(ValueError):
    """A recipe or input failed a safety check."""


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
    if not isinstance(recipe["writes"], list) or not recipe["writes"]:
        raise PatchError("writes must be a non-empty list")
    return recipe


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


def apply_recipe(
    input_path: str | Path, recipe_path: str | Path, output_path: str | Path
) -> dict[str, Any]:
    source = Path(input_path)
    destination = Path(output_path)
    try:
        if source.resolve() == destination.resolve():
            raise PatchError("refusing to overwrite the input; choose a separate output")
        original = source.read_bytes()
    except OSError as error:
        raise PatchError(f"cannot read input {source}: {error}") from error

    recipe = load_recipe(recipe_path)
    input_sha1 = _digest("sha1", original)
    canonical = input_sha1.lower() in {item.lower() for item in recipe["accepted_sha1"]}
    modified_allowed = recipe.get("allow_modified_input") is True
    if not canonical and not modified_allowed:
        raise PatchError(f"unsupported input SHA-1: {input_sha1}")
    if not canonical and not recipe["fingerprints"]:
        raise PatchError("modified-input mode requires at least one invariant fingerprint")

    for index, fingerprint in enumerate(recipe["fingerprints"]):
        _check_region(original, fingerprint, f"fingerprints[{index}]")

    output = bytearray(original)
    occupied: list[tuple[int, int]] = []
    for index, write in enumerate(recipe["writes"]):
        offset, expected = _check_region(original, write, f"writes[{index}]")
        replacement = _hex(write.get("replacement_hex"), f"writes[{index}].replacement_hex")
        if len(replacement) != len(expected):
            raise PatchError(f"writes[{index}] changes file length")
        end = offset + len(expected)
        if any(offset < prior_end and prior_offset < end for prior_offset, prior_end in occupied):
            raise PatchError(f"writes[{index}] overlaps another write")
        occupied.append((offset, end))
        output[offset:end] = replacement

    result = bytes(output)
    output_sha256 = _digest("sha256", result)
    canonical_expected = recipe.get("canonical_output_sha256")
    if canonical and canonical_expected and output_sha256.lower() != canonical_expected.lower():
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

    return {
        "recipe": recipe["id"],
        "game": recipe["game"],
        "input_sha1": input_sha1,
        "input_kind": "canonical" if canonical else "compatible-modified",
        "output_sha256": output_sha256,
        "writes": len(recipe["writes"]),
        "output": str(destination),
    }

