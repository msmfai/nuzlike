# NuzLike

NuzLike is a roguelite take on the Nuzlocke format for players who enjoy the
team-building decisions but not the grinding. It turns the main story into a
limited-resource run: each area offers one wild encounter, Trainers provide the
finite supply of experience, and the next boss sets the level ceiling.

The game enforces the rules for you. It tracks encounters and caps, retires
fainted Pokémon, and gives you a practical way to bring replacements into the
team. The objective is to keep moving forward and make the best of what the run
gives you.

> [!WARNING]
> NuzLike is alpha software. Keep your original game backup untouched, write the
> patched game to a new file, and use a separate save you are prepared to lose.
> Please report freezes, resets, corrupted graphics, and progression blockers.

NuzLike supports Pokémon Red, Blue, Yellow, Crystal, Emerald, FireRed, and
LeafGreen. It does not contain or download those games; you supply your own
legally obtained backup of one supported release.

## The rules

### One encounter per area

Random encounters remain disabled until you have obtained your first item that
can catch a Pokémon. From then on, each named location provides one random wild
battle. Floors and encounter methods that share the same in-game location share
the same allowance.

When possible, the encounter table is filtered to species that your Pokédex does
not already mark as caught. If every species in that table has been caught, the
normal table is used instead. Gifts, trades, and scripted static encounters do
not consume an area's random encounter.

The first attempted encounter in a spent area opens an empty battle and reports
that no one came. That scene appears only once during the whole run; later rolls
in spent areas are silent. Before the first Badge, wild Pokémon below level 5
are raised to level 5. NuzLike does not otherwise change wild levels.

### Trainer battles replace grinding

Wild battles award no experience during the run. Trainer battles still award
experience, but no Pokémon can grow beyond the configured cap for the next Gym
Leader, Elite Four member, or Champion. Rare Candies obey the same cap. Pokémon
received above it keep their real level but cannot gain another level until the
cap catches up.

If a Pokémon already at the cap would receive Trainer EXP, a configurable share
of that award—75% by default—becomes one pool divided among conscious teammates
with room below the cap. It is divided, not copied, and nobody can be pushed
over the cap. The Trainer Card displays the current **MIN** training level and
**MAX** level cap while the run is active.

### Gym Passes keep replacements useful

Every Poké Mart sells a consumable Gym Pass for ₽1,000. Use one inside a Gym you
have already defeated to train every eligible party member to that Gym's level.
Training happens one level at a time, so normal move-learning and evolution
events still occur; routine levels pass under a fade rather than printing every
step. In games with a clock, the stay advances time by three days.

EV vitamins are also sold in every Poké Mart for one tenth of their normal
price. Gym Passes and cheap vitamins remain available after the run.

### Fainting changes the roster

After a battle, fainted Pokémon are moved to protected PC boxes named
**MEMORIAL**. You may inspect or release them, but you cannot withdraw them,
move them, alter them, or deposit other Pokémon into those boxes during the run.
Refused PC actions explain why they are blocked.

When a Pokémon is retired, the surviving party shares 75% of the experience it
earned above the current MIN, subject to the active cap. A full-party wipe ends
the run and invalidates its save. If you want a gentler personal ruleset, take
an emulator save state after each Gym and use those as manual checkpoints.

### Progress never depends on catching an HM user

Owned HMs offer separate **USE** and **TEACH** actions in the Bag or TM/HM Case.
USE performs the field action without requiring a compatible party member;
TEACH follows the original move-teaching flow. Badge, story, and location checks
still apply. This shortcut remains available after the run.

### Repeatable side systems are paused

Before the first Champion clear, NuzLike disables Day Care deposits, passive Day
Care EXP, breeding, player-initiated rematches, gambling, renewable daily
rewards, and berry planting. Existing Day Care occupants in an imported save can
still be retrieved. Unsolicited calls in which a Trainer challenges you remain
valid.

The coin desk cannot be used for profitable arbitrage. Games with Pokémon prizes
allow one Pokémon prize for the run; other Game Corner prizes stay closed.
Trading remains available for custom multiplayer challenges, but starting a
trade displays a warning that it is cheating in a standard NuzLike run.

### Becoming Champion ends the restrictions

The first Champion victory completes the run. Wild encounters and EXP return to
normal, the cap and profile range disappear, fainted Pokémon stop entering the
Memorial, and its boxes become ordinary PC storage. Native Day Care, breeding,
rematches, Game Corner, daily events, berry planting, and trading behavior also
return.

Gym Passes, cheap vitamins, and direct HM actions remain as postgame
conveniences.

## Install the patcher

Download the package for your platform from the latest GitHub release:

