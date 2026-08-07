# Copyright (C) 2026 Quicklocke contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Public, ROM-free Quicklocke patcher."""

from .patcher import PatchError, apply_recipe, inspect_input, load_recipe, repair_cartridge_checksum
from .randomizer import (
    analyze_randomizer_compatibility,
    changed_ranges,
    compose_randomized_rom,
    load_randomizer_manifest,
    recipe_write_ranges,
    semantic_composition_rules,
)

__all__ = [
    "PatchError",
    "analyze_randomizer_compatibility",
    "apply_recipe",
    "changed_ranges",
    "compose_randomized_rom",
    "inspect_input",
    "load_randomizer_manifest",
    "load_recipe",
    "recipe_write_ranges",
    "repair_cartridge_checksum",
    "semantic_composition_rules",
]
__version__ = "0.1.0-pre-alpha.9"
