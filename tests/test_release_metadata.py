# Copyright (C) 2026 NuzLike contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALPHA_VERSION = "0.1.0-alpha.1"


class ReleaseMetadataTests(unittest.TestCase):
    def test_alpha_version_is_consistent_across_every_package(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        package_lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
        cargo = tomllib.loads((ROOT / "src-tauri/Cargo.toml").read_text(encoding="utf-8"))
        tauri = json.loads((ROOT / "src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
        python = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        init = (ROOT / "nuzlike_patcher/__init__.py").read_text(encoding="utf-8")

        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), ALPHA_VERSION)
        self.assertEqual(package["version"], ALPHA_VERSION)
        self.assertEqual(package_lock["version"], ALPHA_VERSION)
        self.assertEqual(package_lock["packages"][""]["version"], ALPHA_VERSION)
        self.assertEqual(cargo["package"]["version"], ALPHA_VERSION)
        self.assertEqual(tauri["version"], ALPHA_VERSION)
        self.assertEqual(python["project"]["version"], "0.1.0a1")
        self.assertIn(f'__version__ = "{ALPHA_VERSION}"', init)

    def test_release_workflow_builds_the_declared_matrix_and_checksums_it(self) -> None:
        workflow = (ROOT / ".github/workflows/build-apps.yml").read_text(encoding="utf-8")
        for target in (
            "aarch64-apple-darwin",
            "x86_64-apple-darwin",
            "aarch64-pc-windows-msvc",
            "x86_64-pc-windows-msvc",
            "aarch64-unknown-linux-gnu",
            "x86_64-unknown-linux-gnu",
            "nuzlike-android-arm64",
            "nuzlike-android-x86_64",
        ):
            self.assertIn(target, workflow)
        self.assertIn("sha256sum nuzlike-* > SHA256SUMS", workflow)
        self.assertIn("--notes-file RELEASE_NOTES.md", workflow)
        self.assertIn("[Alpha] NuzLike", workflow)
        self.assertIn("needs: [source-checks, desktop, android]", workflow)
        self.assertIn("python tools/release_audit.py --tree . --history", workflow)

    def test_local_document_links_resolve(self) -> None:
        failures: list[str] = []
        pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
        for relative in ("README.md", "BUILDING.md", "TESTING.md", "RELEASE_NOTES.md"):
            path = ROOT / relative
            for target in pattern.findall(path.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                destination = target.split("#", 1)[0]
                if destination and not (path.parent / destination).exists():
                    failures.append(f"{relative}: {target}")
        self.assertEqual(failures, [])

if __name__ == "__main__":
    unittest.main()
