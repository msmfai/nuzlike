> [!WARNING]
> Hey there! I'm taking a top down approach to development here where I started with something vibe coded and then clean things up. In pre alpha the documentation is purely AI generated so I can focus on the programming, it will be hand written at final release. The AI-generated documentation is overly verbose by design at this point so all the features of the mod are visible to you.

# [Pre-Alpha] Quicklocke

Quicklocke is a Pokémon challenge mode about building a team with scarce
encounters and strict level caps—without spending hours grinding replacements.
It modifies your own copy of a Generation I, II, or III game and enforces the
rules in the game itself.

The basic rhythm is simple: catch one Pokémon in each area, build a team from
what you find, stay under the next boss cap, and earn reliable team training by
beating Gyms. A fainted Pokémon is retired to the Memorial. A full-party wipe
ends the run. Defeat the Champion and every Quicklocke restriction is lifted.

> **This is a very early pre-alpha. It will almost certainly softlock or break
> somewhere.** Do not use a valuable save. Keep your original game backup
> untouched and begin with a disposable save you are prepared to lose.

## What changes?

### One encounter per area

Random encounters remain disabled until you first obtain an item capable of
catching Pokémon. From then on, each named location gives you one random wild
battle. Different floors, grass, caves, water, fishing spots, and other random
encounter methods sharing that location name all count as the same area.

Your one encounter plays legendary battle music. The next successful encounter
roll in that area opens a battle with an empty opponent slot, displays
“But no one came…”, and returns you to the overworld. That scene is shown only
once in the entire playthrough so it does not become repetitive. After it has
been seen, exhausted areas suppress later encounters silently.

Gift Pokémon and scripted static encounters do not consume the area's random
encounter. Before the first Badge, wild Pokémon below level 5 are raised to
level 5 so an unlucky early encounter is still useful. Wild levels return to
their normal or randomized values after the first Badge.

While Quicklocke is active, a random encounter is also suppressed if its
species is already marked as caught in your Pokédex. Releasing, trading, or
retiring that Pokémon does not make the species available again. A rejected
duplicate does not consume the area's one encounter, so you may keep searching
for a species you have not previously owned. This rule is removed after you
become Champion.

### No wild EXP

Wild battles give no experience while the challenge is active. Trainer battles
are the main source of experience, making the available EXP part of the team-
building puzzle instead of an invitation to grind.

### Enforced boss level caps

Your Pokémon cannot advance beyond the configured cap for the next Gym, Elite
Four member, or Champion. The cap also applies to Rare Candies, Day Care, and
scripted level changes—not only ordinary battle EXP.

If a Pokémon at the cap would receive trainer EXP, it gets none of that award.
By default, 75% of the blocked EXP is divided across eligible conscious
teammates below the cap. It is one shared pool, never multiplied, and no
recipient can cross the current cap. The patcher lets you change the percentage
from 0% to 100%.

The player profile shows the current minimum training level and maximum cap
while the challenge is active.

### Gym Pass training

Every Poké Mart sells a consumable **Gym Pass** for ₽1,000. Use one inside a Gym
you have already defeated to train every eligible Pokémon in your current party
up to that Gym's configured level. The pass is consumed only when at least one
party member can benefit.

Training advances each Pokémon one real level at a time. Ordinary level and stat
screens are skipped, but the native move-learning prompt and evolution scene run
whenever that level would normally trigger them. The training screen otherwise
needs no input.

In games with a clock, the training represents three days spent at the Gym and
advances time-based events accordingly. The Gym Pass is designed to make a new
or under-levelled team member usable without wild grinding.

### HMs work from the Bag

Selecting an HM you own from the Bag or TM/HM Case presents separate **USE** and
**TEACH** actions. USE attempts its field action without requiring a compatible
Pokémon; TEACH always opens the original Pokémon-selection and teaching flow.
The original Badge, story, and location requirements still apply to USE, so it
cannot bypass normal progression.

This applies to every supported game and to every HM that has an overworld
action, including Cut, Fly, Surf, Strength, Flash, Whirlpool, Waterfall, Rock
Smash, and Dive where those moves exist.

### The Memorial and permadeath

