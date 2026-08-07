// Copyright (C) 2026 Quicklocke contributors
// SPDX-License-Identifier: GPL-3.0-or-later
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::patcher::{
    PatchReport, Recipe, UserConfig, apply, repair_checksum_for_recipe, write_ranges,
};

const ENGINE: &str = "upr-fvx-quicklocke";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SemanticSettings {
    starters_mode: String,
    evolutions_mode: String,
    movesets_mode: String,
    trainers_mode: String,
    trainer_levels_modified: bool,
    trainer_level_modifier: i16,
    additional_boss_pokemon: u8,
    additional_important_pokemon: u8,
    additional_regular_pokemon: u8,
    wild_randomized: bool,
    wild_zone_mode: String,
    wild_type_mode: String,
    wild_evolution_mode: String,
    wild_levels_modified: bool,
    wild_level_modifier: i16,
    static_pokemon_mode: String,
    static_levels_modified: bool,
    static_level_modifier: i16,
    tm_moves_mode: String,
    tm_hm_compatibility_mode: String,
    full_hm_compatibility: bool,
    keep_field_move_tms: bool,
    field_items_mode: String,
    shop_items_mode: String,
    balance_shop_prices: bool,
    cheap_rare_candies: bool,
    misc_tweaks: i32,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RandomizerManifest {
    schema: u8,
    engine: String,
    engine_version: String,
    upstream_base_revision: String,
    seed: String,
    settings: String,
    semantic_settings: SemanticSettings,
    rom_name: String,
    rom_code: String,
    generation: u8,
    default_extension: String,
    input_size: usize,
    input_sha256: String,
    randomized_size: usize,
    randomized_sha256: String,
    randomizer_log_sha256: String,
    fvx_check_value: i32,
    next_stage: String,
    warnings: Vec<String>,
}

#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct CompositionRule {
    pub system: &'static str,
    pub owner: &'static str,
    pub message: String,
}

#[derive(Debug, Serialize, PartialEq, Eq)]
pub struct Collision {
    pub start: usize,
    pub end: usize,
    pub message: String,
    pub resolution: &'static str,
}

#[derive(Debug, Serialize)]
pub struct CompatibilityReport {
    pub compatible: bool,
    pub seed: String,
    pub engine_version: String,
    pub randomizer_changed_bytes: usize,
    pub collisions: Vec<Collision>,
    pub semantic_rules: Vec<CompositionRule>,
}

#[derive(Debug, Serialize)]
pub struct CombinedManifest {
    pub schema: u8,
    pub pipeline: &'static str,
    pub randomizer_engine: String,
    pub randomizer_engine_version: String,
    pub randomizer_upstream_revision: String,
    pub seed: String,
    pub randomizer_settings: String,
    pub input_sha256: String,
    pub randomized_sha256: String,
    pub randomizer_log_sha256: String,
    pub fvx_check_value: i32,
    pub quicklocke_config: UserConfig,
    pub quicklocke_report: PatchReport,
    pub final_sha256: String,
    pub semantic_rules: Vec<CompositionRule>,
    pub warnings: Vec<String>,
    pub collisions: Vec<Collision>,
}

#[derive(Debug)]
pub struct CombinedResult {
    pub bytes: Vec<u8>,
    pub manifest: CombinedManifest,
}

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn valid_hex(value: &str, length: usize) -> bool {
    value.len() == length && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}

fn one_of(value: &str, accepted: &[&str], field: &str) -> Result<(), String> {
    if accepted.contains(&value) {
        Ok(())
    } else {
        Err(format!(
            "randomizer semantic_settings {field} is unsupported"
        ))
    }
}

