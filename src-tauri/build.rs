// Copyright (C) 2026 NuzLike contributors
// SPDX-License-Identifier: GPL-3.0-or-later
fn main() {
    #[cfg(feature = "desktop")]
    tauri_build::build()
}
