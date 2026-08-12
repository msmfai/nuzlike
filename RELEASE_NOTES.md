# NuzLike alpha 2

This alpha release fixes malformed macOS application bundles from alpha 1. The
macOS packages are now explicitly sealed and must pass strict bundle validation
before they can be published.

The unified NuzLike patcher supports
Pokémon Red, Blue, Yellow, Crystal, Emerald, FireRed, and LeafGreen, with
optional Universal Pokémon Randomizer FVX settings-string composition.

The alpha includes the complete declared NuzLike ruleset, configurable boss
caps and capped-EXP sharing, independent debug switches, copier-header
normalization, and native packages for Android, Windows, Linux, and macOS.

All declared mechanics pass deterministic headless-emulator scenarios in every
applicable game. Recipe validation, input safety, configuration, randomizer
composition, save persistence, and the public-source boundary are also tested.

Human full-playthrough coverage is not yet complete. Keep your original backup
untouched, create a new patched file, and use a separate save you are prepared
to lose. Randomizer combinations, uncommon emulators, and original hardware may
still expose progression blockers or presentation defects.

Packages are not yet signed by platform distribution identities or notarized.
Verify downloads with the accompanying `SHA256SUMS` file and consult the README
for the exact supported game revisions.