fn validate_manifest(
    manifest: &RandomizerManifest,
    clean: &[u8],
    randomized: &[u8],
) -> Result<(), String> {
    if manifest.schema != 2 {
        return Err("randomizer manifest must use schema 2".into());
    }
    if manifest.engine != ENGINE || !manifest.engine_version.starts_with("FVX ") {
        return Err("randomizer manifest must identify the Quicklocke FVX engine".into());
    }
    if !valid_hex(&manifest.upstream_base_revision, 40) {
        return Err("randomizer upstream revision must be a 40-digit Git revision".into());
    }
    let parsed_seed = manifest
        .seed
        .parse::<i64>()
        .map_err(|_| "randomizer seed must be a canonical signed 64-bit integer".to_string())?;
    if parsed_seed.to_string() != manifest.seed {
        return Err("randomizer seed must be a canonical signed 64-bit integer".into());
    }
    if manifest.settings.is_empty()
        || manifest.rom_name.is_empty()
        || manifest.rom_code.is_empty()
        || manifest.default_extension.is_empty()
    {
        return Err("randomizer manifest text fields must not be empty".into());
    }
    if !(1..=3).contains(&manifest.generation) {
        return Err("randomizer generation must be 1, 2, or 3".into());
    }
    for (name, digest) in [
        ("input_sha256", &manifest.input_sha256),
        ("randomized_sha256", &manifest.randomized_sha256),
        ("randomizer_log_sha256", &manifest.randomizer_log_sha256),
    ] {
        if !valid_hex(digest, 64) {
            return Err(format!(
                "randomizer manifest {name} must be a SHA-256 digest"
            ));
        }
    }
    if manifest.next_stage != "quicklocke" {
        return Err("randomizer manifest is not intended for the Quicklocke stage".into());
    }
    if clean.len() != manifest.input_size
        || sha256(clean) != manifest.input_sha256.to_ascii_lowercase()
    {
        return Err("randomizer manifest does not match the clean input ROM".into());
    }
    if randomized.len() != manifest.randomized_size
        || sha256(randomized) != manifest.randomized_sha256.to_ascii_lowercase()
    {
        return Err("randomizer manifest does not match the randomized ROM".into());
    }
    if clean.len() != randomized.len() {
        return Err("FVX changed the ROM size; this recipe cannot be safely composed".into());
    }
    let settings = &manifest.semantic_settings;
    one_of(
        &settings.starters_mode,
        &[
            "UNCHANGED",
            "CUSTOM",
            "COMPLETELY_RANDOM",
            "RANDOM_WITH_TWO_EVOLUTIONS",
            "RANDOM_BASIC",
        ],
        "starters_mode",
    )?;
    one_of(
        &settings.evolutions_mode,
        &["UNCHANGED", "RANDOM", "RANDOM_EVERY_LEVEL"],
        "evolutions_mode",
    )?;
    one_of(
        &settings.movesets_mode,
        &[
            "UNCHANGED",
            "RANDOM_PREFER_SAME_TYPE",
            "COMPLETELY_RANDOM",
            "METRONOME_ONLY",
        ],
        "movesets_mode",
    )?;
    one_of(
        &settings.trainers_mode,
        &[
            "UNCHANGED",
            "RANDOM",
            "DISTRIBUTED",
            "MAINPLAYTHROUGH",
            "TYPE_THEMED",
            "TYPE_THEMED_ELITE4_GYMS",
            "KEEP_THEMED",
            "KEEP_THEME_OR_PRIMARY",
        ],
        "trainers_mode",
    )?;
    one_of(
        &settings.wild_zone_mode,
        &["NONE", "ENCOUNTER_SET", "MAP", "NAMED_LOCATION", "GAME"],
        "wild_zone_mode",
    )?;
    one_of(
        &settings.wild_type_mode,
        &["NONE", "RANDOM_THEMES", "KEEP_PRIMARY"],
        "wild_type_mode",
    )?;
    one_of(
        &settings.wild_evolution_mode,
        &["NONE", "BASIC_ONLY", "KEEP_STAGE"],
        "wild_evolution_mode",
    )?;
    one_of(
        &settings.static_pokemon_mode,
        &[
            "UNCHANGED",
            "RANDOM_MATCHING",
            "COMPLETELY_RANDOM",
            "SIMILAR_STRENGTH",
        ],
        "static_pokemon_mode",
    )?;
    one_of(
        &settings.tm_moves_mode,
        &["UNCHANGED", "RANDOM"],
        "tm_moves_mode",
    )?;
    one_of(
        &settings.tm_hm_compatibility_mode,
        &[
            "UNCHANGED",
            "RANDOM_PREFER_TYPE",
            "COMPLETELY_RANDOM",
            "FULL",
        ],
        "tm_hm_compatibility_mode",
    )?;
    one_of(
        &settings.field_items_mode,
        &["UNCHANGED", "SHUFFLE", "RANDOM", "RANDOM_EVEN"],
        "field_items_mode",
    )?;
    one_of(
        &settings.shop_items_mode,
        &["UNCHANGED", "SHUFFLE", "RANDOM"],
        "shop_items_mode",
    )?;
    for (enabled, modifier, name) in [
        (
            settings.trainer_levels_modified,
            settings.trainer_level_modifier,
            "trainer_level_modifier",
        ),
        (
            settings.wild_levels_modified,
            settings.wild_level_modifier,
            "wild_level_modifier",
        ),
        (
            settings.static_levels_modified,
            settings.static_level_modifier,
            "static_level_modifier",
        ),
    ] {
        if !enabled && modifier != 0 {
            return Err(format!(
                "randomizer semantic_settings {name} must be zero when disabled"
            ));
        }
        if !(-100..=155).contains(&modifier) {
            return Err(format!(
                "randomizer semantic_settings {name} is outside FVX's range"
            ));
        }
    }
    let _ = (
        settings.additional_boss_pokemon,
        settings.additional_important_pokemon,
        settings.additional_regular_pokemon,
        settings.wild_randomized,
        settings.static_levels_modified,
        settings.full_hm_compatibility,
        settings.keep_field_move_tms,
        settings.balance_shop_prices,
        settings.cheap_rare_candies,
        settings.misc_tweaks,
        manifest.fvx_check_value,
        &manifest.warnings,
    );
    Ok(())
}

