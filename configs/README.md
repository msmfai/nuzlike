# Default configurations

Each schema-1 JSON file is an editable patcher configuration for one supported
game. A full-party wipe permanently invalidates the run; it is not configurable.
`overflow_percent` selects how much EXP from a capped Pokémon is divided among
eligible teammates; it accepts 0 through 100 and defaults to 75.
Level values come from a documented cross-check of published community
hardcore-Nuzlocke cap tables. They are not calculated from trainer-party data.
Passing a file to `apply --config` changes only option bytes explicitly declared
by the selected release recipe.

The graphical patcher offers Easy, Medium, and Hard level-cap modes. Medium is
the sourced community table represented by the top-level game configuration
files. Easy and Hard are transparent Quicklocke balance presets, not claimed
community standards. All three are complete per-game, per-boss tables in
[`presets/level_caps.json`](presets/level_caps.json); the patcher never produces
them with a blanket numerical offset. Editing any individual field changes the
displayed mode to Custom.

Yellow uses the community-listed Lt. Surge cap of 28. Gold, Silver, and Crystal
list Pryce (31) before Jasmine (35) to avoid a decreasing enforced cap. Users
can override any level directly.

Sources and rationale:

- <https://nuzlockeuniversity.ca/2022/01/18/hardcore-nuzlocke-level-caps-by-generation/>
- <https://www.reddit.com/r/nuzlocke/comments/8cejlk/level_limits/>
- <https://nuzlocketracker.org/guides>

See [the full per-game source audit](LEVEL_CAP_SOURCES.md) for every Medium default,
the two source disagreements, Yellow's solo-Raichu case, and Johto ordering.

These files contain configuration data only. They contain no ROM bytes, game
source, extracted assets, keys, or patches.
