# Copyright (C) 2026 NuzLike contributors
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import hashlib
import json
import base64
import tempfile
import unittest
from pathlib import Path

from nuzlike_patcher import PatchError, apply_recipe


class PatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.input = self.root / "owned-backup.gbc"
        self.output = self.root / "nuzlike.gbc"
        self.recipe = self.root / "recipe.json"
        self.config = self.root / "config.json"
        data = bytearray(range(64))
        data[22] = 0
        data[23] = 75
        self.data = bytes(data)
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
            ],
            "configurable": {
                "level_caps": [
                    {"id": "brock", "offset": 20, "default": 20},
                    {"id": "misty", "offset": 21, "default": 21}
                ],
                "overflow_percent": {
                    "offset": 23, "default": 75, "minimum": 0, "maximum": 100
                },
                "debug_flags": {
                    "offset": 22,
                    "default": 0,
                    "flags": {
                        "infinite_health": 1,
                        "maximum_damage": 2,
                        "disable_trainer_sight": 4
                    }
                }
            },
            "debug_variant": {
                "writes": [
                    {
                        "offset": 16,
                        "expected_hex": "10111213",
                        "replacement_hex": "b0b1b2b3"
                    }
                ],
                "configurable": {
                    "level_caps": [
                        {"id": "brock", "offset": 20, "default": 20},
                        {"id": "misty", "offset": 21, "default": 21}
                    ],
                    "overflow_percent": {
                        "offset": 23, "default": 75, "minimum": 0, "maximum": 100
                    },
                    "debug_flags": {
                        "offset": 22,
                        "default": 0,
                        "flags": {
                            "infinite_health": 1,
                            "maximum_damage": 2,
                            "disable_trainer_sight": 4
                        }
                    }
                },
                "canonical_output_sha256": "0" * 64
            }
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
        self.assertEqual(result["input_normalization"], "none")
        self.assertEqual(self.input.read_bytes(), self.data)

    def test_common_copier_header_is_removed_only_after_validation(self) -> None:
        copier_header = bytes([0xA5]) * 512
        supplied = copier_header + self.data
        self.input.write_bytes(supplied)
        self.write_recipe()
        result = apply_recipe(self.input, self.recipe, self.output)
        expected = bytearray(self.data)
        expected[16:20] = bytes.fromhex("a0a1a2a3")
        self.assertEqual(self.output.read_bytes(), expected)
        self.assertEqual(result["input_kind"], "canonical")
        self.assertEqual(
            result["input_normalization"], "removed-512-byte-copier-header"
        )
        self.assertEqual(self.input.read_bytes(), supplied)

    def test_arbitrary_prefix_is_not_removed_when_body_is_unsupported(self) -> None:
        self.input.write_bytes(bytes(512) + bytes(reversed(self.data)))
        self.write_recipe()
        with self.assertRaises(PatchError):
            apply_recipe(self.input, self.recipe, self.output)
        self.assertFalse(self.output.exists())

    def test_modified_input_preserves_randomized_region(self) -> None:
        randomized = bytearray(self.data)
        randomized[40:44] = b"RND!"
        self.input.write_bytes(randomized)
        self.write_recipe()
        result = apply_recipe(self.input, self.recipe, self.output)
        self.assertEqual(self.output.read_bytes()[40:44], b"RND!")
        self.assertEqual(result["input_kind"], "compatible-modified")

    def test_source_copy_recipe_relocates_and_xors_without_embedding_target(self) -> None:
        delta = bytes(value ^ replacement for value, replacement in zip(self.data[16:20], b"QLCK"))
        self.write_recipe(
            writes=[],
            source_copy={
                "encoding": "source-copy-v1",
                "output_size": len(self.data),
                "literal_bytes": 4,
                "operations": [
                    {"source_offset": 0, "length": 16},
                    {"xor_b64": base64.b64encode(delta).decode("ascii")},
                    {"source_offset": 20, "length": 44},
                ],
            },
        )
        result = apply_recipe(self.input, self.recipe, self.output)
        expected = bytearray(self.data)
        expected[16:20] = b"QLCK"
        self.assertEqual(self.output.read_bytes(), expected)
        self.assertEqual(result["writes"], 3)

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

    def test_config_overrides_declared_cap_bytes_after_fixed_writes(self) -> None:
        self.write_recipe()
        self.config.write_text(json.dumps({
            "schema": 1,
            "game": "red",
            "level_caps": {"brock": 13, "misty": 20}
        }), encoding="utf-8")
        result = apply_recipe(
            self.input, self.recipe, self.output, config_path=self.config
        )
        self.assertEqual(self.output.read_bytes()[20:22], bytes((13, 20)))
        self.assertEqual(result["level_cap_overrides"], {"brock": 13, "misty": 20})

    def test_config_overrides_overflow_percent(self) -> None:
        self.write_recipe()
        self.config.write_text(json.dumps({
            "schema": 1, "game": "red", "level_caps": {}, "overflow_percent": 50
        }), encoding="utf-8")
        result = apply_recipe(self.input, self.recipe, self.output, config_path=self.config)
        self.assertEqual(self.output.read_bytes()[23], 50)
        self.assertEqual(result["overflow_percent"], 50)

    def test_debug_cheats_are_independent_and_default_off(self) -> None:
        self.write_recipe()
        normal = apply_recipe(self.input, self.recipe, self.output)
        self.assertEqual(self.output.read_bytes()[22], 0)
        self.assertEqual(normal["debug"], {
            "infinite_health": False,
            "maximum_damage": False,
            "disable_trainer_sight": False,
        })
        self.assertEqual(self.output.read_bytes()[16:20], bytes.fromhex("a0a1a2a3"))
        for name, mask in (
            ("infinite_health", 1),
            ("maximum_damage", 2),
            ("disable_trainer_sight", 4),
        ):
            with self.subTest(name=name):
                self.config.write_text(json.dumps({
                    "schema": 1,
                    "game": "red",
                    "debug": {name: True},
                }), encoding="utf-8")
                result = apply_recipe(self.input, self.recipe, self.output, config_path=self.config)
                self.assertEqual(self.output.read_bytes()[22], mask)
                self.assertEqual(self.output.read_bytes()[16:20], bytes.fromhex("b0b1b2b3"))
                self.assertTrue(result["debug"][name])

    def test_debug_toggle_requires_instrumented_patch_variant(self) -> None:
        self.write_recipe()
        recipe = json.loads(self.recipe.read_text(encoding="utf-8"))
        recipe.pop("debug_variant")
        self.recipe.write_text(json.dumps(recipe), encoding="utf-8")
        self.config.write_text(json.dumps({
            "schema": 1,
            "game": "red",
            "debug": {"infinite_health": True},
        }), encoding="utf-8")
        with self.assertRaisesRegex(PatchError, "no opt-in debug patch variant"):
            apply_recipe(self.input, self.recipe, self.output, config_path=self.config)

    def test_config_rejects_unknown_cap(self) -> None:
        self.write_recipe()
        self.config.write_text(json.dumps({
            "schema": 1,
            "game": "red",
            "level_caps": {"missingno": 42}
        }), encoding="utf-8")
        with self.assertRaises(PatchError):
            apply_recipe(
                self.input, self.recipe, self.output, config_path=self.config
            )

    def test_config_rejects_wrong_game_and_invalid_levels(self) -> None:
        self.write_recipe()
        for config in (
            {"schema": 1, "game": "blue", "level_caps": {}},
            {"schema": 1, "game": "red", "level_caps": {"brock": 0}},
            {"schema": 1, "game": "red", "level_caps": {"brock": True}},
            {"schema": 1, "game": "red", "wipe_mode": "soft", "level_caps": {}},
            {"schema": 1, "game": "red", "overflow_percent": 101, "level_caps": {}},
            {"schema": 1, "game": "red", "overflow_percent": True, "level_caps": {}},
            {"schema": 1, "game": "red", "debug": {"infinite_health": 1}},
            {"schema": 1, "game": "red", "debug": {"walk_through_walls": True}},
        ):
            with self.subTest(config=config):
                self.config.write_text(json.dumps(config), encoding="utf-8")
                with self.assertRaises(PatchError):
                    apply_recipe(
                        self.input, self.recipe, self.output, config_path=self.config
                    )


class CheckedInConfigTests(unittest.TestCase):
    def test_all_canonical_games_have_valid_editable_defaults(self) -> None:
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (root / "recipes/manifest.json").read_text(encoding="utf-8")
        )
        expected_games = set(manifest["canonical_inputs"])
        config_paths = sorted((root / "configs").glob("*.json"))
        self.assertEqual({path.stem for path in config_paths}, expected_games)
        for path in config_paths:
            with self.subTest(path=path.name):
                config = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(config["schema"], 1)
                self.assertEqual(config["game"], path.stem)
                self.assertNotIn("wipe_mode", config)
                self.assertEqual(config["overflow_percent"], 75)
                self.assertEqual(config["debug"], {
                    "infinite_health": False,
                    "maximum_damage": False,
                    "disable_trainer_sight": False,
                })
                self.assertTrue(config["level_caps"])
                self.assertTrue(
                    all(
                        isinstance(level, int)
                        and not isinstance(level, bool)
                        and 1 <= level <= 100
                        for level in config["level_caps"].values()
                    )
                )


if __name__ == "__main__":
    unittest.main()