fn changed_ranges(before: &[u8], after: &[u8]) -> Vec<(usize, usize)> {
    let mut ranges = Vec::new();
    let mut start = None;
    for (offset, (left, right)) in before.iter().zip(after).enumerate() {
        match (left == right, start) {
            (false, None) => start = Some(offset),
            (true, Some(begin)) => {
                ranges.push((begin, offset));
                start = None;
            }
            _ => {}
        }
    }
    if let Some(begin) = start {
        ranges.push((begin, before.len()));
    }
    ranges
}

fn intersections(left: &[(usize, usize)], right: &[(usize, usize)]) -> Vec<(usize, usize)> {
    let mut found = Vec::new();
    for &(left_start, left_end) in left {
        for &(right_start, right_end) in right {
            let start = left_start.max(right_start);
            let end = left_end.min(right_end);
            if start < end {
                found.push((start, end));
            }
        }
    }
    found
}

fn composition_rules(settings: &SemanticSettings) -> Vec<CompositionRule> {
    let mut rules = vec![
        CompositionRule { system: "level_caps", owner: "quicklocke", message: "Player caps remain the selected fixed Quicklocke values and are not recalculated from randomized trainers.".into() },
        CompositionRule { system: "encounters", owner: "quicklocke-runtime", message: "FVX supplies encounter species; Quicklocke enforces capture-item gating, one encounter per area, and duplicate-species exclusion.".into() },
        CompositionRule { system: "hm_progression", owner: "quicklocke-runtime", message: "FVX may change compatibility; Quicklocke preserves direct bag actions and story authorization checks.".into() },
        CompositionRule { system: "shops", owner: "quicklocke-final", message: "FVX randomizes ordinary shop contents first; Quicklocke then guarantees Gym Passes and discounted EV items.".into() },
        CompositionRule { system: "memorial_and_champion", owner: "quicklocke-runtime", message: "Memorial handling and Champion shutdown remain Quicklocke rules.".into() },
    ];
    if settings.trainer_levels_modified {
        rules.push(CompositionRule {
            system: "randomized_trainer_levels",
            owner: "fvx",
            message: format!(
                "FVX applies its {}% trainer modifier while the player cap stays fixed.",
                settings.trainer_level_modifier
            ),
        });
    }
    if settings.wild_levels_modified {
        rules.push(CompositionRule { system: "randomized_wild_levels", owner: "fvx-then-quicklocke", message: format!("FVX applies its {}% wild modifier, then Quicklocke applies only its pre-first-badge floor.", settings.wild_level_modifier) });
    }
    if settings.field_items_mode != "UNCHANGED" {
        rules.push(CompositionRule { system: "capture_item_gate", owner: "fvx-then-quicklocke-runtime", message: "Randomized field items may change when catching items appear; encounters unlock only after one is actually owned.".into() });
    }
    rules
}

pub fn analyze(
    clean: &[u8],
    randomized: &[u8],
    manifest_json: &str,
    recipe: &Recipe,
) -> Result<CompatibilityReport, String> {
    let manifest: RandomizerManifest = serde_json::from_str(manifest_json)
        .map_err(|error| format!("invalid randomizer manifest: {error}"))?;
    validate_manifest(&manifest, clean, randomized)?;
    let changed = changed_ranges(clean, randomized);
    let collisions = intersections(&changed, &write_ranges(recipe)?)
        .into_iter()
        .map(|(start, end)| Collision {
            start,
            end,
            message: format!("FVX and Quicklocke both change bytes 0x{start:x}-0x{:x}; this needs an explicit composition rule", end - 1),
            resolution: "quicklocke-final",
        })
        .collect::<Vec<_>>();
    Ok(CompatibilityReport {
        compatible: collisions.is_empty(),
        seed: manifest.seed,
        engine_version: manifest.engine_version,
        randomizer_changed_bytes: changed.iter().map(|(start, end)| end - start).sum(),
        collisions,
        semantic_rules: composition_rules(&manifest.semantic_settings),
    })
}

