> [!WARNING]
> Hey there! I'm taking a top down approach to development here where I started with something vibe coded and then clean things up. In pre alpha the documentation is purely AI generated so I can focus on the programming, it will be hand written at final release. The AI-generated documentation is overly verbose by design at this point so all the features of the mod are visible to you.

# [Pre-Alpha] NuzLike

NuzLike is a roguelite twist on the Nuzlocke format for players who enjoy its
team-building decisions but do not enjoy grinding.

A traditional Nuzlocke can leave you training replacements for a long time
after a bad encounter or an important loss. NuzLike removes that part of the
loop. Wild battles give no experience, boss level caps are enforced by the
game, and defeating a Gym unlocks quick catch-up training for the whole party.
The aim is simple: make the challenge about strategy rather than how much time
you are willing to spend levelling Pokémon.

You still play through the original Pokémon campaign. Each area gives you one
unpredictable encounter, Trainers provide a limited supply of experience, and
the next major boss sets your level ceiling. You decide which Pokémon to use,
which battles to take, where to spend your available EXP and money, and how to
rebuild when somebody faints. A full-party wipe ends the run.

This is not meant to replace the traditional Nuzlocke. It is aimed at the part
of the community that likes adapting to a restricted roster, planning for boss
fights, and living with mistakes, but would rather start making the next
decision than spend an evening grinding a replacement.

NuzLike enforces its rules inside your own copy of Pokémon Red, Blue, Yellow,
Crystal, Emerald, FireRed, or LeafGreen. You do not need to track level caps or
encounters separately while playing.

> **This is a very early pre-alpha. It will almost certainly softlock or break
> somewhere.** Do not use a valuable save. Keep your original game backup
> untouched and begin with a disposable save you are prepared to lose.

## How a run works

### Explore, then commit

Random encounters remain off until you obtain your first item capable of
catching a Pokémon. After that, each named area contains exactly one random wild
battle. Its different floors, grass, caves, water, fishing spots, and other
random-encounter methods all share that opportunity.

That one encounter uses the game's Gym Leader battle music: this is the area's
one chance to change your run. NuzLike prefers species your Pokédex does not yet
mark as caught while preserving the encounter table's original weights. If you
have caught every species available there, it falls back to the full table so
the area never becomes unusable.

The next successful encounter roll in a spent area opens the normal battle
screen with an empty opponent and says “But no one came…” before returning to
the overworld. You see that scene only once per playthrough; exhausted areas
then stay quiet. Gifts and scripted static Pokémon do not spend a random area's
encounter. Before your first Badge, encounters below level 5 are raised to level
5 so the opening cannot leave you with unusably weak options.

### Trainer battles replace grinding

Wild Pokémon award no experience during the run. Your growth comes primarily
from the Trainers already placed throughout the campaign. EXP is something you
plan around rather than something you farm.

The next Gym Leader, Elite Four member, or Champion also sets a hard level cap.
Battle experience, Rare Candies, Day Care growth, and scripted level changes
cannot push a Pokémon past it. The player profile always shows the current
**MIN** training level and **MAX** boss cap, so the strategic boundaries are
visible in game.

Reaching the cap does not make later Trainer experience entirely worthless. If
a capped Pokémon would earn EXP, NuzLike takes a configurable portion—75% by
default—and divides that single shared pool among conscious teammates below the
cap. It never multiplies the award, and it never pushes a recipient above MAX.
You can therefore use an established lead to help develop the rest of the team,
but you cannot grind beyond the next challenge.

### Gyms keep new team members usable

Every Poké Mart sells a consumable **Gym Pass** for ₽1,000. Use one while
standing inside a Gym you have defeated and every eligible Pokémon in your
party trains up to that Gym's configured level. This is what makes the no-grind
structure practical: a newly caught specialist or emergency replacement can
join the active roster without hours of repetitive battling.

The game really advances each Pokémon one level at a time behind a fade to
black. It stays out of your way unless a Pokémon wants to learn a move or evolve,
in which case the original decision and evolution scenes appear normally. The
pass is consumed only if somebody can benefit. In Crystal and Emerald, the
training represents three days spent at the Gym and advances the game's clock
accordingly.

