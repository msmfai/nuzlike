# Copyright (C) 2026 Quicklocke contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Public, ROM-free Quicklocke patcher."""

from .patcher import PatchError, apply_recipe, inspect_input, load_recipe

__all__ = ["PatchError", "apply_recipe", "inspect_input", "load_recipe"]
__version__ = "0.1.0-pre-alpha.9"