| Platform | Packages |
| --- | --- |
| Windows | x86-64 and ARM64 NSIS installers |
| macOS | Apple Silicon and Intel app bundles in `.tar.gz` archives |
| Linux | x86-64 and ARM64 Debian packages in `.tar.gz` archives |
| Android | ARM64 and x86-64 APKs |

Alpha packages may be unsigned, so your operating system may require you to
approve an app downloaded from an unidentified developer. You can instead build
the patcher from source by following [BUILDING.md](BUILDING.md).

## Required game releases

The patcher identifies a backup by its contents, not its filename. You need one
of these exact English releases:

| Game | Required release | Canonical SHA-1 |
| --- | --- | --- |
| Pokémon Red | USA/Europe, English | `ea9bcae617fdf159b045185467ae58b2e4a48b9a` |
| Pokémon Blue | USA/Europe, English | `d7037c83e1ae5b39bde3c30787637ba1d4c48ce2` |
| Pokémon Yellow | USA/Europe, English | `cc7d03262ebfaf2f06772c1a480c7d9d5f4a38e1` |
| Pokémon Crystal | USA/Europe, English, version 1.0 | `f4cd194bdee0d04ca4eac29e09b8e4e9d818c133` |
| Pokémon Emerald | USA/Europe, English | `f3ae088181bf583e55daf962a92bb46f4f1d07b7` |
| Pokémon FireRed | USA, English, version 1.0—not 1.1 | `41cb23d8dccc8ebd7c649cd8fbb58eeace6e2fdc` |
| Pokémon LeafGreen | USA, English, version 1.0—not 1.1 | `574fa542ffebb14be69902d1d36f1ec0a4afd71e` |

Gold and Silver are not supported; use Crystal for Johto. Ruby and Sapphire are
not supported; use Emerald for Hoenn.

A common 512-byte copier header is accepted only when removing it reveals one of
the supported inputs. The patched output is always headerless. Other revisions,
arbitrary prefixes, and near matches are rejected rather than patched
speculatively.

## Create a game

1. Keep an untouched copy of your original backup.
2. Open NuzLike and choose the backup you want to patch.
3. Choose Easy, Medium, or Hard caps, or edit individual bosses.
4. Optionally change the capped-EXP sharing percentage.
5. Optionally enable FVX randomization and paste a canonical FVX settings string
   with a signed 64-bit seed.
6. Save the result as a new game file and start a fresh save.

The patcher validates the input and every protected patch region before writing
anything. It never edits the selected backup in place. If randomization is
enabled, FVX runs locally first and NuzLike then applies its guarded changes. The
patcher also saves a manifest and FVX log beside the combined output so the build
can be reproduced.

Fixed NuzLike caps are not recalculated from randomized Trainer parties. Every
supported game has a composition adapter, but alpha testing cannot cover every
possible FVX option combination. Keep the settings string, seed, manifest, and
original backup when reporting a randomized-game problem.

See [configs/README.md](configs/README.md) for every configurable value and
[configs/LEVEL_CAP_SOURCES.md](configs/LEVEL_CAP_SOURCES.md) for the Medium cap
sources. Debug cheats are available for port testing and are off by default;
do not enable them for a normal run.

## Troubleshooting and bug reports

If the patcher rejects a game, compare its SHA-1 with the table above. Region,
revision, and prior ROM modifications matter even when the filename looks right.
Do not rename a different revision and expect it to work.

When reporting a gameplay problem, include:

- the game and exact revision;
- the NuzLike version and selected configuration;
- the emulator and version, or the hardware/flash cartridge used;
- whether FVX was enabled, plus its settings string and seed;
- the last reliable action before the problem; and
- a save or save state from before the problem, when you are comfortable sharing
  it.

Never attach a ROM. The project does not need copyrighted game files in public
issues.

## Alpha status

All declared mechanics have deterministic headless-emulator coverage in each
game where they apply, including refusal paths and post-Champion transitions.
The patcher also has recipe, normalization, configuration, randomizer-composition,
and public-boundary tests. Human full-playthrough coverage is still incomplete,
and unusual emulator, hardware, and randomizer combinations may expose problems
that the automated suite does not.

## License

NuzLike's patcher, recipes, tests, and release tooling are licensed under the
[GNU General Public License version 3 or later](LICENSE). This license covers
only the project's original code and grants no rights to Pokémon or any other
third-party work.

This repository contains no ROM images, saves, decompilation source, extracted
assets, or replacement games. NuzLike is an unofficial fan project and is not
affiliated with or endorsed by Nintendo, Game Freak, Creatures, or The Pokémon
Company.
