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