EV-improving items also appear in every Poké Mart for one tenth of their normal
price. This keeps team development available without requiring repetitive wild
battles.

### A loss changes your team, not your workload

A Pokémon that faints after battle is immediately retired to reserved PC boxes
named **MEMORIAL**. You may inspect or release a Memorial Pokémon, but you cannot
withdraw it or deposit another Pokémon into the protected boxes. If the
Memorial is full, NuzLike refuses the retirement rather than deleting or
partially moving anything.

A fallen teammate still leaves something behind. By default, the survivors
divide 75% of all experience it earned above the current MIN. Eggs, fainted
teammates, the lost Pokémon, and Pokémon already at MAX are ineligible, and any
experience that cannot fit below the cap is lost. This helps a run continue
after a death without removing the cost of losing a team member.

A full-party wipe invalidates the run save, and the next attempt begins from the
start. If you want a gentler experience, take an emulator save state after each
Gym Leader and treat those as your own manual checkpoints.

### Progress does not depend on catching an HM user

Scarce encounters should affect your battle strategy without blocking campaign
progress. Selecting an HM from the Bag or TM/HM Case therefore gives you
separate **USE** and **TEACH** choices. USE performs its field action without
requiring a compatible party member; TEACH follows the original move-teaching
flow. Badge, story, and location requirements still apply, so this cannot skip
normal progression.

This covers every field HM present in a supported game, including Cut, Fly,
Surf, Strength, Flash, Whirlpool, Waterfall, Rock Smash, and Dive where
applicable.

## Winning the run

Your first Champion victory is the finish line. The game announces that the
NuzLike run is complete and turns off its challenge restrictions: wild
encounters and wild EXP return, the level cap disappears entirely, fainted
Pokémon stop going to the Memorial, and its boxes become ordinary storage. The
profile range, special vitamin economy, and HM Bag shortcuts also disappear.

Gym Passes remain available as a postgame convenience. The rest of the
completed save continues under the original game's normal rules.

## Supported games

NuzLike identifies games by their contents, not their filenames. You need a
backup of the exact English release shown below for the game you want to patch;
you do not need all seven.

| Game | Required release | Canonical SHA-1 |
| --- | --- | --- |
| Pokémon Red | USA/Europe, English | `ea9bcae617fdf159b045185467ae58b2e4a48b9a` |
| Pokémon Blue | USA/Europe, English | `d7037c83e1ae5b39bde3c30787637ba1d4c48ce2` |
| Pokémon Yellow | USA/Europe, English | `cc7d03262ebfaf2f06772c1a480c7d9d5f4a38e1` |
| Pokémon Crystal | USA/Europe, English, version 1.0 | `f4cd194bdee0d04ca4eac29e09b8e4e9d818c133` |
| Pokémon Emerald | USA/Europe, English | `f3ae088181bf583e55daf962a92bb46f4f1d07b7` |
| Pokémon FireRed | USA, English, version 1.0—not 1.1 | `41cb23d8dccc8ebd7c649cd8fbb58eeace6e2fdc` |
| Pokémon LeafGreen | USA, English, version 1.0—not 1.1 | `574fa542ffebb14be69902d1d36f1ec0a4afd71e` |

A raw unmodified backup is ideal. Some dumping tools prepend a common 512-byte
copier header. The graphical and command-line patchers automatically remove
that header only when the underlying ROM then passes the normal canonical hash
or protected-fingerprint checks. The patched output is written in standard
headerless form. Arbitrary prefixes, unknown revisions, and near matches remain
rejected rather than being patched speculatively.

Gold and Silver are not supported; use Crystal for the Johto version of the
challenge. Ruby and Sapphire are not supported; use Emerald for Hoenn. Every
listed port is still undergoing emulator and owner playtesting.
Emerald has received the most manual testing, but even it is not known to be
completable without a blocker.

## Start your own run

You need your own legally obtained backup of a supported game. NuzLike does
not include or download Pokémon games, ROMs, saves, artwork, or extracted game
data.

