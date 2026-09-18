# Building the NuzLike Patcher

The same application source builds the graphical patcher for every supported
Generation I–III game. Game recognition and recipe selection happen at runtime;
there are no game-specific application binaries.

## Supported packages

| Platform | CPU | Output |
| --- | --- | --- |
| Android | ARM64, x86-64 | split APKs |
| Windows | ARM64, x86-64 | NSIS installer inside a ZIP archive |
| Linux | ARM64, x86-64 | Debian package inside a tar archive |
| macOS | Apple Silicon, Intel | application bundle inside a tar archive |

The GitHub Actions workflow builds on the matching native architecture and
uploads temporary workflow artifacts for review. A deliberately pushed version
tag also publishes those same packages to a pre-release GitHub release after
the source and recipe checks have passed. Tagged releases include a
`SHA256SUMS` file covering every package.

macOS bundles are ad-hoc sealed after assembly and must pass strict `codesign`
verification before packaging. They are not Developer ID signed or notarized.

## Local desktop build

Install Node.js 24, stable Rust, and the system prerequisites for Tauri 2, then:

```sh
npm ci
npm run check
npm run build
```

Pass `-- --target <rust-target> --bundles <formats>` to select the same target
and package formats used in `.github/workflows/build-apps.yml`.

## Local Android build

Install Java 17, the Android SDK, and NDK `27.2.12479018`, set `ANDROID_HOME`
and `NDK_HOME`, and add the Android Rust targets. Then run:

```sh
npm ci
npm run android:init -- --ci
npm run android:build -- --target aarch64 x86_64 --apk --split-per-abi --ci
```

Release APKs are unsigned until an Android signing identity is configured.
Neither the application nor its packages contain ROMs, saves, decompilation
sources, or complete replacement game images.

## Verification

Run the public checks before packaging:

```sh
python3 -m unittest discover -s tests -v
python3 tools/release_audit.py --tree . --history
npm run check
```

`npm run check` compiles the web interface and runs the Rust patcher tests. On
macOS, make sure Rust uses Apple's Clang rather than a GNU `cc` earlier on your
`PATH`:

```sh
CARGO_TARGET_AARCH64_APPLE_DARWIN_LINKER=/usr/bin/clang \
  CC=/usr/bin/clang CXX=/usr/bin/clang++ npm run check
```

The tagged CI matrix remains authoritative for platform-specific packages. A
successful build on one operating system is not evidence that the other seven
artifacts package correctly.

## Browser and offline HTML build

The browser compiles the existing Rust patching and composition functions with
`--no-default-features --features web`. Native builds keep the default `desktop`
feature (also used for Tauri Android). No patching algorithm is reimplemented in
JavaScript. The browser worker embeds its WASM and recipes; the generated HTML
embeds the worker, UI and styles. ROM bytes never leave the device.

```sh
npm ci
rustup target add wasm32-unknown-unknown
cargo install wasm-bindgen-cli --version 0.2.121 --locked
npm run web:build
npx playwright install chromium
npm run web:test
```

Open `ui-dist/index.html` directly, or serve that directory. The versioned
`*-offline.html` is the same self-contained document. `version.json` records its
hash and the WASM hash. Generated binaries are excluded from Git.

The `web-patcher` workflow builds and tests every main-branch change and pull
request. Deployments are deliberate: dispatch it on `main` with `deploy=true`.
It publishes only after its checks pass, and the deployed build stays pinned
until another deployment. This distributes an alpha patcher; it does not assert
that every gameplay scenario has independent acceptance evidence.

### FVX files for the browser

Use the NuzLike FVX fork, not an arbitrary upstream JAR. The native package
contains `engines/UPR-FVX.jar`; its preparation scripts also build the pinned
fork revision. With Java 17 and a settings string for your game:

```sh
java -jar UPR-FVX.jar nuzlike \
  -i clean.gba -o randomized.gba -S 'YOUR_FVX_SETTINGS_STRING' \
  -z 12345 --manifest randomized.fvx.json --log randomized.fvx.log
```

Choose the clean backup, randomized ROM and manifest in the browser. For Game
Boy games use the corresponding `.gb`/`.gbc` files. Keep the generated log.
Do not pass `--layout`: the browser expects the vanilla-to-NuzLike pipeline.

Browser-side FVX generation is not implemented. The current Java bridge opens
and saves ROMs through filesystem APIs and resource bundles; a TeaVM port would
need dedicated compatibility and deterministic-output verification.
[TeaVM](https://www.teavm.org/) can compile Java for browsers, but that alone does
not establish FVX compatibility. [CheerpJ's licensing](https://cheerpj.com/docs/licensing.html)
requires a commercial license for self-hosting/redistribution, so its hosted
runtime is not included in this self-contained offline build. Importing FVX
output preserves the existing validated composition path without a new runtime
or external service.
