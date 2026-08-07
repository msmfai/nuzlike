# Copyright (C) 2026 Quicklocke contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from quickloke_patcher import (
    PatchError,
    analyze_randomizer_compatibility,
    changed_ranges,
    load_recipe,
    recipe_write_ranges,
)


class RandomizerIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.clean = self.root / "clean.gbc"
        self.randomized = self.root / "randomized.gbc"
        self.manifest = self.root / "randomized.json"
        self.recipe = self.root / "recipe.json"
        self.clean_bytes = bytes(range(256)) * 4
        self.clean.write_bytes(self.clean_bytes)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_recipe(self, *, offset: int = 700) -> None:
        recipe = {
            "schema": 1,
            "id": "test-crystal-1",
            "game": "crystal",
            "accepted_sha1": [hashlib.sha1(self.clean_bytes).hexdigest()],
            "allow_modified_input": True,
            "fingerprints": [{"offset": 0, "expected_hex": "00010203"}],
            "writes": [{
                "offset": offset,
                "expected_hex": self.clean_bytes[offset:offset + 4].hex(),
                "replacement_hex": "a0a1a2a3",
            }],
            "configurable": {},
        }
        self.recipe.write_text(json.dumps(recipe), encoding="utf-8")

    def write_manifest(self, randomized: bytes, **changes: object) -> None:
        self.randomized.write_bytes(randomized)
        manifest = {
            "schema": 1,
            "engine": "upr-fvx-quicklocke",
            "engine_version": "FVX 1.6.1",
            "upstream_base_revision": "d9700e2dd668f19e1392b8d5e8f370dd484245b3",
            "seed": "123456789",
            "settings": "427canonical-settings",
            "rom_name": "Crystal (U)",
            "rom_code": "C",
            "generation": 2,
            "default_extension": "gbc",
            "input_size": len(self.clean_bytes),
            "input_sha256": hashlib.sha256(self.clean_bytes).hexdigest(),
            "randomized_size": len(randomized),
            "randomized_sha256": hashlib.sha256(randomized).hexdigest(),
            "randomizer_log_sha256": hashlib.sha256(b"log").hexdigest(),
            "fvx_check_value": 42,
            "next_stage": "quicklocke",
            "warnings": [],
        }
        manifest.update(changes)
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")

    def test_changed_ranges_are_compact_and_half_open(self) -> None:
        after = bytearray(self.clean_bytes)
        after[3:6] = b"abc"
        after[9] ^= 0xFF
        self.assertEqual(changed_ranges(self.clean_bytes, bytes(after)), [(3, 6), (9, 10)])

    def test_non_overlapping_randomization_is_compatible(self) -> None:
        self.write_recipe(offset=700)
        after = bytearray(self.clean_bytes)
        after[600:604] = b"FVX!"
        self.write_manifest(bytes(after))
        report = analyze_randomizer_compatibility(
            clean_rom=self.clean,
            randomized_rom=self.randomized,
            manifest_path=self.manifest,
            recipe_path=self.recipe,
        )
        self.assertTrue(report["compatible"])
        self.assertEqual(report["randomizer_changed_bytes"], 4)
        self.assertEqual(report["collisions"], [])

    def test_overlapping_randomization_is_reported_with_exact_bytes(self) -> None:
        self.write_recipe(offset=700)
        after = bytearray(self.clean_bytes)
        after[702:706] = b"FVX!"
        self.write_manifest(bytes(after))
        report = analyze_randomizer_compatibility(
            clean_rom=self.clean,
            randomized_rom=self.randomized,
            manifest_path=self.manifest,
            recipe_path=self.recipe,
        )
        self.assertFalse(report["compatible"])
        self.assertEqual(report["collisions"], [{
            "start": 702,
            "end": 704,
            "message": (
                "FVX and Quicklocke both change ROM bytes 0x2be-0x2bf; "
                "this option combination needs an explicit composition rule"
            ),
        }])

    def test_manifest_is_cryptographically_bound_to_both_roms(self) -> None:
        self.write_recipe()
        after = bytearray(self.clean_bytes)
        after[600] ^= 0xFF
        self.write_manifest(bytes(after), randomized_sha256="0" * 64)
        with self.assertRaisesRegex(PatchError, "does not match the randomized ROM"):
            analyze_randomizer_compatibility(
                clean_rom=self.clean,
                randomized_rom=self.randomized,
                manifest_path=self.manifest,
                recipe_path=self.recipe,
            )

    def test_source_copy_xor_operations_resolve_to_output_ranges(self) -> None:
        self.write_recipe()
        recipe = json.loads(self.recipe.read_text(encoding="utf-8"))
        recipe["writes"] = []
        recipe["source_copy"] = {
            "encoding": "source-copy-v1",
            "output_size": len(self.clean_bytes),
            "literal_bytes": 4,
            "operations": [
                {"source_offset": 0, "length": 8},
                {"xor_b64": base64.b64encode(b"ABCD").decode("ascii")},
                {"source_offset": 12, "length": len(self.clean_bytes) - 12},
            ],
        }
        self.recipe.write_text(json.dumps(recipe), encoding="utf-8")
        ranges = recipe_write_ranges(load_recipe(self.recipe))
        self.assertIn((8, 12), ranges)
        self.assertIn((0x14E, 0x150), ranges)


if __name__ == "__main__":
    unittest.main()
