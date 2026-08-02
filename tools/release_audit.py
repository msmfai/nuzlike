#!/usr/bin/env python3
# Copyright (C) 2026 Quicklocke contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
    ".github", "quickloke_patcher", "recipes", "tests", "tools",
    ".gitignore", "LICENSE", "README.md", "VERSION", "pyproject.toml",
}
GPL_MARKERS = (
    "GNU GENERAL PUBLIC LICENSE",
    "Version 3, 29 June 2007",
    "Everyone is permitted to copy and distribute verbatim copies",
)
LICENSED_SOURCE_ROOTS = {"quickloke_patcher", "tests", "tools"}


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
            path = Path(parts[1])
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                failures.append(f"forbidden file in Git history: {path}")
            if FORBIDDEN_PARTS.intersection(part.lower() for part in path.parts):
                failures.append(f"forbidden path in Git history: {path}")
    return failures


def audit(root: Path, include_history: bool) -> list[str]:
    failures: list[str] = []
    manifest = root / "recipes" / "manifest.json"
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] == ".git":
            continue
        if "__pycache__" in relative.parts or ".pytest_cache" in relative.parts:
            continue
        if path.is_symlink():
            failures.append(f"symlink is not allowed: {relative}")
            continue
        if not path.is_file():
            continue
        if relative.parts[0] not in ALLOWED_ROOTS:
            failures.append(f"unexpected public root: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(f"forbidden file type: {relative}")
        if FORBIDDEN_PARTS.intersection(part.lower() for part in relative.parts):
            failures.append(f"forbidden path: {relative}")
        if path.stat().st_size > 1_000_000:
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
            path.suffix == ".py"
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
