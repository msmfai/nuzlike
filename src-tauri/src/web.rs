// Copyright (C) 2026 NuzLike contributors
// SPDX-License-Identifier: GPL-3.0-or-later
use wasm_bindgen::prelude::*;

/// The browser and native app share validation, recipes and byte operations.
#[wasm_bindgen]
pub fn catalog() -> Result<String, JsError> {
    let value = super::get_catalog().map_err(|e| JsError::new(&e))?;
    Ok(serde_json::to_string(&value)?)
}

#[wasm_bindgen]
pub fn inspect(bytes: &[u8]) -> Result<String, JsError> {
    let result = super::inspect_rom_bytes(bytes).map_err(|e| JsError::new(&e))?;
    Ok(serde_json::to_string(&result)?)
}

#[wasm_bindgen]
pub fn patch(bytes: &[u8]) -> Result<Vec<u8>, JsError> {
    super::patch_rom_bytes(bytes).map_err(|e| JsError::new(&e))
}

#[wasm_bindgen]
pub fn compose(bytes: &[u8]) -> Result<Vec<u8>, JsError> {
    super::compose_randomized_rom_bytes(bytes).map_err(|e| JsError::new(&e))
}

#[wasm_bindgen]
pub fn analyze(bytes: &[u8]) -> Result<Vec<u8>, JsError> {
    super::analyze_randomized_rom_bytes(bytes).map_err(|e| JsError::new(&e))
}
