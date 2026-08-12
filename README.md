# NuzLike

NuzLike is a roguelite twist on the Nuzlocke format for players who enjoy the
team-building and risk but not the grinding. It turns each Pokémon story into a
finite-resource run where progress comes from making good decisions with the
team you find.

The game enforces the rules for you, so there is no encounter spreadsheet or
manual level-cap tracking.

> [!WARNING]
> NuzLike is alpha software. Not all features are tested, so please be prepared
> to lose save games. All GitHub issues are appreciated and will be dealt with
> promptly.

## What changes

- Each area gives you one wild encounter, with uncaught species prioritised.
- Wild Pokémon give no EXP. Trainers are the finite source of experience, and
  boss-based level caps prevent overlevelling.
- Gym Passes let you bring replacement party members up to a useful level
  without grinding.
- Fainted Pokémon are retired to the PC Memorial. A full-party wipe ends the
  run.
- Repeatable side activities are restricted during the run so the best use of
  your time is continuing the story and fighting Trainers.
- Becoming Champion ends the challenge restrictions while keeping the useful
  quality-of-life features.

Level caps and capped-EXP sharing are configurable. Easy, Medium, and Hard cap
sets are included.

## Supported games

NuzLike supports Pokémon Red, Blue, Yellow, Crystal, Emerald, FireRed, and
LeafGreen. Gold and Silver are represented by Crystal; Ruby and Sapphire are
represented by Emerald.

The patcher requires your own legally obtained backup of one exact English
release:

| Game | Required release | SHA-1 |
| --- | --- | --- |
| Red | USA/Europe, English | `ea9bcae617fdf159b045185467ae58b2e4a48b9a` |
| Blue | USA/Europe, English | `d7037c83e1ae5b39bde3c30787637ba1d4c48ce2` |
| Yellow | USA/Europe, English | `cc7d03262ebfaf2f06772c1a480c7d9d5f4a38e1` |
| Crystal | USA/Europe, English, version 1.0 | `f4cd194bdee0d04ca4eac29e09b8e4e9d818c133` |
| Emerald | USA/Europe, English | `f3ae088181bf583e55daf962a92bb46f4f1d07b7` |
| FireRed | USA, English, version 1.0—not 1.1 | `41cb23d8dccc8ebd7c649cd8fbb58eeace6e2fdc` |
| LeafGreen | USA, English, version 1.0—not 1.1 | `574fa542ffebb14be69902d1d36f1ec0a4afd71e` |

Common 512-byte copier headers are handled automatically when the underlying
game is supported. Other revisions are rejected rather than patched
speculatively.

## Get started

1. Download the patcher for Windows, macOS, Linux, or Android from the
   [latest release](https://github.com/msmfai/nuzlike/releases/latest).
2. Select your original game backup.
3. Choose a level-cap preset or customise the caps.
4. Save the patched game as a new file and begin a fresh save.

The original backup is never edited in place. Alpha packages may be unsigned,
so your operating system may ask you to approve the application. Source build
instructions are in [BUILDING.md](BUILDING.md).

## Randomized runs

NuzLike can apply an FVX settings string and seed before adding its own rules.
The patcher records a manifest and log so the result can be reproduced. Random
Trainer parties do not change your selected level caps.

Randomizer compatibility is tested across every supported game, but the full
combination of possible FVX options is too large to exhaust during alpha.

## Reporting problems

Please open an issue for freezes, resets, corrupted graphics, or progression
blockers. Include the game revision, NuzLike version, emulator or hardware,
selected settings, and the last reliable action. For randomized runs, also
include the FVX settings string and seed.

Never attach a ROM to a public issue.

See [RELEASE_NOTES.md](RELEASE_NOTES.md) for current alpha limitations,
[configs/README.md](configs/README.md) for configuration details, and
[TESTING.md](TESTING.md) for the verification process.

## License

NuzLike's original patcher, recipes, tests, and release tooling are licensed
under the [GNU General Public License version 3 or later](LICENSE). This project
contains no games and grants no rights to third-party material.

NuzLike is an unofficial fan project and is not affiliated with or endorsed by
Nintendo, Game Freak, Creatures, or The Pokémon Company.
