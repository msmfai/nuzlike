// Copyright (C) 2026 Quicklocke contributors
// SPDX-License-Identifier: GPL-3.0-or-later
mod patcher;

use std::collections::BTreeMap;

use include_dir::{Dir, include_dir};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::ipc::{InvokeBody, Request, Response};

use patcher::{UserConfig, apply, inspect, parse_config, parse_recipe};

static RECIPES: Dir<'_> = include_dir!("$CARGO_MANIFEST_DIR/../recipes");
static CONFIGS: Dir<'_> = include_dir!("$CARGO_MANIFEST_DIR/../configs");

#[derive(Debug, Deserialize)]
struct Manifest {
    schema: u8,
    releases: Vec<Release>,
    canonical_inputs: BTreeMap<String, String>,
}

#[derive(Debug, Deserialize)]
struct Release {
    id: String,
    game: String,
    #[serde(default)]
    recipe: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CatalogGame {
    id: String,
    name: String,
    canonical_sha1: String,
    default_config: UserConfig,
    recipe_id: Option<String>,
}

#[derive(Debug, Serialize)]
struct Catalog {
    schema: u8,
    games: Vec<CatalogGame>,
}

#[derive(Debug, Deserialize)]
struct PatchEnvelope {
    recipe_id: String,
    config: Value,
}

fn raw_body<'a>(request: &'a Request<'a>) -> Result<&'a [u8], String> {
    match request.body() {
        InvokeBody::Raw(data) => Ok(data),
        _ => Err("patcher commands require a raw binary request".into()),
    }
}

fn manifest() -> Result<Manifest, String> {
    let file = RECIPES
        .get_file("manifest.json")
        .ok_or_else(|| "embedded recipe manifest is missing".to_string())?;
    let manifest: Manifest = serde_json::from_slice(file.contents())
        .map_err(|error| format!("embedded recipe manifest is invalid: {error}"))?;
    if manifest.schema != 1 {
        return Err("embedded recipe manifest must use schema 1".into());
    }
    Ok(manifest)
}

fn game_name(game: &str) -> String {
    match game {
        "red" => "Pokémon Red",
        "blue" => "Pokémon Blue",
        "yellow" => "Pokémon Yellow",
        "gold" => "Pokémon Gold",
        "silver" => "Pokémon Silver",
        "crystal" => "Pokémon Crystal",
        "ruby" => "Pokémon Ruby",
        "sapphire" => "Pokémon Sapphire",
        "emerald" => "Pokémon Emerald",
        "firered" => "Pokémon FireRed",
        "leafgreen" => "Pokémon LeafGreen",
        other => return other.to_string(),
    }
    .to_string()
}

fn embedded_config(game: &str) -> Result<UserConfig, String> {
    let path = format!("{game}.json");
    let file = CONFIGS
        .get_file(path)
        .ok_or_else(|| format!("embedded default config for {game} is missing"))?;
    let json = std::str::from_utf8(file.contents())
        .map_err(|_| format!("embedded default config for {game} is not UTF-8"))?;
    parse_config(json)
}

fn embedded_recipe(id: &str, hinted_file: Option<&str>) -> Result<String, String> {
    if let Some(path) = hinted_file
        && let Some(file) = RECIPES.get_file(path)
    {
        let json = std::str::from_utf8(file.contents())
            .map_err(|_| format!("embedded recipe {path} is not UTF-8"))?;
        let recipe = parse_recipe(json)?;
        if recipe_id(&recipe) == id {
            return Ok(json.to_string());
        }
    }
    for file in RECIPES.files() {
        if file.path() == std::path::Path::new("manifest.json") {
            continue;
        }
        let Ok(json) = std::str::from_utf8(file.contents()) else {
            continue;
        };
        let Ok(recipe) = parse_recipe(json) else {
            continue;
        };
        if recipe_id(&recipe) == id {
            return Ok(json.to_string());
        }
    }
    Err(format!(
        "release recipe {id:?} is not embedded in this build"
    ))
}

fn recipe_id(recipe: &patcher::Recipe) -> &str {
    // Keep recipe fields private to the safety module except for this lookup.
    recipe.id()
}

#[tauri::command]
fn get_catalog() -> Result<Catalog, String> {
    let manifest = manifest()?;
    let mut games = Vec::with_capacity(manifest.canonical_inputs.len());
    for (id, canonical_sha1) in manifest.canonical_inputs {
        let recipe_id = manifest
            .releases
            .iter()
            .find(|release| release.game == id)
            .map(|release| release.id.clone());
        games.push(CatalogGame {
            name: game_name(&id),
            default_config: embedded_config(&id)?,
            id,
            canonical_sha1,
            recipe_id,
        });
    }
    games.sort_by_key(|game| {
        const ORDER: [&str; 11] = [
            "red",
            "blue",
            "yellow",
            "gold",
            "silver",
            "crystal",
            "ruby",
            "sapphire",
            "emerald",
            "firered",
            "leafgreen",
        ];
        ORDER
            .iter()
            .position(|candidate| *candidate == game.id)
            .unwrap_or(usize::MAX)
    });
    Ok(Catalog { schema: 1, games })
}

#[tauri::command]
fn inspect_rom(request: Request<'_>) -> Result<patcher::InspectResult, String> {
    Ok(inspect(raw_body(&request)?))
}

#[tauri::command]
fn patch_rom(request: Request<'_>) -> Result<Response, String> {
    let body = raw_body(&request)?;
    if body.len() < 4 {
        return Err("patch request is truncated".into());
    }
    let metadata_size = u32::from_be_bytes(body[0..4].try_into().unwrap()) as usize;
    let metadata_end = 4_usize
        .checked_add(metadata_size)
        .ok_or_else(|| "patch request metadata size overflows".to_string())?;
    if metadata_end > body.len() {
        return Err("patch request metadata is truncated".into());
    }
    let envelope: PatchEnvelope = serde_json::from_slice(&body[4..metadata_end])
        .map_err(|error| format!("patch request metadata is invalid: {error}"))?;
    let manifest = manifest()?;
    let release = manifest
        .releases
        .iter()
        .find(|release| release.id == envelope.recipe_id)
        .ok_or_else(|| format!("unknown release recipe {:?}", envelope.recipe_id))?;
    let recipe_json = embedded_recipe(&release.id, release.recipe.as_deref())?;
    let recipe = parse_recipe(&recipe_json)?;
    let config_json = serde_json::to_string(&envelope.config)
        .map_err(|error| format!("cannot encode patch config: {error}"))?;
    let config = parse_config(&config_json)?;
    let result = apply(&recipe, Some(&config), &body[metadata_end..])?;
    let report = serde_json::to_vec(&result.report)
        .map_err(|error| format!("cannot encode patch report: {error}"))?;
    let report_size =
        u32::try_from(report.len()).map_err(|_| "patch report is too large".to_string())?;
    let mut response = Vec::with_capacity(4 + report.len() + result.bytes.len());
    response.extend_from_slice(&report_size.to_be_bytes());
    response.extend_from_slice(&report);
    response.extend_from_slice(&result.bytes);
    Ok(Response::new(response))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            get_catalog,
            inspect_rom,
            patch_rom
        ])
        .run(tauri::generate_context!())
        .expect("error while running Quicklocke Patcher");
}
