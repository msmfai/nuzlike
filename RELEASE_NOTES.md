# NuzLike alpha 7

This update fixes encounter handling, level-cap progression and inherited
experience, and tightens which ROMs the patcher accepts.

## Gameplay fixes

- **Crystal: exhausted-area encounters.** A pending empty encounter could lose
  its state when battle initialization began, allowing a populated battle where
  the empty encounter should have completed. Battle entry now distinguishes wild
  and trainer battles using context that is already initialized. Trainer battles
  continue to discard leftover empty-encounter state.
- **Red, Blue, Yellow and Crystal: level-100 configurations.** Setting a cap to
  100 no longer counts as finishing the challenge. Wild-experience restrictions
  and other challenge rules remain active until the game's completion condition
  is met; normal post-Champion behavior is restored by completion itself.
- **Emerald: Elite Four caps.** League caps now advance when the relevant trainer
  is defeated, rather than when the next room is entered. Entering a room should
  no longer advance the cap prematurely.
- **Emerald, FireRed and LeafGreen: inherited experience.** Retirement now shares
  experience before compacting the party, preventing moved survivors from being
  counted in duplicated party slots. Memorial capacity is checked first, so a
  retirement that cannot be completed does not award experience.

## Patcher and randomizer changes

- Direct patching now requires the complete hash of a supported clean backup.
  Matching only the cartridge header is insufficient, including when an older
  recipe enables modified inputs. Both the desktop patcher and Python CLI enforce
  this rule.
- Validated 512-byte copier headers remain supported. Arbitrary prefixes and
  modified ROMs are rejected rather than treated as clean inputs.
- Use the integrated FVX composition workflow for randomized games. It verifies
  the clean source and randomizer manifest before combining changes. Directly
  opening an already modified ROM is no longer a supported shortcut.

## Verification and remaining limitations

The development checks pass 516 private tests, 34 public Python tests and 15 Rust
tests. TypeScript checking, the production UI build, and recipe checks across all
seven games also pass. New regression coverage executes the encounter guard from
development, candidate and debug Crystal binaries across 81 combinations.

These results do not certify complete playthroughs. The gameplay acceptance gate
still has quarantined emulator evidence awaiting reconstruction or independent
review. New-starter experience, complete retirement/save persistence and every
randomizer configuration are not established by this test pass. This candidate
must not be described as having passed the full gameplay release gate.

## Updating and supported games

Supported games remain Red, Blue, Yellow, Crystal, Emerald, FireRed and LeafGreen.
Only the exact revisions and hashes listed in the [supported-input table](README.md#supported-pokémon-games)
are accepted; support for a game name does not imply support for every revision
or translation.

Create a fresh patched ROM from your untouched supported backup, keep a copy of
your save, and preserve your previous patched ROM until you have checked the
update. Do not apply this patch directly to an earlier NuzLike ROM. Cross-version
save compatibility has not received complete gameplay validation.

NuzLike remains alpha software. Please include the game, patcher version,
configuration, randomizer seed/settings and steps to reproduce when reporting a
bug. Never attach a ROM to an issue.