After a battle, fainted party members are moved automatically into reserved PC
boxes named **MEMORIAL**. Before becoming Champion, you may inspect or release
Pokémon there, but you cannot withdraw, move, rename, deposit, or give items to
them. The reserved boxes are named from the beginning so they cannot be mistaken
for ordinary storage.

Losing a Pokémon also passes on part of its training: 75% of all EXP it earned
above the current **MIN** is divided evenly among its eligible surviving party
members. The inheritance cannot push anyone above **MAX**. Eggs, fainted
teammates, the lost Pokémon itself, and teammates already at the cap receive
nothing; any EXP that cannot fit is lost.

If the Memorial has no room, Quicklocke will not delete or partially move a
Pokémon. It stops and reports that storage must be freed.

A full-party wipe invalidates the run save. Forgiving checkpoint mode was
removed because these cartridges cannot safely maintain the exact second save
needed for a true rollback. For now, Quicklocke is hardcore only.

### Cheaper training items

EV-improving items are sold in every Poké Mart for one tenth of their usual
price, providing another controlled way to develop the small roster available
to you.

### The challenge ends at the Championship

After the first Champion victory, the game clearly announces that Quicklocke is
over and bypasses the hack's runtime features. Normal wild encounters and wild
EXP return; there is no Quicklocke level cap at all (rather than a cap of 100);
faint retirement is disabled; the profile stops showing the Quicklocke range;
and the Memorial becomes ordinary accessible PC storage. Quicklocke's special
vitamin stock and prices and HM Bag actions also switch off. Gym Passes remain
stocked and usable as the deliberate exception.
The completed save remains playable under the original game's ordinary rules.

## Supported games

Quicklocke identifies games by their contents, not their filenames. You need a
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

## Make a Quicklocke game

You need your own legally obtained backup of a supported game. Quicklocke does
not include or download Pokémon games, ROMs, saves, artwork, or extracted game
data.

1. Keep an untouched copy of your original backup.
2. Download the patcher for your platform from the GitHub release.
3. Select your game backup. The patcher identifies the game automatically.
4. Choose Easy, Medium, Hard, or edit individual boss caps.
5. Set the capped-EXP sharing percentage if you do not want the 75% default.
6. Create a new patched copy and load that copy in your emulator or hardware.
7. Start with a fresh, disposable save.

The patcher never edits the selected input in place. It validates the game and
every protected patch site before atomically writing a separate output file. An
unrecognized revision or incompatible modified game is rejected instead of
being patched speculatively.

Pre-alpha builds target Android, Windows, Linux, and macOS, with ARM64 and
x86-64 variants where the platform supports both. A missing package in a given
release means that build has not yet passed packaging checks; see
[BUILDING.md](BUILDING.md) if you want to build the app yourself.

### Choosing level caps

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
Quicklocke rules. They are baked into the patched copy, so create a separate
debug build rather than using one for a real run.

## Randomizer compatibility

Quicklocke is designed to preserve encounter, species, trainer, item, and move
tables owned by compatible randomizers. Use this order:

1. make a backup of your supported game;
2. randomize that backup using the compatibility profile named by the release;
3. apply Quicklocke to the randomized result.

The configured boss caps do not inspect randomized trainer parties. Quicklocke
changes only its declared code and configuration regions and accepts a modified
input only when all invariant fingerprints still match. Compatibility is a
design goal, not a promise that every randomizer and every option combination
will work during pre-alpha.

## Command-line use

The graphical app is the normal way to use Quicklocke. A Python 3.11 command-
line patcher is also included for automation:

```sh
python3 -m quickloke_patcher inspect --input /path/to/your-backup.gba

python3 -m quickloke_patcher apply \
  --input /path/to/your-backup.gba \
  --recipe recipes/emerald.json \
  --config configs/emerald.json \
  --output /path/to/quicklocke-emerald.gba
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

Quicklocke is an unofficial fan project and is not affiliated with or endorsed
by Nintendo, Game Freak, Creatures, or The Pokémon Company.

Developers and release reviewers can find build instructions in
[BUILDING.md](BUILDING.md), configuration details in
[configs/README.md](configs/README.md), and the auditable recipe format in
[recipes/FORMAT.md](recipes/FORMAT.md).
