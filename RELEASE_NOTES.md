# NuzLike alpha 7

Alpha 7 brings NuzLike to your browser, fixes several battle and experience
problems, and requires an original, supported game backup.

## Patch in your browser

Open the [NuzLike patcher](https://msmfai.github.io/nuzlike/), choose your game
backup and challenge settings, then download a patched copy. No installation,
account, or ROM upload is needed. Your original backup stays unchanged.

You can also download the self-contained HTML patcher from that page for
offline use. All seven games, difficulty presets, custom caps, EXP sharing and
debug options are included.

## Gameplay fixes

- **Crystal:** Fixed cases where an exhausted area's empty encounter could turn
  into another normal wild battle instead of showing “But no one came…”.
- **Red, Blue, Yellow and Crystal:** Choosing a level cap of 100 no longer
  disables challenge rules early. Restrictions such as no wild-battle experience
  stay in effect until you finish the Pokémon League.
- **Emerald:** Elite Four level caps now advance after you defeat each trainer,
  rather than advancing early when you enter their room.
- **Emerald, FireRed and LeafGreen:** Fixed incorrect experience sharing when
  fainted Pokémon are retired to the Memorial and the surviving party is
  rearranged.

## Patching and randomized runs

Use an untouched backup of a [supported game version](README.md#supported-pokémon-games).
The patcher now rejects modified ROMs that older versions could accept, including
ROMs already patched with NuzLike. Supported copier-header backups still work.

For a randomized run, the browser accepts a randomized ROM and matching manifest
created by the NuzLike FVX bridge, alongside your clean backup. It checks those
files before combining them with NuzLike and offers a combined manifest to save
with the result. The browser does not run Java FVX itself; built-in generation
from a seed and settings string remains available in the native desktop patcher.
See the [randomized-run instructions](README.md#randomized-nuzlocke-runs).

## Updating from an earlier version

1. Back up your save and keep your previous patched ROM.
2. Create a new patched ROM from your original game backup using alpha 7.
3. Check that your save loads and your chosen settings work before replacing
   your previous setup.

Supported games remain Red, Blue, Yellow, Crystal, Emerald, FireRed and LeafGreen.

## Known limitations

Android players can use the browser patcher. The current Android APKs are
unsigned and cannot be installed as-is. Desktop packages are
not developer-signed or notarized, so your operating system may show an
unverified-publisher warning.

NuzLike is still alpha software. Full playthroughs, upgrading existing saves and
all combinations of randomizer settings have not been fully tested. Keep backups
and use a save you are prepared to lose.

If you find a problem, please [report it](https://github.com/msmfai/nuzlike/issues)
with your game, NuzLike version, settings, and steps to reproduce it. For randomized
runs, include the seed and randomizer settings. Never attach a ROM.
