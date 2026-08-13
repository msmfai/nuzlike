#!/usr/bin/env python3
# Copyright (C) 2026 NuzLike contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import zlib
from pathlib import Path


FORBIDDEN_SUFFIXES = {
    ".gb", ".gbc", ".gba", ".sav", ".srm", ".state", ".rom", ".bin",
    ".elf", ".o", ".map", ".ips", ".ups", ".bps", ".xdelta", ".xdelta3",
    ".png", ".bmp", ".wav", ".mid",
}
FORBIDDEN_PARTS = {
    "roms", "upstreams", "work", "toolchains", "decomp", "decomps",
    "assets", "symbols", "maps", "build", "dist", "__pycache__",
}
FORBIDDEN_TEXT = (
    "gitlab" + ".com",
    "/Users" + "/",
    "C:\\Users" + "\\",
    "BEGIN PRIVATE" + " KEY",
)
ALLOWED_ROOTS = {
    ".github", "assets", "branding", "configs", "nuzlike_patcher", "recipes",
    "src-tauri", "tests", "tools", "ui", ".gitignore", "BUILDING.md",
    "LICENSE", "README.md", "RELEASE_NOTES.md", "TESTING.md", "VERSION", "index.html", "package-lock.json",
    "package.json", "pyproject.toml", "tsconfig.json", "vite.config.ts",
}
ALLOWED_BINARY_ASSETS = {
    Path("assets/juno-logo.png"): "771286cb1173c678d0d6cbaac45653e66d732c92cbc66bb977c8850c6b1e2c95",
}
GPL_MARKERS = (
    "GNU GENERAL PUBLIC LICENSE",
    "Version 3, 29 June 2007",
    "Everyone is permitted to copy and distribute verbatim copies",
)
LICENSED_SOURCE_ROOTS = {"nuzlike_patcher", "src-tauri", "tests", "tools", "ui"}
LICENSED_SOURCE_SUFFIXES = {".css", ".py", ".rs", ".ts"}
MAX_RECIPE_FILE_BYTES = 8_000_000
MAX_TRANSFORMED_BYTES = 2 * 1024 * 1024
MAX_TRANSFORMED_FRACTION = 0.10


def validate_recipe(path: Path, data: object) -> list[str]:
    relative = path.as_posix()
    if not isinstance(data, dict) or data.get("schema") != 1:
        return [f"recipe has an invalid schema: {relative}"]
    writes = data.get("writes", [])
    source_copy = data.get("source_copy")
    if bool(writes) == bool(source_copy):
        return [f"recipe must contain exactly one patch body: {relative}"]
    failures: list[str] = []
    if writes:
        transformed = 0
        for index, write in enumerate(writes):
            if not isinstance(write, dict) or set(write) != {
                "offset", "expected_hex", "replacement_hex"
            }:
                failures.append(f"invalid write {index} in {relative}")
                continue
            expected = write.get("expected_hex")
            replacement = write.get("replacement_hex")
            if (
                not isinstance(expected, str)
                or not isinstance(replacement, str)
                or len(expected) != len(replacement)
                or len(expected) % 2
            ):
                failures.append(f"invalid write lengths at {index} in {relative}")
                continue
            try:
                bytes.fromhex(expected)
                bytes.fromhex(replacement)
            except ValueError:
                failures.append(f"invalid write hex at {index} in {relative}")
                continue
            transformed += len(replacement) // 2
        if transformed > MAX_TRANSFORMED_BYTES:
            failures.append(f"recipe changes too many bytes: {relative}")
        return failures

    if not isinstance(source_copy, dict) or set(source_copy) != {
        "encoding", "output_size", "literal_bytes", "operations"
    }:
        return [f"invalid source_copy body: {relative}"]
    if source_copy.get("encoding") != "source-copy-v1":
        failures.append(f"unsupported source_copy encoding: {relative}")
    output_size = source_copy.get("output_size")
    declared = source_copy.get("literal_bytes")
    operations = source_copy.get("operations")
    if (
        not isinstance(output_size, int)
        or output_size <= 0
        or not isinstance(declared, int)
        or declared < 0
        or not isinstance(operations, list)
        or not operations
    ):
        return failures + [f"invalid source_copy declarations: {relative}"]
    produced = 0
    transformed = 0
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            failures.append(f"invalid source_copy operation {index} in {relative}")
            continue
        keys = set(operation)
        try:
            if keys == {"source_offset", "length"}:
                offset = operation["source_offset"]
                length = operation["length"]
                if not isinstance(offset, int) or offset < 0 or not isinstance(length, int) or length <= 0:
                    raise ValueError
                if offset + length > output_size:
                    raise ValueError
                produced += length
            elif keys == {"xor_b64"}:
                delta = base64.b64decode(operation["xor_b64"], validate=True)
                produced += len(delta)
                transformed += len(delta)
            elif keys == {"length", "xor_zlib_b64"}:
                length = operation["length"]
                if not isinstance(length, int) or length <= 0:
                    raise ValueError
                delta = zlib.decompress(
                    base64.b64decode(operation["xor_zlib_b64"], validate=True)
                )
                if len(delta) != length:
                    raise ValueError
                produced += length
                transformed += length
            else:
                raise ValueError
        except (KeyError, TypeError, ValueError, zlib.error):
            failures.append(f"invalid source_copy operation {index} in {relative}")
    if produced != output_size:
        failures.append(f"source_copy output size does not add up: {relative}")
    if transformed != declared:
        failures.append(f"source_copy transformed-byte declaration is wrong: {relative}")
    if transformed > MAX_TRANSFORMED_BYTES or transformed > output_size * MAX_TRANSFORMED_FRACTION:
        failures.append(f"source_copy transforms too much of the input: {relative}")
    return failures


