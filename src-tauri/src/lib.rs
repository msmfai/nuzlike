#![recursion_limit = "256"]

// Copyright (C) 2026 Quicklocke contributors
// SPDX-License-Identifier: GPL-3.0-or-later
mod patcher;
mod randomizer;

use std::collections::{BTreeMap, BTreeSet};

use include_dir::{Dir, include_dir};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::ipc::{InvokeBody, Request, Response};

use patcher::{UserConfig, apply, inspect, parse_config, parse_recipe};
use randomizer::{analyze, compose};

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
    level_cap_presets: LevelCapPresets,
    recipe_id: Option<String>,
}

#[derive(Debug, Serialize)]
struct Catalog {
    schema: u8,
    games: Vec<CatalogGame>,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
struct LevelCapPresets {
    easy: BTreeMap<String, u8>,
    medium: BTreeMap<String, u8>,
    hard: BTreeMap<String, u8>,
}

#[derive(Debug, Deserialize)]
struct PresetCatalog {
    schema: u8,
    games: BTreeMap<String, LevelCapPresets>,
}

#[derive(Debug, Deserialize)]
struct PatchEnvelope {
    recipe_id: String,
    config: Value,
}

#[derive(Debug, Deserialize)]
struct RandomizerAnalysisEnvelope {
    recipe_id: String,
    manifest_json: String,
    clean_size: usize,
}

#[derive(Debug, Deserialize)]
struct RandomizerCompositionEnvelope {
    recipe_id: String,
    manifest_json: String,
    clean_size: usize,
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
        "crystal" => "Pokémon Crystal",
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

fn embedded_presets() -> Result<BTreeMap<String, LevelCapPresets>, String> {
    let file = CONFIGS
        .get_file("presets/level_caps.json")
        .ok_or_else(|| "embedded level-cap presets are missing".to_string())?;
    let catalog: PresetCatalog = serde_json::from_slice(file.contents())
        .map_err(|error| format!("embedded level-cap presets are invalid: {error}"))?;
    if catalog.schema != 1 {
        return Err("embedded level-cap presets must use schema 1".into());
    }
    Ok(catalog.games)
}

fn validate_presets(
    game: &str,
    defaults: &UserConfig,
    presets: &LevelCapPresets,
) -> Result<(), String> {
    if presets.medium != defaults.level_caps {
        return Err(format!(
            "medium level-cap preset for {game} must exactly match its researched defaults"
        ));
    }
    let expected: BTreeSet<_> = defaults.level_caps.keys().collect();
    for (name, levels) in [
        ("easy", &presets.easy),
        ("medium", &presets.medium),
        ("hard", &presets.hard),
    ] {
        if levels.keys().collect::<BTreeSet<_>>() != expected {
            return Err(format!(
                "{name} level-cap preset for {game} must contain every configured boss exactly once"
            ));
        }
        if levels.values().any(|level| !(1..=100).contains(level)) {
            return Err(format!(
                "{name} level-cap preset for {game} contains a level outside 1 through 100"
            ));
        }
    }
    for boss in &expected {
        if presets.easy[*boss] < presets.medium[*boss]
            || presets.medium[*boss] < presets.hard[*boss]
        {
            return Err(format!(
                "level-cap presets for {game}.{boss} must be ordered easy >= medium >= hard"
            ));
        }
    }
    Ok(())
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
    let expected_games: BTreeSet<_> = manifest.canonical_inputs.keys().cloned().collect();
    let mut presets = embedded_presets()?;
    if presets.keys().cloned().collect::<BTreeSet<_>>() != expected_games {
        return Err("level-cap presets must contain exactly every supported game".into());
    }
    let mut games = Vec::with_capacity(manifest.canonical_inputs.len());
    for (id, canonical_sha1) in manifest.canonical_inputs {
        let recipe_id = manifest
            .releases
            .iter()
            .find(|release| release.game == id)
            .map(|release| release.id.clone());
        let default_config = embedded_config(&id)?;
        let level_cap_presets = presets
            .remove(&id)
            .ok_or_else(|| format!("level-cap presets for {id} are missing"))?;
        validate_presets(&id, &default_config, &level_cap_presets)?;
        games.push(CatalogGame {
            name: game_name(&id),
            default_config,
            level_cap_presets,
            id,
            canonical_sha1,
            recipe_id,
        });
    }
    games.sort_by_key(|game| {
        const ORDER: [&str; 7] = [
            "red",
            "blue",
            "yellow",
            "crystal",
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

#[tauri::command]
fn analyze_randomized_rom(request: Request<'_>) -> Result<Response, String> {
    let body = raw_body(&request)?;
    if body.len() < 4 {
        return Err("randomizer analysis request is truncated".into());
    }
    let metadata_size = u32::from_be_bytes(body[..4].try_into().unwrap()) as usize;
    let metadata_end = 4_usize
        .checked_add(metadata_size)
        .ok_or_else(|| "randomizer analysis request metadata is too large".to_string())?;
    if metadata_end > body.len() {
        return Err("randomizer analysis request metadata is truncated".into());
    }
    let envelope: RandomizerAnalysisEnvelope = serde_json::from_slice(&body[4..metadata_end])
        .map_err(|error| format!("randomizer analysis metadata is invalid: {error}"))?;
    let rom_bytes = &body[metadata_end..];
    if envelope.clean_size > rom_bytes.len() {
        return Err("randomizer analysis clean ROM is truncated".into());
    }
    let release = manifest()?
        .releases
        .into_iter()
        .find(|release| release.id == envelope.recipe_id)
        .ok_or_else(|| format!("unknown release recipe {:?}", envelope.recipe_id))?;
    let recipe_json = embedded_recipe(&release.id, release.recipe.as_deref())?;
    let recipe = parse_recipe(&recipe_json)?;
    let report = analyze(
        &rom_bytes[..envelope.clean_size],
        &rom_bytes[envelope.clean_size..],
        &envelope.manifest_json,
        &recipe,
    )?;
    serde_json::to_vec(&report)
        .map(Response::new)
        .map_err(|error| format!("cannot encode randomizer analysis: {error}"))
}

#[tauri::command]
fn compose_randomized_rom(request: Request<'_>) -> Result<Response, String> {
    let body = raw_body(&request)?;
    if body.len() < 4 {
        return Err("randomizer composition request is truncated".into());
    }
    let metadata_size = u32::from_be_bytes(body[..4].try_into().unwrap()) as usize;
    let metadata_end = 4_usize
        .checked_add(metadata_size)
        .ok_or_else(|| "randomizer composition metadata is too large".to_string())?;
    if metadata_end > body.len() {
        return Err("randomizer composition metadata is truncated".into());
    }
    let envelope: RandomizerCompositionEnvelope = serde_json::from_slice(&body[4..metadata_end])
        .map_err(|error| format!("randomizer composition metadata is invalid: {error}"))?;
    let rom_bytes = &body[metadata_end..];
    if envelope.clean_size > rom_bytes.len() {
        return Err("randomizer composition clean ROM is truncated".into());
    }
    let release = manifest()?
        .releases
        .into_iter()
        .find(|release| release.id == envelope.recipe_id)
        .ok_or_else(|| format!("unknown release recipe {:?}", envelope.recipe_id))?;
    let recipe_json = embedded_recipe(&release.id, release.recipe.as_deref())?;
    let recipe = parse_recipe(&recipe_json)?;
    let config = parse_config(
        &serde_json::to_string(&envelope.config)
            .map_err(|error| format!("cannot encode patch config: {error}"))?,
    )?;
    let result = compose(
        &rom_bytes[..envelope.clean_size],
        &rom_bytes[envelope.clean_size..],
        &envelope.manifest_json,
        &recipe,
        &config,
    )?;
    let report = serde_json::to_vec(&result.manifest)
        .map_err(|error| format!("cannot encode combined manifest: {error}"))?;
    let report_size =
        u32::try_from(report.len()).map_err(|_| "combined manifest is too large".to_string())?;
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
            patch_rom,
            analyze_randomized_rom,
            compose_randomized_rom
        ])
        .run(tauri::generate_context!())
        .expect("error while running Quicklocke Patcher");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embeds_one_parseable_recipe_for_every_supported_game() {
        let manifest = manifest().unwrap();
        assert_eq!(manifest.releases.len(), manifest.canonical_inputs.len());
        for release in manifest.releases {
            let json = embedded_recipe(&release.id, release.recipe.as_deref()).unwrap();
            let recipe = parse_recipe(&json).unwrap();
            assert_eq!(recipe_id(&recipe), release.id);
        }
    }

    #[test]
    fn embeds_complete_ordered_level_cap_presets() {
        let catalog = get_catalog().unwrap();
        assert_eq!(catalog.games.len(), 7);
        assert_eq!(
            catalog
                .games
                .iter()
                .map(|game| game.id.as_str())
                .collect::<Vec<_>>(),
            vec![
                "red",
                "blue",
                "yellow",
                "crystal",
                "emerald",
                "firered",
                "leafgreen"
            ]
        );
        for game in catalog.games {
            validate_presets(&game.id, &game.default_config, &game.level_cap_presets).unwrap();
        }
        let yellow = get_catalog()
            .unwrap()
            .games
            .into_iter()
            .find(|game| game.id == "yellow")
            .unwrap();
        assert_eq!(yellow.level_cap_presets.medium["surge"], 28);
    }
}
