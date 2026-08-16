# NuzLike alpha 4

This release hardens the development and release pipeline without changing the
rules introduced in alpha 3.

- Emulator replays now have strict process-tree timeouts and preserve evidence
  when a test stalls or fails.
- Recorded tests run without native frame-rate throttling while keeping every
  controller input attached to its exact emulated frame.
- Development runs reuse verified content-addressed evidence and remove
  redundant setup; release runs continue to force fresh evidence.
- Gen III tests use a fresh emulator core per save state after full-matrix
  testing found that persistent cores do not restore all host-side state.
- GitHub package builds now cancel superseded branch work, reuse safe build
  caches, and retain immutable tag builds until release assets are published.

The alpha 3 encounter and experience fixes remain included for Red, Blue,
Yellow, Crystal, Emerald, FireRed, and LeafGreen.

NuzLike remains alpha software. Full-playthrough coverage is incomplete, so
keep your original backup untouched, create a new patched file, and use a
separate save you are prepared to lose. Bug reports are welcome.

Packages are not yet signed by platform distribution identities or notarized.
Verify downloads with the accompanying `SHA256SUMS` file and consult the README
for the exact supported game revisions.