def public_source_paths(root: Path) -> tuple[list[Path], list[str]]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        return [], [f"cannot enumerate public source tree: {result.stderr.decode(errors='replace').strip()}"]
    paths = [Path(value.decode()) for value in result.stdout.split(b"\0") if value]
    return sorted(paths), []


def tracked_history(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "rev-list", "--objects", "--all"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        return [f"cannot inspect Git history: {result.stderr.strip()}"]
    failures: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            object_id = parts[0]
            path = Path(parts[1])
            if any(path in allowed.parents for allowed in ALLOWED_BINARY_ASSETS):
                continue
            allowed_digest = ALLOWED_BINARY_ASSETS.get(path)
            if allowed_digest is not None:
                blob = subprocess.run(
                    ["git", "cat-file", "blob", object_id],
                    cwd=root,
                    capture_output=True,
                    check=False,
                )
                if blob.returncode or hashlib.sha256(blob.stdout).hexdigest() != allowed_digest:
                    failures.append(f"unapproved binary asset in Git history: {path}")
                continue
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                failures.append(f"forbidden file in Git history: {path}")
            if FORBIDDEN_PARTS.intersection(part.lower() for part in path.parts):
                failures.append(f"forbidden path in Git history: {path}")
    return failures


def audit(root: Path, include_history: bool) -> list[str]:
    source_paths, failures = public_source_paths(root)
    manifest = root / "recipes" / "manifest.json"
    for relative in source_paths:
        path = root / relative
        if path.is_symlink():
            failures.append(f"symlink is not allowed: {relative}")
            continue
        if not path.is_file():
            continue
        allowed_digest = ALLOWED_BINARY_ASSETS.get(relative)
        if allowed_digest is not None:
            if hashlib.sha256(path.read_bytes()).hexdigest() != allowed_digest:
                failures.append(f"binary asset does not match its approved digest: {relative}")
            continue
        if relative.parts[0] not in ALLOWED_ROOTS:
            failures.append(f"unexpected public root: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"forbidden file type: {relative}")
        if FORBIDDEN_PARTS.intersection(part.lower() for part in relative.parts):
            failures.append(f"forbidden path: {relative}")
        size_limit = MAX_RECIPE_FILE_BYTES if relative.parts[0] == "recipes" and path.suffix == ".json" else 1_000_000
        if path.stat().st_size > size_limit:
            failures.append(f"file exceeds 1 MB public limit: {relative}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            failures.append(f"non-text payload is not allowed: {relative}")
            continue
        for marker in FORBIDDEN_TEXT:
            if marker.lower() in text.lower():
                failures.append(f"private marker {marker!r} in {relative}")
        if (
            path.suffix in LICENSED_SOURCE_SUFFIXES
            and relative.parts[0] in LICENSED_SOURCE_ROOTS
            and "SPDX-License-Identifier: GPL-3.0-or-later" not in text
        ):
            failures.append(f"missing GPL-3.0-or-later source notice: {relative}")

    license_path = root / "LICENSE"
    if not license_path.is_file():
        failures.append("LICENSE is missing")
    else:
        license_text = license_path.read_text(encoding="utf-8")
        for marker in GPL_MARKERS:
            if marker not in license_text:
                failures.append(f"LICENSE is not the complete GPLv3 text: missing {marker!r}")

    pyproject = root / "pyproject.toml"
    if not pyproject.is_file() or 'license = "GPL-3.0-or-later"' not in pyproject.read_text(encoding="utf-8"):
        failures.append("pyproject.toml must declare GPL-3.0-or-later")

    if not manifest.is_file():
        failures.append("recipes/manifest.json is missing")
    else:
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("schema") != 1 or not isinstance(data.get("releases"), list):
                failures.append("recipe manifest has an invalid schema")
            else:
                releases = data["releases"]
                canonical = data.get("canonical_inputs", {})
                games = [release.get("game") for release in releases if isinstance(release, dict)]
                if len(games) != len(set(games)) or set(games) != set(canonical):
                    failures.append("recipe manifest must contain exactly one release per canonical game")
                for release in releases:
                    if not isinstance(release, dict) or set(release) != {"id", "game", "recipe"}:
                        failures.append("recipe manifest contains an invalid release")
                        continue
                    recipe_path = root / "recipes" / release["recipe"]
                    try:
                        recipe_data = json.loads(recipe_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError) as error:
                        failures.append(f"release recipe cannot be read: {recipe_path.name}: {error}")
                        continue
                    if recipe_data.get("id") != release["id"] or recipe_data.get("game") != release["game"]:
                        failures.append(f"release metadata mismatch: {recipe_path.name}")
                    failures.extend(validate_recipe(recipe_path.relative_to(root), recipe_data))
        except (OSError, json.JSONDecodeError) as error:
            failures.append(f"recipe manifest cannot be read: {error}")
    if include_history:
        failures.extend(tracked_history(root))
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tree", type=Path, default=Path.cwd())
    parser.add_argument("--history", action="store_true")
    arguments = parser.parse_args()
    root = arguments.tree.resolve()
    failures = audit(root, arguments.history)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"Public release audit passed: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
