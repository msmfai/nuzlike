# Copyright (C) 2026 NuzLike contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Focused ROM-free tests for Emerald's chapter-based experience curves."""

from __future__ import annotations

from fractions import Fraction
import unittest

from nuzlike_patcher.emerald_analysis import (
    EmeraldAnalysisError,
    QUOTAS,
    chapter_trainer_budgets,
    classify_trainers,
    decode_species,
    decode_trainers,
    generate_piecewise_tables,
    solve_reachability,
)
from tests.test_emerald_analysis import synthetic_rom_and_template


CAPS = (15, 19, 24, 29, 31, 33, 42, 46, 58)
BUDGETS = (10_000, 16_000, 36_000, 43_000, 11_000, 101_000, 132_000, 159_000, 116_000)


def vanilla_tables() -> list[list[int]]:
    return [
        [(growth + 1) * level**3 for level in range(101)]
        for growth in range(8)
    ]


class EmeraldChapterCurveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.vanilla = vanilla_tables()
        self.groups = tuple((0, 1, 2, 3, 4, 5) for _ in range(9))

    def test_quota_schedule_controls_mean_team_concentration(self) -> None:
        _, diagnostics = generate_piecewise_tables(
            self.vanilla, CAPS, BUDGETS, self.groups
        )
        self.assertEqual([row["quota"] for row in diagnostics], list(QUOTAS))
        for row in diagnostics:
            target = Fraction(
                row["target_mean_cost"]["numerator"],
                row["target_mean_cost"]["denominator"],
            )
            represented = Fraction(
                row["represented_mean_cost"]["numerator"],
                row["represented_mean_cost"]["denominator"],
            )
            # Half-up rounding occurs once per level. Its aggregate error is
            # consequently bounded by half the number of levels in the band.
            self.assertLessEqual(abs(represented - target), (row["cap"] - row["floor"]) / 2)

    def test_one_exact_scale_is_applied_to_every_growth_group_in_a_band(self) -> None:
        tables, diagnostics = generate_piecewise_tables(
            self.vanilla, CAPS, BUDGETS, self.groups
        )
        for row in diagnostics:
            scale = Fraction(row["scale"]["numerator"], row["scale"]["denominator"])
            for growth in range(8):
                for level in range(row["floor"] + 1, row["cap"] + 1):
                    vanilla_delta = self.vanilla[growth][level] - self.vanilla[growth][level - 1]
                    scaled = Fraction(vanilla_delta) * scale
                    expected = max(
                        1,
                        (scaled.numerator * 2 + scaled.denominator)
                        // (scaled.denominator * 2),
                    )
                    self.assertEqual(tables[growth][level] - tables[growth][level - 1], expected)

    def test_every_post_champion_delta_is_vanilla(self) -> None:
        tables, _ = generate_piecewise_tables(
            self.vanilla, CAPS, BUDGETS, self.groups
        )
        for growth in range(8):
            for level in range(CAPS[-1] + 1, 101):
                self.assertEqual(
                    tables[growth][level] - tables[growth][level - 1],
                    self.vanilla[growth][level] - self.vanilla[growth][level - 1],
                )

    def test_zero_xp_band_is_reported_instead_of_silently_normalized(self) -> None:
        budgets = list(BUDGETS)
        budgets[4] = 0
        _, diagnostics = generate_piecewise_tables(
            self.vanilla, CAPS, budgets, self.groups
        )
        self.assertEqual(diagnostics[4]["warning"], "positive level band has no trainer XP")

    def test_invalid_caps_and_family_inputs_fail_closed(self) -> None:
        cases = (
            ((15, 14, *CAPS[2:]), self.groups, "chapter 2 cap"),
            ((*CAPS[:-1], 100), self.groups, "chapter 9 cap"),
            (CAPS, (*self.groups[:-1], (8,)), "chapter 9 has invalid family"),
            (CAPS, (*self.groups[:-1], ()), "chapter 9 has invalid family"),
        )
        for caps, groups, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(EmeraldAnalysisError, message):
                generate_piecewise_tables(self.vanilla, caps, BUDGETS, groups)


class EmeraldChapterClassificationTests(unittest.TestCase):
    def test_repeatables_and_boss_reward_are_excluded_and_choices_count_once(self) -> None:
        rom, template, _ = synthetic_rom_and_template()
        template["trainer_instances"] = [
            {"id": "ordinary", "trainer_id": 1, "zone": "start", "requires": [], "source": "test"},
            {"id": "repeatable", "trainer_id": 1, "zone": "start", "requires": [], "repeatable": True, "source": "test"},
            {"id": "boss", "trainer_id": 1, "zone": "start", "requires": [], "milestone": "leader_1", "source": "test"},
            {"id": "choice-low", "trainer_id": 0, "zone": "start", "requires": [], "choice_group": "fork", "source": "test"},
            {"id": "choice-high", "trainer_id": 1, "zone": "start", "requires": [], "choice_group": "fork", "source": "test"},
        ]
        reachability = solve_reachability(template)
        trainers = decode_trainers(rom, template)
        species = decode_species(rom, template)
        classified = classify_trainers(template, reachability, trainers, species)
        budgets, rows = chapter_trainer_budgets(classified, template)
        trainer_xp = next(row["xp"] for row in classified if row["id"] == "ordinary")
        self.assertNotIn("repeatable", {row["id"] for row in classified})
        self.assertEqual({row["id"] for row in rows[0]}, {"ordinary", "choice-high"})
        self.assertEqual(budgets[0], trainer_xp * 2)


if __name__ == "__main__":
    unittest.main()
