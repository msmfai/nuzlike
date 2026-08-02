# Structured recipe format

Recipes are UTF-8 JSON using schema `1`. A release recipe declares:

- `id`: immutable release identifier;
- `game`: canonical game key;
- `accepted_sha1`: exact canonical inputs;
- `allow_modified_input`: whether a compatible randomized input may be used;
- `fingerprints`: invariant regions that must still match;
- `writes`: fixed-size expected/replacement byte pairs; and
- `canonical_output_sha256`: optional exact output check for canonical input.

Each fingerprint has a non-negative byte `offset` and `expected_hex`. Each write
adds `replacement_hex` of exactly the same length. Writes may not overlap or
extend the file. The patcher checks all regions against the original input before
writing anything.

This format intentionally cannot insert arbitrary files, run scripts, resize an
input, or silently overwrite bytes. A randomized input is accepted only if a
recipe opts in and provides invariant fingerprints in addition to per-write
expected bytes.