pub fn compose(
    clean: &[u8],
    randomized: &[u8],
    manifest_json: &str,
    recipe: &Recipe,
    config: &UserConfig,
) -> Result<CombinedResult, String> {
    if !recipe.has_identity_randomizer_layout() {
        return Err(format!(
            "{}: no verified FVX layout adapter is installed; refusing an unsafe offset-based composition",
            recipe.game()
        ));
    }
    let compatibility = analyze(clean, randomized, manifest_json, recipe)?;
    let randomizer: RandomizerManifest = serde_json::from_str(manifest_json)
        .map_err(|error| format!("invalid randomizer manifest: {error}"))?;
    let mut patched = apply(recipe, Some(config), clean)?;
    for offset in 0..clean.len() {
        if randomized[offset] != clean[offset] && patched.bytes[offset] == clean[offset] {
            patched.bytes[offset] = randomized[offset];
        }
    }
    repair_checksum_for_recipe(&mut patched.bytes, recipe);
    let final_sha256 = sha256(&patched.bytes);
    patched.report.output_sha256 = final_sha256.clone();
    Ok(CombinedResult {
        bytes: patched.bytes,
        manifest: CombinedManifest {
            schema: 1,
            pipeline: "upr-fvx-then-quicklocke",
            randomizer_engine: randomizer.engine,
            randomizer_engine_version: randomizer.engine_version,
            randomizer_upstream_revision: randomizer.upstream_base_revision,
            seed: randomizer.seed,
            randomizer_settings: randomizer.settings,
            input_sha256: randomizer.input_sha256,
            randomized_sha256: randomizer.randomized_sha256,
            randomizer_log_sha256: randomizer.randomizer_log_sha256,
            fvx_check_value: randomizer.fvx_check_value,
            quicklocke_config: config.clone(),
            quicklocke_report: patched.report,
            final_sha256,
            semantic_rules: compatibility.semantic_rules,
            warnings: randomizer.warnings,
            collisions: compatibility.collisions,
        },
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::patcher::parse_recipe;

    fn manifest(clean: &[u8], randomized: &[u8]) -> String {
        serde_json::json!({
            "schema": 2, "engine": ENGINE, "engine_version": "FVX test",
            "upstream_base_revision": "d9700e2dd668f19e1392b8d5e8f370dd484245b3",
            "seed": "42", "settings": "settings", "rom_name": "Test", "rom_code": "T",
            "generation": 2, "default_extension": "gbc", "input_size": clean.len(),
            "input_sha256": sha256(clean), "randomized_size": randomized.len(),
            "randomized_sha256": sha256(randomized), "randomizer_log_sha256": sha256(b"log"),
            "fvx_check_value": 1, "next_stage": "quicklocke", "warnings": [],
            "semantic_settings": {
                "starters_mode":"UNCHANGED", "evolutions_mode":"UNCHANGED", "movesets_mode":"UNCHANGED",
                "trainers_mode":"RANDOM", "trainer_levels_modified":true, "trainer_level_modifier":10,
                "additional_boss_pokemon":0, "additional_important_pokemon":0, "additional_regular_pokemon":0,
                "wild_randomized":true, "wild_zone_mode":"MAP", "wild_type_mode":"NONE",
                "wild_evolution_mode":"NONE", "wild_levels_modified":false, "wild_level_modifier":0,
                "static_pokemon_mode":"UNCHANGED", "static_levels_modified":false, "static_level_modifier":0,
                "tm_moves_mode":"RANDOM", "tm_hm_compatibility_mode":"FULL", "full_hm_compatibility":true,
                "keep_field_move_tms":true, "field_items_mode":"RANDOM", "shop_items_mode":"RANDOM",
                "balance_shop_prices":true, "cheap_rare_candies":false, "misc_tweaks":0
            }
        }).to_string()
    }

    #[test]
    fn exact_manifest_and_non_overlapping_changes_are_compatible() {
        let clean = vec![0_u8; 1024];
        let mut randomized = clean.clone();
        randomized[600] = 1;
        let recipe = parse_recipe(&serde_json::json!({
            "schema":1, "id":"test", "game":"crystal", "accepted_sha1":["0".repeat(40)],
            "fingerprints":[], "writes":[{"offset":700,"expected_hex":"0000","replacement_hex":"0102"}]
        }).to_string()).unwrap();
        let report = analyze(&clean, &randomized, &manifest(&clean, &randomized), &recipe).unwrap();
        assert!(report.compatible);
        assert_eq!(report.randomizer_changed_bytes, 1);
        assert!(
            report
                .semantic_rules
                .iter()
                .any(|rule| rule.system == "randomized_trainer_levels")
        );
        assert!(
            report
                .semantic_rules
                .iter()
                .any(|rule| rule.system == "capture_item_gate")
        );
    }

    #[test]
    fn overlapping_changes_and_tampered_hashes_are_rejected_or_reported() {
        let clean = vec![0_u8; 1024];
        let mut randomized = clean.clone();
        randomized[701] = 1;
        let recipe = parse_recipe(&serde_json::json!({
            "schema":1, "id":"test", "game":"emerald", "accepted_sha1":["0".repeat(40)],
            "fingerprints":[], "writes":[{"offset":700,"expected_hex":"0000","replacement_hex":"0102"}]
        }).to_string()).unwrap();
        let json = manifest(&clean, &randomized);
        let report = analyze(&clean, &randomized, &json, &recipe).unwrap();
        assert!(!report.compatible);
        assert_eq!(
            (report.collisions[0].start, report.collisions[0].end),
            (701, 702)
        );
        let mut tampered = randomized;
        tampered[10] = 9;
        assert!(
            analyze(&clean, &tampered, &json, &recipe)
                .unwrap_err()
                .contains("does not match")
        );
    }

    #[test]
    fn composition_is_deterministic_and_records_both_configurations() {
        let mut clean = vec![0_u8; 1024];
        clean[20] = 20;
        clean[21] = 75;
        let mut randomized = clean.clone();
        randomized[600] = 1;
        let recipe = parse_recipe(
            &serde_json::json!({
                "schema":1, "id":"test", "game":"emerald", "accepted_sha1":["0".repeat(40)],
                "allow_modified_input":true,
                "randomizer_layout":{"schema":1,"mode":"identity"},
                "fingerprints":[{"offset":0,"expected_hex":"0000"}],
                "writes":[{"offset":700,"expected_hex":"0000","replacement_hex":"0102"}],
                "configurable":{
                    "level_caps":[{"id":"roxanne","offset":20,"default":20}],
                    "overflow_percent":{"offset":21,"default":75,"minimum":0,"maximum":100}
                }
            })
            .to_string(),
        )
        .unwrap();
        let config = crate::patcher::parse_config(
            r#"{"schema":1,"game":"emerald","level_caps":{"roxanne":18},"overflow_percent":60}"#,
        )
        .unwrap();
        let bridge_manifest = manifest(&clean, &randomized);
        let first = compose(&clean, &randomized, &bridge_manifest, &recipe, &config).unwrap();
        let second = compose(&clean, &randomized, &bridge_manifest, &recipe, &config).unwrap();
        assert_eq!(first.bytes, second.bytes);
        assert_eq!(first.manifest.final_sha256, second.manifest.final_sha256);
        assert_eq!(first.manifest.randomizer_settings, "settings");
        assert_eq!(first.manifest.quicklocke_config.level_caps["roxanne"], 18);
        assert_eq!(first.bytes[20], 18);
        assert_eq!(first.bytes[21], 60);
        assert_eq!(&first.bytes[700..702], &[1, 2]);
    }

    #[test]
    fn composition_rebases_fvx_bytes_and_records_quicklocke_owned_collisions() {
        let clean = vec![0_u8; 1024];
        let mut randomized = clean.clone();
        randomized[600] = 9;
        randomized[701] = 9;
        let recipe = parse_recipe(
            &serde_json::json!({
                "schema":1, "id":"test", "game":"emerald", "accepted_sha1":["0".repeat(40)],
                "allow_modified_input":true,
                "randomizer_layout":{"schema":1,"mode":"identity"},
                "fingerprints":[{"offset":0,"expected_hex":"0000"}],
                "writes":[{"offset":700,"expected_hex":"0000","replacement_hex":"0102"}]
            })
            .to_string(),
        )
        .unwrap();
        let config = crate::patcher::parse_config(r#"{"schema":1,"game":"emerald"}"#).unwrap();
        let result = compose(
            &clean,
            &randomized,
            &manifest(&clean, &randomized),
            &recipe,
            &config,
        )
        .unwrap();
        assert_eq!(result.bytes[600], 9);
        assert_eq!(&result.bytes[700..702], &[1, 2]);
        assert_eq!(result.manifest.collisions.len(), 1);
        assert_eq!(result.manifest.collisions[0].resolution, "quicklocke-final");
    }
}