1. Keep an untouched copy of your original game backup.
2. Download the NuzLike patcher for your platform from the GitHub release.
3. Select the backup; NuzLike identifies the game automatically.
4. Choose Easy, Medium, or Hard caps, or customize every boss individually.
5. Optionally change the capped-EXP sharing percentage from its 75% default.
6. Create a separate patched copy and open it in your emulator or hardware.
7. Begin a fresh, disposable save and start the run.

The patcher never edits the selected input in place. It validates the game and
every protected patch site before atomically writing a separate output file. An
unrecognized revision or incompatible modified game is rejected instead of
being patched speculatively.

Pre-alpha builds target Android, Windows, Linux, and macOS, with ARM64 and
x86-64 variants where the platform supports both. A missing package in a given
release means that build has not yet passed packaging checks; see
[BUILDING.md](BUILDING.md) if you want to build the app yourself.

### Choose the pressure of the run

- **Medium** uses published community hardcore-Nuzlocke cap tables and is the
  default.
- **Easy** and **Hard** use separate, hand-authored per-boss tables. They are
  not blanket numerical offsets and are not presented as community standards.
- **Custom** appears when you edit any individual boss value.

All boss values remain editable, including ambiguous cases such as Yellow's
solo level-28 Raichu. The source comparison and every Medium default are
documented in [configs/LEVEL_CAP_SOURCES.md](configs/LEVEL_CAP_SOURCES.md).

### Debug builds

The patcher provides three independent test switches, all disabled by default:

- infinite health for the player's Pokémon;
- maximum damage from the player's damaging attacks; and
- disabled trainer sight, while still allowing battles when you speak to them.

These options are for rapidly testing a pre-alpha port, not part of the
NuzLike rules. They are baked into the patched copy, so create a separate
debug build rather than using one for a real run.

## Randomizer compatibility

The patcher can run deterministic Universal Pokémon Randomizer FVX settings and
then apply NuzLike without copying bytes back into the wrong ROM layout. Use
this order in the combined interface:

1. make a backup of your supported game;
2. configure NuzLike and the randomizer in the same patcher;
3. build one combined output and retain its manifest for reproduction.

The configured boss caps do not inspect randomized trainer parties. NuzLike
changes only its declared code and configuration regions. All seven supported
games have explicit composition adapters: Red, Blue, Yellow, Crystal, Emerald,
FireRed, and LeafGreen. Compatibility is a design goal, not a promise that every
randomizer option combination will work during pre-alpha.

## Command-line use

The graphical app is the normal way to use NuzLike. A Python 3.11 command-
line patcher is also included for automation:

```sh
python3 -m nuzlike_patcher inspect --input /path/to/your-backup.gba

python3 -m nuzlike_patcher apply \
  --input /path/to/your-backup.gba \
  --recipe recipes/emerald.json \
  --config configs/emerald.json \
  --output /path/to/nuzlike-emerald.gba
```

Copy the matching file in [`configs/`](configs/) before editing it. Invalid
boss names, unknown settings, incorrect game selections, and out-of-range
values fail before an output is created.

## Reporting a problem

When a run freezes, restarts, corrupts graphics, or behaves differently from
the rules above, please include:

- the game and exact revision;
- whether the input was randomized and with which settings;
- the patcher version and configuration used;
- the last reliable in-game action before the failure; and
- an emulator save state or ordinary save made before the failure, if it is
  safe and legal for you to share it.

Never send copyrighted ROM files with a report.

## License and project status

The patcher, recipes, tests, and release tooling in this repository are free
software under the GNU General Public License version 3 or later
(`GPL-3.0-or-later`). The license covers this project's original patching
machinery; it grants no rights to Pokémon or any other third-party work.

This public repository deliberately contains no ROM images, replacement games,
saves, decompilation source, extracted assets, symbols, or maps. Public recipes
describe guarded transformations that users apply to their own backups.

NuzLike is an unofficial fan project and is not affiliated with or endorsed
by Nintendo, Game Freak, Creatures, or The Pokémon Company.

Developers and release reviewers can find build instructions in
[BUILDING.md](BUILDING.md), configuration details in
[configs/README.md](configs/README.md), and the auditable recipe format in
[recipes/FORMAT.md](recipes/FORMAT.md).
