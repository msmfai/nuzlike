# [Pre-Alpha] Quicklocke Patcher

This public repository contains only the ROM-free Quicklocke patching machinery,
transparent recipe metadata, tests, and release automation. It does not contain
Pokémon game data, ROM images, saves, decompilation sources, symbols, maps, or
generated hacked games.

The patcher source is copyright © 2026 Quicklocke contributors and is free
software under the GNU General Public License, version 3 or (at your option) any
later version (`GPL-3.0-or-later`). The license covers this original patching
machinery; it does not grant rights to Pokémon games or other third-party works.

Quicklocke is a configurable challenge mode for the main-series Generation I–III
games. It uses explicit boss caps, shares part of capped trainer experience,
limits random encounters by named location, memorializes fainted Pokémon until
the Championship, offers paid Gym training, and preserves randomizer-owned data.

## Current status

This is the first owner-test pre-alpha. The graphical app and ROM-free recipes
for all 11 supported games are present, but the ports and packaged applications
are still undergoing emulator and owner playtesting. Expect defects, keep your
original backup untouched, and keep separate copies of any saves used for tests.

## Use

The graphical application is the primary patcher. A single build recognizes all
11 supported games, presents the appropriate cap defaults and wipe rule, and
writes a separate patched copy. Native packages are built for Android, Windows,
Linux, and macOS on both ARM64 and x86-64; see `BUILDING.md` for the exact matrix.
Its level-cap selector provides explicit Easy, Medium, and Hard tables for every
game. Medium is the documented community-default table; Easy and Hard are
Quicklocke-authored balance choices rather than arithmetic offsets. Every boss
level remains directly editable, which changes the selector to Custom.

The Python 3.11 command-line interface remains available for automation. Apply a
published recipe to your own legally obtained backup:

```sh
python3 -m quickloke_patcher apply \
  --input /path/to/your-backup.gbc \
  --recipe recipes/<release>.json \
  --config configs/red.json \
  --output /path/to/quicklocke.gbc
```

Copy the matching file under `configs/`, set `overflow_percent` from 0 through
100, edit any named boss level, and pass it with `--config`. A full-party wipe
always permanently ends the run. Omitting the file uses the identical defaults
embedded in the recipe. The patcher rejects unsupported fields, misspelled bosses,
and out-of-range percentages or levels rather than silently producing a malformed game.

Inspect an input without changing it:

```sh
python3 -m quickloke_patcher inspect --input /path/to/your-backup.gba
```

The patcher never edits its input in place. It checks the input hash and/or every
protected code fingerprint, checks the expected bytes at every write site, writes
only declared fixed-size regions, and atomically creates a separate output.

## Randomizer compatibility

The supported order is:

1. start with your own supported backup;
2. randomize it with the release's named compatibility profile; and
3. apply the Quicklocke recipe to the randomized result.

Unlike a whole-file binary delta, a structured recipe changes only declared
Quicklocke code and save-system regions. All randomizer-owned encounter, species,
trainer, item, and move data outside those regions is left byte-for-byte intact.
Modified inputs are accepted only when the release explicitly permits them and
all invariant fingerprints still match.

## Supported families

The patcher recognizes the canonical English releases of Red, Blue, Yellow,
Gold, Silver, Crystal 1.0, Ruby 1.0, Sapphire 1.0, Emerald, FireRed 1.0, and
LeafGreen 1.0. A ROM-free development recipe is embedded for every listed game;
see `recipes/manifest.json` for the exact release catalog. These recipes remain
pre-release until owner playtesting is complete.

## Repository boundary

This repository has independent public history. Private development sources and
decomp work remain in a separate private repository. Run the public audit before
every commit or release:

```sh
python3 tools/release_audit.py --tree . --history
python3 -m unittest discover -s tests -v
```

Quicklocke is an unofficial fan project and is not affiliated with Nintendo,
Game Freak, Creatures, or The Pokémon Company. No copyrighted game data is
provided; users must supply their own backups.
