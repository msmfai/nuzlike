# Copyright (C) 2026 Quicklocke contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from quickloke_patcher import PatchError, apply_recipe


class PatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.input = self.root / "owned-backup.gbc"
        self.output = self.root / "quicklocke.gbc"
        self.recipe = self.root / "recipe.json"
        self.data = bytes(range(64))
        self.input.write_bytes(self.data)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_recipe(self, **changes: object) -> None:
        recipe = {
            "schema": 1,
            "id": "test-red-1",
            "game": "red",
            "accepted_sha1": [hashlib.sha1(self.data).hexdigest()],
            "allow_modified_input": True,
            "fingerprints": [{"offset": 0, "expected_hex": "00010203"}],
            "writes": [
                {
                    "offset": 16,
                    "expected_hex": "10111213",
                    "replacement_hex": "a0a1a2a3"
                }
            ]
        }
        recipe.update(changes)
        self.recipe.write_text(json.dumps(recipe), encoding="utf-8")

    def test_canonical_patch_changes_only_declared_region(self) -> None:
        self.write_recipe()
        result = apply_recipe(self.input, self.recipe, self.output)
        expected = bytearray(self.data)
        expected[16:20] = bytes.fromhex("a0a1a2a3")
        self.assertEqual(self.output.read_bytes(), expected)
        self.assertEqual(result["input_kind"], "canonical")
        self.assertEqual(self.input.read_bytes(), self.data)

    def test_modified_input_preserves_randomized_region(self) -> None:
        randomized = bytearray(self.data)
        randomized[40:44] = b"RND!"
        self.input.write_bytes(randomized)
        self.write_recipe()
        result = apply_recipe(self.input, self.recipe, self.output)
        self.assertEqual(self.output.read_bytes()[40:44], b"RND!")
        self.assertEqual(result["input_kind"], "compatible-modified")

    def test_write_site_mismatch_fails_without_output(self) -> None:
        altered = bytearray(self.data)
        altered[16] = 255
        self.input.write_bytes(altered)
        self.write_recipe()
        with self.assertRaises(PatchError):
            apply_recipe(self.input, self.recipe, self.output)
        self.assertFalse(self.output.exists())

    def test_in_place_patch_is_refused(self) -> None:
        self.write_recipe()
        with self.assertRaises(PatchError):
            apply_recipe(self.input, self.recipe, self.input)

    def test_overlapping_writes_are_refused(self) -> None:
        self.write_recipe(writes=[
            {"offset": 16, "expected_hex": "10111213", "replacement_hex": "a0a1a2a3"},
            {"offset": 18, "expected_hex": "12131415", "replacement_hex": "b0b1b2b3"}
        ])
        with self.assertRaises(PatchError):
            apply_recipe(self.input, self.recipe, self.output)


if __name__ == "__main__":
    unittest.main()
