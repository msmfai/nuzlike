# Quicklocke Patcher

This public repository contains only the ROM-free Quicklocke patching machinery,
transparent recipe metadata, tests, and release automation. It does not contain
Pokémon game data, ROM images, saves, decompilation sources, symbols, maps, or
generated hacked games.

The patcher source is copyright © 2026 Quicklocke contributors and is free
software under the GNU General Public License, version 3 or (at your option) any
later version (`GPL-3.0-or-later`). The license covers this original patching
machinery; it does not grant rights to Pokémon games or other third-party works.

Quicklocke is a gym-gated challenge mode for the main-series Generation I–III
games. Its design removes wild-battle experience grinding, enforces the next Gym
Leader's level ceiling, offers paid party catch-up training after each gym, adds
soft and hardcore wipe modes, makes EV-building items affordable, and preserves
randomizer-owned data.

## Current status

The patcher and its safety contract are implemented. There is not yet a gameplay
release recipe; recipes will be published here only after the corresponding game
port passes private build, behavior, randomizer-preservation, and release audits.

## Use

Python 3.11 or newer is required. Apply a published recipe to your own legally
obtained backup:

```sh
python3 -m quickloke_patcher apply \
  --input /path/to/your-backup.gbc \
  --recipe recipes/<release>.json \
  --output /path/to/quicklocke.gbc
```

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
LeafGreen 1.0. Recognition does not mean a Quicklocke recipe has shipped yet;
see `recipes/manifest.json` for the release list.

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
