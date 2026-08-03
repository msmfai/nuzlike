# Default configurations

Each schema-1 JSON file is an editable patcher configuration for one supported
game. `wipe_mode` selects `forgiving` (restore the post-victory checkpoint from
the previous Gym after a wipe) or `hardcore` (permanently invalidate the run).
Level values are community hardcore-Nuzlocke boss caps with documented
Quicklocke challenge-flow adjustments. Passing a file to `apply --config`
changes only option bytes explicitly declared by the selected release recipe.

Yellow defaults Lt. Surge to 26 rather than his solo Raichu's level 28. Gold,
Silver, and Crystal list Pryce (31) before Jasmine (35) to avoid a decreasing
enforced cap. Users can change either decision directly.

Sources and rationale:

- <https://nuzlockeuniversity.ca/2022/01/18/hardcore-nuzlocke-level-caps-by-generation/>
- <https://www.smogon.com/articles/introduction-nuzlockes>

These files contain configuration data only. They contain no ROM bytes, game
source, extracted assets, keys, or patches.
