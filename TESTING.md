# Testing NuzLike

NuzLike uses several independent checks because no single test can establish
that a cross-generation ROM patch is safe.

## Public patcher checks

The public repository tests:

- canonical and copier-header input recognition;
- refusal of unsupported, mismatched, overlapping, or in-place patches;
- recipe reconstruction and configuration bounds;
- independent debug flags;
- deterministic FVX composition and collision handling;
- version and release metadata;
- GPL notices and the absence of ROMs, saves, extracted assets, private paths,
  and other forbidden payloads throughout Git history; and
- TypeScript and Rust compilation.

Run the portable checks with:

```sh
python3 -m unittest discover -s tests -v
python3 tools/release_audit.py --tree . --history
CARGO_TARGET_AARCH64_APPLE_DARWIN_LINKER=/usr/bin/clang \
  CC=/usr/bin/clang CXX=/usr/bin/clang++ npm run check  # Apple Silicon macOS
```

On Linux and Windows, use the native C/C++ compiler instead of the macOS
environment assignments shown above.

## Compiled-game checks

The private development repository builds every supported port and replays
recorded controller input in pinned headless emulators. Each declared mechanic
has its own predeclared before, intermediate, and after state, authoritative
memory/save assertions, and per-frame visual evidence. Applicable requirements
cover canonical and randomized inputs, configurable extremes, negative paths,
normal save/load cycles, full wipes, and post-Champion behavior.

ROMs, saves, save states, screenshots, and emulator traces are private generated
evidence. They are never committed to this public repository.

## What remains manual

Automation cannot cover every emulator, flash cartridge, randomizer setting, or
route through seven games. Alpha testers should report full-playthrough results
and attach a save or save state from before a defect when it is safe to do so.
Never attach a ROM to an issue.
