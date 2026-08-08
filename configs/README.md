# Customizing a Quicklocke run

You do not need to edit a configuration file when using the graphical patcher.
It exposes the same options as ordinary controls and starts with Quicklocke's
recommended defaults. These JSON files are for players who want a reusable
configuration or use the command-line patcher.

There is one file for every supported game:

- `red.json`, `blue.json`, and `yellow.json`
- `crystal.json`
- `emerald.json`
- `firered.json` and `leafgreen.json`

Copy the matching file before changing it. The `game` value must match both the
selected game and recipe.

## What can I change?

### Boss level caps

Every Gym Leader, Elite Four member, and Champion has an explicit value under
`level_caps`. This is the maximum level your Pokémon may reach before that
victory. The same value becomes the training target when a Gym Pass is used in
that defeated Gym.

The top-level files contain the **Medium** preset: published community hardcore-
Nuzlocke defaults cross-checked across multiple tables. The graphical patcher
also provides:

- **Easy**, a hand-balanced table with more room;
- **Hard**, a hand-balanced table with tighter caps; and
- **Custom**, selected automatically after any individual cap is edited.

Easy and Hard are complete per-game tables, not a fixed number added to or
subtracted from every boss. Their values are stored in
[`presets/level_caps.json`](presets/level_caps.json). The research and judgment
behind Medium—including Yellow's level-28 Lt. Surge and Johto's Pryce/Jasmine
ordering—are recorded in [LEVEL_CAP_SOURCES.md](LEVEL_CAP_SOURCES.md).

Levels must be whole numbers from 1 through 100. The patcher rejects unknown or
misspelled boss names.

### Capped-EXP sharing

`overflow_percent` controls how much trainer EXP blocked by the current level
cap becomes one shared pool for eligible teammates below the cap.

- `75` is the Quicklocke default.
- `100` shares the entire blocked award.
- `0` discards it all.

The pool is divided rather than duplicated. Fainted Pokémon, Eggs, the capped
Pokémon itself, and teammates already at the cap are not eligible. No recipient
can be pushed above the cap. The value must be a whole percentage from 0 to 100.

### Debug switches

The three values under `debug` produce a dedicated testing build:

- `infinite_health` prevents battle damage to the player's Pokémon;
- `maximum_damage` makes the player's damaging attacks remove the opponent's
  current HP; and
- `disable_trainer_sight` stops trainers initiating sight-line battles, while
  still permitting a battle when spoken to.

All three default to `false`. They are intended for testing broken or unfinished
ports and are not Quicklocke difficulty settings.

## Example

This Yellow configuration keeps the default 75% EXP share but replaces Lt.
Surge's community cap with a stricter personal cap and enables one debug aid:

```json
{
  "schema": 1,
  "game": "yellow",
  "overflow_percent": 75,
  "debug": {
    "infinite_health": false,
    "maximum_damage": false,
    "disable_trainer_sight": true
  },
  "level_caps": {
    "brock": 12,
    "misty": 21,
    "surge": 26,
    "erika": 32,
    "koga": 50,
    "sabrina": 50,
    "blaine": 54,
    "giovanni": 55,
    "lorelei": 56,
    "bruno": 58,
    "agatha": 60,
    "lance": 62,
    "champion": 65
  }
}
```

Apply it with the matching recipe:

```sh
python3 -m quickloke_patcher apply \
  --input /path/to/your-yellow-backup.gbc \
  --recipe recipes/yellow.json \
  --config /path/to/my-yellow-run.json \
  --output /path/to/quicklocke-yellow.gbc
```

The input is never edited in place.

## Rules that are not configurable yet

Configuration changes only level caps, the EXP-sharing percentage, and the
three debug switches. The rest of the Quicklocke rules—including one encounter
per area, no wild EXP, Gym Pass behavior, Memorial retirement, and the
Championship unlock—remain fixed.

A full-party wipe always ends the run.

These configuration files contain settings only. They contain no ROM data,
game source, extracted assets, keys, saves, or replacement games.
