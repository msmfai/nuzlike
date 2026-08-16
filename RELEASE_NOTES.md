# NuzLike alpha 3

This release fixes encounter and experience regressions reported during Crystal
playtesting, and applies the relevant protections across every supported game.

- Encounter selection now terminates when every locally available species has
  already been caught.
- A Pokémon's first trainer experience award can no longer corrupt its level.
- Shared capped experience now uses the games' normal level-up path, including
  move learning and evolution.
- Level caps remain enforced after battle dialogue completes.
- Generation I experience messages remain inside the battle text area.

The reproductions for these bugs are now permanent deterministic emulator tests
covering Red, Blue, Yellow, Crystal, Emerald, FireRed, and LeafGreen where the
mechanic applies. The public recipes were regenerated from the same production
builds used by those tests.

NuzLike remains alpha software. Full-playthrough coverage is incomplete, so
keep your original backup untouched, create a new patched file, and use a
separate save you are prepared to lose. Bug reports are welcome.

Packages are not yet signed by platform distribution identities or notarized.
Verify downloads with the accompanying `SHA256SUMS` file and consult the README
for the exact supported game revisions.
