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
    compose_randomized_rom,
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
            "randomizer_layout": {"schema": 1, "mode": "identity"},
        }
        self.recipe.write_text(json.dumps(recipe), encoding="utf-8")

    def write_manifest(self, randomized: bytes, **changes: object) -> None:
        self.randomized.write_bytes(randomized)
        manifest = {
            "schema": 2,
            "engine": "upr-fvx-quicklocke",
            "engine_version": "FVX 1.6.1",
            "upstream_base_revision": "d9700e2dd668f19e1392b8d5e8f370dd484245b3",
            "seed": "123456789",
            "settings": "427canonical-settings",
            "semantic_settings": {
                "starters_mode": "UNCHANGED",
                "evolutions_mode": "UNCHANGED",
                "movesets_mode": "UNCHANGED",
                "trainers_mode": "UNCHANGED",
                "trainer_levels_modified": False,
                "trainer_level_modifier": 0,
                "additional_boss_pokemon": 0,
                "additional_important_pokemon": 0,
                "additional_regular_pokemon": 0,
                "wild_randomized": False,
                "wild_zone_mode": "GAME",
                "wild_type_mode": "NONE",
                "wild_evolution_mode": "NONE",
                "wild_levels_modified": False,
                "wild_level_modifier": 0,
                "static_pokemon_mode": "UNCHANGED",
                "static_levels_modified": False,
                "static_level_modifier": 0,
                "tm_moves_mode": "UNCHANGED",
                "tm_hm_compatibility_mode": "UNCHANGED",
                "full_hm_compatibility": False,
                "keep_field_move_tms": False,
                "field_items_mode": "UNCHANGED",
                "shop_items_mode": "UNCHANGED",
                "balance_shop_prices": False,
                "cheap_rare_candies": False,
                "misc_tweaks": 0,
            },
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
        self.assertEqual(
            [rule["system"] for rule in report["semantic_rules"][:5]],
            ["level_caps", "encounters", "hm_progression", "shops", "memorial_and_champion"],
        )

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
            "resolution": "quicklocke-final",
            "message": (
                "FVX and Quicklocke both change ROM bytes 0x2be-0x2bf; "
                "this option combination needs an explicit composition rule"
            ),
        }])

    def test_composition_preserves_fvx_only_bytes_and_quicklocke_wins_overlap(self) -> None:
        self.write_recipe(offset=700)
        after = bytearray(self.clean_bytes)
        after[600:604] = b"FVX!"
        after[702:706] = b"CLSH"
        self.write_manifest(bytes(after))
        output = self.root / "combined.gbc"
        combined_manifest = self.root / "combined.json"
        report = compose_randomized_rom(
            clean_rom=self.clean,
            randomized_rom=self.randomized,
            manifest_path=self.manifest,
            recipe_path=self.recipe,
            output_rom=output,
            output_manifest=combined_manifest,
        )
        composed = output.read_bytes()
        self.assertEqual(composed[600:604], b"FVX!")
        self.assertEqual(composed[700:704], b"\xa0\xa1\xa2\xa3")
        self.assertEqual(composed[704:706], b"SH")
        self.assertEqual(report["collisions"][0]["resolution"], "quicklocke-final")
        self.assertEqual(report["final_sha256"], hashlib.sha256(composed).hexdigest())
        self.assertEqual(
            json.loads(combined_manifest.read_text(encoding="utf-8")), report
        )

    def test_composition_is_byte_and_manifest_deterministic(self) -> None:
        self.write_recipe(offset=700)
        after = bytearray(self.clean_bytes)
        after[600] ^= 0xFF
        self.write_manifest(bytes(after))
        results: list[tuple[bytes, bytes]] = []
        for suffix in ("a", "b"):
            output = self.root / f"combined-{suffix}.gbc"
            combined_manifest = self.root / f"combined-{suffix}.json"
            compose_randomized_rom(
                clean_rom=self.clean,
                randomized_rom=self.randomized,
                manifest_path=self.manifest,
                recipe_path=self.recipe,
                output_rom=output,
                output_manifest=combined_manifest,
            )
            results.append((output.read_bytes(), combined_manifest.read_bytes()))
        self.assertEqual(results[0], results[1])

    def test_composition_refuses_an_unadapted_relocated_layout(self) -> None:
        self.write_recipe(offset=700)
        recipe = json.loads(self.recipe.read_text(encoding="utf-8"))
        recipe.pop("randomizer_layout")
        self.recipe.write_text(json.dumps(recipe), encoding="utf-8")
        self.write_manifest(self.clean_bytes)
        with self.assertRaisesRegex(PatchError, "no verified FVX layout adapter"):
            compose_randomized_rom(
                clean_rom=self.clean,
                randomized_rom=self.randomized,
                manifest_path=self.manifest,
                recipe_path=self.recipe,
                output_rom=self.root / "unsafe.gbc",
                output_manifest=self.root / "unsafe.json",
            )
        self.assertFalse((self.root / "unsafe.gbc").exists())

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

    def test_active_semantic_settings_receive_explicit_composition_rules(self) -> None:
        self.write_recipe(offset=700)
        after = bytearray(self.clean_bytes)
        after[600] ^= 0xFF
        semantics = {
            "trainer_levels_modified": True,
            "trainer_level_modifier": 15,
            "wild_levels_modified": True,
            "wild_level_modifier": -10,
            "field_items_mode": "RANDOM",
        }
        default_manifest = {
            "starters_mode": "UNCHANGED", "evolutions_mode": "UNCHANGED",
            "movesets_mode": "UNCHANGED", "trainers_mode": "RANDOM",
            "trainer_levels_modified": False, "trainer_level_modifier": 0,
            "additional_boss_pokemon": 0, "additional_important_pokemon": 0,
            "additional_regular_pokemon": 0, "wild_randomized": True,
            "wild_zone_mode": "MAP", "wild_type_mode": "NONE",
            "wild_evolution_mode": "NONE", "wild_levels_modified": False,
            "wild_level_modifier": 0, "static_pokemon_mode": "UNCHANGED",
            "static_levels_modified": False, "static_level_modifier": 0,
            "tm_moves_mode": "RANDOM", "tm_hm_compatibility_mode": "FULL",
            "full_hm_compatibility": True, "keep_field_move_tms": True,
            "field_items_mode": "UNCHANGED", "shop_items_mode": "RANDOM",
            "balance_shop_prices": True, "cheap_rare_candies": False,
            "misc_tweaks": 0,
        }
        default_manifest.update(semantics)
        self.write_manifest(bytes(after), semantic_settings=default_manifest)
        report = analyze_randomizer_compatibility(
            clean_rom=self.clean, randomized_rom=self.randomized,
            manifest_path=self.manifest, recipe_path=self.recipe,
        )
        systems = {rule["system"] for rule in report["semantic_rules"]}
        self.assertTrue({"randomized_trainer_levels", "randomized_wild_levels", "capture_item_gate"} <= systems)

    def test_semantic_manifest_rejects_disabled_nonzero_modifier(self) -> None:
        self.write_recipe()
        semantics = {
            "starters_mode": "UNCHANGED", "evolutions_mode": "UNCHANGED",
            "movesets_mode": "UNCHANGED", "trainers_mode": "UNCHANGED",
            "trainer_levels_modified": False, "trainer_level_modifier": 25,
            "additional_boss_pokemon": 0, "additional_important_pokemon": 0,
            "additional_regular_pokemon": 0, "wild_randomized": False,
            "wild_zone_mode": "GAME", "wild_type_mode": "NONE",
            "wild_evolution_mode": "NONE", "wild_levels_modified": False,
            "wild_level_modifier": 0, "static_pokemon_mode": "UNCHANGED",
            "static_levels_modified": False, "static_level_modifier": 0,
            "tm_moves_mode": "UNCHANGED", "tm_hm_compatibility_mode": "UNCHANGED",
            "full_hm_compatibility": False, "keep_field_move_tms": False,
            "field_items_mode": "UNCHANGED", "shop_items_mode": "UNCHANGED",
            "balance_shop_prices": False, "cheap_rare_candies": False,
            "misc_tweaks": 0,
        }
        self.write_manifest(self.clean_bytes, semantic_settings=semantics)
        with self.assertRaisesRegex(PatchError, "trainer_level_modifier must be zero"):
            analyze_randomizer_compatibility(
                clean_rom=self.clean, randomized_rom=self.randomized,
                manifest_path=self.manifest, recipe_path=self.recipe,
            )


if __name__ == "__main__":
    unittest.main()
