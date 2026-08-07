// Copyright (C) 2026 Quicklocke contributors
// SPDX-License-Identifier: GPL-3.0-or-later
use std::collections::{BTreeMap, BTreeSet};
use std::io::Read;

use base64::{Engine as _, engine::general_purpose::STANDARD as BASE64};
use flate2::read::ZlibDecoder;
use serde::{Deserialize, Serialize};
use sha1::{Digest as _, Sha1};
use sha2::Sha256;

const COPIER_HEADER_SIZE: usize = 512;

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Region {
    offset: usize,
    expected_hex: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Write {
    offset: usize,
    expected_hex: String,
    replacement_hex: String,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SourceCopyOperation {
    #[serde(default)]
    source_offset: Option<usize>,
    #[serde(default)]
    length: Option<usize>,
    #[serde(default)]
    xor_b64: Option<String>,
    #[serde(default)]
    xor_zlib_b64: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct SourceCopyPatch {
    encoding: String,
    output_size: usize,
    literal_bytes: usize,
    operations: Vec<SourceCopyOperation>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct LevelCapSite {
    id: String,
    offset: usize,
    default: u8,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct OverflowPercentSite {
    offset: usize,
    default: u8,
    minimum: u8,
    maximum: u8,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DebugFlagsSite {
    offset: usize,
    default: u8,
    flags: BTreeMap<String, u8>,
}

#[derive(Debug, Default, Deserialize)]
#[serde(default, deny_unknown_fields)]
pub struct Configurable {
    level_caps: Vec<LevelCapSite>,
    overflow_percent: Option<OverflowPercentSite>,
    debug_flags: Option<DebugFlagsSite>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Recipe {
    schema: u8,
    id: String,
    game: String,
    accepted_sha1: Vec<String>,
    #[serde(default)]
    allow_modified_input: bool,
    fingerprints: Vec<Region>,
    #[serde(default)]
    writes: Vec<Write>,
    #[serde(default)]
    source_copy: Option<SourceCopyPatch>,
    #[serde(default)]
    configurable: Configurable,
    #[serde(default)]
    canonical_output_sha256: Option<String>,
}

impl Recipe {
    pub fn id(&self) -> &str {
        &self.id
    }
}

#[derive(Debug, Clone, Default, Deserialize, Serialize, PartialEq, Eq)]
#[serde(default, deny_unknown_fields)]
pub struct DebugOptions {
    pub infinite_health: bool,
    pub maximum_damage: bool,
    pub disable_trainer_sight: bool,
}

impl DebugOptions {
    fn mask(&self) -> u8 {
        u8::from(self.infinite_health)
            | (u8::from(self.maximum_damage) << 1)
            | (u8::from(self.disable_trainer_sight) << 2)
    }
}

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct UserConfig {
    pub schema: u8,
    pub game: String,
    #[serde(default)]
    pub level_caps: BTreeMap<String, u8>,
    #[serde(default)]
    pub overflow_percent: Option<u8>,
    #[serde(default)]
    pub debug: DebugOptions,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PatchReport {
    pub recipe: String,
    pub game: String,
    pub input_sha1: String,
    pub input_kind: String,
    pub input_normalization: String,
    pub output_sha256: String,
    pub writes: usize,
    pub level_cap_overrides: BTreeMap<String, u8>,
    pub overflow_percent: Option<u8>,
    pub debug: DebugOptions,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InspectResult {
    pub size: usize,
    pub sha1: String,
    pub sha256: String,
}

#[derive(Debug)]
pub struct PatchResult {
    pub bytes: Vec<u8>,
    pub report: PatchReport,
}

fn digest_sha1(data: &[u8]) -> String {
    format!("{:x}", Sha1::digest(data))
}

fn digest_sha256(data: &[u8]) -> String {
    format!("{:x}", Sha256::digest(data))
}

pub fn inspect(data: &[u8]) -> InspectResult {
    InspectResult {
        size: data.len(),
        sha1: digest_sha1(data),
        sha256: digest_sha256(data),
    }
}

fn parse_hex(value: &str, field: &str) -> Result<Vec<u8>, String> {
    if value.len() % 2 != 0 {
        return Err(format!("{field} must be an even-length hexadecimal string"));
    }
    let mut output = Vec::with_capacity(value.len() / 2);
    for index in (0..value.len()).step_by(2) {
        let byte = u8::from_str_radix(&value[index..index + 2], 16)
            .map_err(|_| format!("{field} is not valid hexadecimal"))?;
        output.push(byte);
    }
    Ok(output)
}

fn validate_hash(value: &str, digits: usize, field: &str) -> Result<(), String> {
    if value.len() != digits || !value.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(format!(
            "{field} must be a {digits}-digit hexadecimal string"
        ));
    }
    Ok(())
}

fn check_region(
    data: &[u8],
    offset: usize,
    expected_hex: &str,
    label: &str,
) -> Result<usize, String> {
    let expected = parse_hex(expected_hex, &format!("{label}.expected_hex"))?;
    let end = offset
        .checked_add(expected.len())
        .ok_or_else(|| format!("{label} offset overflows"))?;
    if end > data.len() {
        return Err(format!("{label} extends beyond the input"));
    }
    if data[offset..end] != expected {
        let actual = data[offset..end]
            .iter()
            .map(|byte| format!("{byte:02x}"))
            .collect::<String>();
        return Err(format!(
            "{label} mismatch at 0x{offset:x}: expected {}, got {actual}",
            expected_hex.to_ascii_lowercase()
        ));
    }
    Ok(end)
}

fn apply_source_copy(original: &[u8], patch: &SourceCopyPatch) -> Result<Vec<u8>, String> {
    if patch.output_size != original.len() {
        return Err("source_copy must preserve the input size".into());
    }
    let mut output = Vec::with_capacity(patch.output_size);
    let mut transformed = 0_usize;
    for (index, operation) in patch.operations.iter().enumerate() {
        let label = format!("source_copy.operations[{index}]");
        match (
            operation.source_offset,
            operation.length,
            operation.xor_b64.as_deref(),
            operation.xor_zlib_b64.as_deref(),
        ) {
            (Some(offset), Some(length), None, None) if length > 0 => {
                let end = offset
                    .checked_add(length)
                    .ok_or_else(|| format!("{label} source range overflows"))?;
                let source = original
                    .get(offset..end)
                    .ok_or_else(|| format!("{label} source range exceeds input"))?;
                output.extend_from_slice(source);
            }
            (None, None, Some(encoded), None) => {
                let delta = BASE64
                    .decode(encoded)
                    .map_err(|error| format!("{label}.xor_b64 is invalid: {error}"))?;
                let start = output.len();
                let end = start
                    .checked_add(delta.len())
                    .ok_or_else(|| format!("{label} range overflows"))?;
                let source = original
                    .get(start..end)
                    .ok_or_else(|| format!("{label} extends beyond input"))?;
                output.extend(
                    source
                        .iter()
                        .zip(&delta)
                        .map(|(value, change)| value ^ change),
                );
                transformed += delta.len();
            }
            (None, Some(length), None, Some(encoded)) => {
                let compressed = BASE64
                    .decode(encoded)
                    .map_err(|error| format!("{label}.xor_zlib_b64 is invalid: {error}"))?;
                let mut decoder = ZlibDecoder::new(compressed.as_slice());
                let mut delta = Vec::new();
                decoder
                    .read_to_end(&mut delta)
                    .map_err(|error| format!("{label}.xor_zlib_b64 is invalid: {error}"))?;
                if delta.len() != length {
                    return Err(format!("{label} expands to the wrong length"));
                }
                let start = output.len();
                let end = start
                    .checked_add(delta.len())
                    .ok_or_else(|| format!("{label} range overflows"))?;
                let source = original
                    .get(start..end)
                    .ok_or_else(|| format!("{label} extends beyond input"))?;
                output.extend(
                    source
                        .iter()
                        .zip(&delta)
                        .map(|(value, change)| value ^ change),
                );
                transformed += delta.len();
            }
            _ => return Err(format!("{label} has an unsupported operation shape")),
        }
        if output.len() > patch.output_size {
            return Err("source_copy exceeds its declared output size".into());
        }
    }
    if output.len() != patch.output_size {
        return Err("source_copy does not fill its declared output size".into());
    }
    if transformed != patch.literal_bytes {
        return Err("source_copy transformed-byte count does not match its declaration".into());
    }
    Ok(output)
}

fn repair_cartridge_checksum(output: &mut [u8], game: &str) {
    if !matches!(game, "red" | "blue" | "yellow" | "crystal") || output.len() < 0x150 {
        return;
    }
    let checksum = output[..0x14e]
        .iter()
        .chain(&output[0x150..])
        .fold(0_u16, |sum, byte| sum.wrapping_add(u16::from(*byte)));
    output[0x14e..0x150].copy_from_slice(&checksum.to_be_bytes());
}

pub fn parse_recipe(json: &str) -> Result<Recipe, String> {
    let recipe: Recipe =
        serde_json::from_str(json).map_err(|error| format!("invalid recipe: {error}"))?;
    if recipe.schema != 1 {
        return Err("recipe must use schema 1".into());
    }
    if recipe.id.is_empty() || recipe.game.is_empty() {
        return Err("recipe id and game must be non-empty".into());
    }
    if recipe.accepted_sha1.is_empty() {
        return Err("accepted_sha1 must not be empty".into());
    }
    for (index, hash) in recipe.accepted_sha1.iter().enumerate() {
        validate_hash(hash, 40, &format!("accepted_sha1[{index}]"))?;
    }
    if recipe.writes.is_empty() && recipe.source_copy.is_none() {
        return Err("recipe must contain writes or source_copy".into());
    }
    if !recipe.writes.is_empty() && recipe.source_copy.is_some() {
        return Err("recipe cannot combine writes and source_copy".into());
    }
    if let Some(patch) = &recipe.source_copy {
        if patch.encoding != "source-copy-v1" {
            return Err("source_copy encoding must be source-copy-v1".into());
        }
        if patch.operations.is_empty() {
            return Err("source_copy.operations must not be empty".into());
        }
    }
    if recipe.allow_modified_input && recipe.fingerprints.is_empty() {
        return Err("modified-input mode requires at least one invariant fingerprint".into());
    }
    if let Some(hash) = &recipe.canonical_output_sha256 {
        validate_hash(hash, 64, "canonical_output_sha256")?;
    }

    let mut cap_ids = BTreeSet::new();
    let mut configurable_offsets = BTreeSet::new();
    for site in &recipe.configurable.level_caps {
        if site.id.is_empty() || !cap_ids.insert(site.id.as_str()) {
            return Err(format!(
                "invalid or duplicate configurable cap id {}",
                site.id
            ));
        }
        if !(1..=100).contains(&site.default) {
            return Err(format!(
                "configurable cap {} default must be 1 through 100",
                site.id
            ));
        }
        if !configurable_offsets.insert(site.offset) {
            return Err(format!("duplicate configurable offset 0x{:x}", site.offset));
        }
    }
    if let Some(site) = &recipe.configurable.overflow_percent {
        if !configurable_offsets.insert(site.offset) {
            return Err(format!("duplicate configurable offset 0x{:x}", site.offset));
        }
        if site.minimum != 0 || site.maximum != 100 {
            return Err("overflow percent range must be 0 through 100".into());
        }
        if !(site.minimum..=site.maximum).contains(&site.default) {
            return Err("overflow percent default must be 0 through 100".into());
        }
    }
    if let Some(site) = &recipe.configurable.debug_flags {
        if !configurable_offsets.insert(site.offset) {
            return Err(format!("duplicate configurable offset 0x{:x}", site.offset));
        }
        let expected = BTreeMap::from([
            ("disable_trainer_sight".to_string(), 4),
            ("infinite_health".to_string(), 1),
            ("maximum_damage".to_string(), 2),
        ]);
        if site.default != 0 || site.flags != expected {
            return Err("debug flags must declare the supported flags with default 0".into());
        }
    }
    Ok(recipe)
}

pub fn parse_config(json: &str) -> Result<UserConfig, String> {
    let config: UserConfig =
        serde_json::from_str(json).map_err(|error| format!("invalid config: {error}"))?;
    if config.schema != 1 {
        return Err("config must use schema 1".into());
    }
    if config.game.is_empty() {
        return Err("config game must be non-empty".into());
    }
    for (id, level) in &config.level_caps {
        if id.is_empty() || !(1..=100).contains(level) {
            return Err(format!(
                "config level_caps.{id} must be an integer from 1 through 100"
            ));
        }
    }
    if config.overflow_percent.is_some_and(|value| value > 100) {
        return Err("config overflow_percent must be an integer from 0 through 100".into());
    }
    Ok(config)
}

pub fn apply(
    recipe: &Recipe,
    config: Option<&UserConfig>,
    supplied: &[u8],
) -> Result<PatchResult, String> {
    if let Some(config) = config
        && config.game != recipe.game
    {
        return Err(format!("config game must be {:?}", recipe.game));
    }
    let cap_overrides = config.map(|value| &value.level_caps);
    let declared_caps = recipe
        .configurable
        .level_caps
        .iter()
        .map(|site| (site.id.as_str(), site))
        .collect::<BTreeMap<_, _>>();
    if let Some(overrides) = cap_overrides {
        let unknown = overrides
            .keys()
            .filter(|id| !declared_caps.contains_key(id.as_str()))
            .cloned()
            .collect::<Vec<_>>();
        if !unknown.is_empty() {
            return Err(format!(
                "config contains caps not declared by this recipe: {}",
                unknown.join(", ")
            ));
        }
    }
    if config.and_then(|value| value.overflow_percent).is_some()
        && recipe.configurable.overflow_percent.is_none()
    {
        return Err("config contains overflow_percent but this recipe does not declare it".into());
    }
    if config.is_some_and(|value| value.debug.mask() != 0)
        && recipe.configurable.debug_flags.is_none()
    {
        return Err("config enables debug toggles but this recipe does not declare them".into());
    }

    let supported = |data: &[u8]| {
        let sha1 = digest_sha1(data);
        recipe
            .accepted_sha1
            .iter()
            .any(|hash| hash.eq_ignore_ascii_case(&sha1))
            || (recipe.allow_modified_input
                && !recipe.fingerprints.is_empty()
                && recipe
                    .fingerprints
                    .iter()
                    .enumerate()
                    .all(|(index, region)| {
                        check_region(
                            data,
                            region.offset,
                            &region.expected_hex,
                            &format!("fingerprints[{index}]"),
                        )
                        .is_ok()
                    }))
    };
    let (original, input_normalization) = if supported(supplied) {
        (supplied, "none")
    } else if supplied.len() > COPIER_HEADER_SIZE && supported(&supplied[COPIER_HEADER_SIZE..]) {
        (
            &supplied[COPIER_HEADER_SIZE..],
            "removed-512-byte-copier-header",
        )
    } else {
        (supplied, "none")
    };

    let input_sha1 = digest_sha1(original);
    let canonical = recipe
        .accepted_sha1
        .iter()
        .any(|hash| hash.eq_ignore_ascii_case(&input_sha1));
    if !canonical && !recipe.allow_modified_input {
        return Err(format!("unsupported input SHA-1: {input_sha1}"));
    }
    for (index, region) in recipe.fingerprints.iter().enumerate() {
        check_region(
            original,
            region.offset,
            &region.expected_hex,
            &format!("fingerprints[{index}]"),
        )?;
    }

    let mut output = if let Some(patch) = &recipe.source_copy {
        apply_source_copy(original, patch)?
    } else {
        original.to_vec()
    };
    let mut occupied = Vec::<(usize, usize)>::new();
    for (index, write) in recipe.writes.iter().enumerate() {
        let label = format!("writes[{index}]");
        let end = check_region(original, write.offset, &write.expected_hex, &label)?;
        let replacement = parse_hex(&write.replacement_hex, &format!("{label}.replacement_hex"))?;
        if replacement.len() != end - write.offset {
            return Err(format!("{label} changes file length"));
        }
        if occupied
            .iter()
            .any(|(prior_start, prior_end)| write.offset < *prior_end && *prior_start < end)
        {
            return Err(format!("{label} overlaps another write"));
        }
        occupied.push((write.offset, end));
        output[write.offset..end].copy_from_slice(&replacement);
    }

    let mut effective_cap_overrides = BTreeMap::new();
    for site in &recipe.configurable.level_caps {
        let generated = output
            .get_mut(site.offset)
            .ok_or_else(|| format!("configurable cap {} extends beyond the output", site.id))?;
        if *generated != site.default {
            return Err(format!(
                "configurable cap {} expected generated default {} at 0x{:x}, got {}",
                site.id, site.default, site.offset, *generated
            ));
        }
        let selected = cap_overrides
            .and_then(|overrides| overrides.get(&site.id))
            .copied()
            .unwrap_or(site.default);
        *generated = selected;
        if selected != site.default {
            effective_cap_overrides.insert(site.id.clone(), selected);
        }
    }

    let mut overflow_percent = None;
    let mut overflow_percent_changed = false;
    if let Some(site) = &recipe.configurable.overflow_percent {
        let generated = output
            .get_mut(site.offset)
            .ok_or_else(|| "configurable overflow percent extends beyond the output".to_string())?;
        if *generated != site.default {
            return Err(format!(
                "configurable overflow percent expected generated default {} at 0x{:x}, got {}",
                site.default, site.offset, *generated
            ));
        }
        let selected = config
            .and_then(|value| value.overflow_percent)
            .unwrap_or(site.default);
        *generated = selected;
        overflow_percent_changed = selected != site.default;
        overflow_percent = Some(selected);
    }

    let debug = config.map(|value| value.debug.clone()).unwrap_or_default();
    let debug_mask = debug.mask();
    let mut debug_flags_changed = false;
    if let Some(site) = &recipe.configurable.debug_flags {
        let generated = output
            .get_mut(site.offset)
            .ok_or_else(|| "configurable debug flags extend beyond the output".to_string())?;
        if *generated != site.default {
            return Err(format!(
                "configurable debug flags expected generated default {} at 0x{:x}, got {}",
                site.default, site.offset, *generated
            ));
        }
        *generated = debug_mask;
        debug_flags_changed = debug_mask != site.default;
    }

    repair_cartridge_checksum(&mut output, &recipe.game);

    let output_sha256 = digest_sha256(&output);
    if canonical
        && effective_cap_overrides.is_empty()
        && !overflow_percent_changed
        && !debug_flags_changed
        && let Some(expected) = &recipe.canonical_output_sha256
        && !expected.eq_ignore_ascii_case(&output_sha256)
    {
        return Err(format!(
            "canonical output verification failed: expected {expected}, got {output_sha256}"
        ));
    }

    Ok(PatchResult {
        bytes: output,
        report: PatchReport {
            recipe: recipe.id.clone(),
            game: recipe.game.clone(),
            input_sha1,
            input_kind: if canonical {
                "canonical"
            } else {
                "compatible-modified"
            }
            .into(),
            input_normalization: input_normalization.into(),
            output_sha256,
            writes: recipe
                .source_copy
                .as_ref()
                .map_or(recipe.writes.len(), |patch| patch.operations.len()),
            level_cap_overrides: effective_cap_overrides,
            overflow_percent,
            debug,
        },
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> (Vec<u8>, String) {
        let mut data = (0_u8..64).collect::<Vec<_>>();
        data[22] = 0;
        data[23] = 75;
        let recipe = serde_json::json!({
            "schema": 1,
            "id": "test-red-1",
            "game": "red",
            "accepted_sha1": [digest_sha1(&data)],
            "allow_modified_input": true,
            "fingerprints": [{"offset": 0, "expected_hex": "00010203"}],
            "writes": [{
                "offset": 16,
                "expected_hex": "10111213",
                "replacement_hex": "a0a1a2a3"
            }],
            "configurable": {
                "level_caps": [
                    {"id": "brock", "offset": 20, "default": 20},
                    {"id": "misty", "offset": 21, "default": 21}
                ],
                "overflow_percent": {
                    "offset": 23, "default": 75, "minimum": 0, "maximum": 100
                },
                "debug_flags": {
                    "offset": 22,
                    "default": 0,
                    "flags": {
                        "infinite_health": 1,
                        "maximum_damage": 2,
                        "disable_trainer_sight": 4
                    }
                }
            }
        });
        (data, recipe.to_string())
    }

    #[test]
    fn patches_caps_and_overflow_without_touching_other_bytes() {
        let (data, recipe_json) = fixture();
        let recipe = parse_recipe(&recipe_json).unwrap();
        let config = parse_config(
            r#"{
            "schema":1,"game":"red",
            "level_caps":{"brock":13,"misty":20},"overflow_percent":50,
            "debug":{"infinite_health":true,"maximum_damage":false,"disable_trainer_sight":true}
        }"#,
        )
        .unwrap();
        let result = apply(&recipe, Some(&config), &data).unwrap();
        let mut expected = data;
        expected[16..20].copy_from_slice(&[0xa0, 0xa1, 0xa2, 0xa3]);
        expected[20] = 13;
        expected[21] = 20;
        expected[22] = 5;
        expected[23] = 50;
        assert_eq!(result.bytes, expected);
        assert_eq!(result.report.overflow_percent, Some(50));
        assert_eq!(result.report.debug.mask(), 5);
        assert_eq!(result.report.input_normalization, "none");
    }

    #[test]
    fn removes_validated_512_byte_copier_header() {
        let (data, recipe_json) = fixture();
        let recipe = parse_recipe(&recipe_json).unwrap();
        let mut supplied = vec![0xa5; COPIER_HEADER_SIZE];
        supplied.extend_from_slice(&data);
        let result = apply(&recipe, None, &supplied).unwrap();
        let mut expected = data;
        expected[16..20].copy_from_slice(&[0xa0, 0xa1, 0xa2, 0xa3]);
        assert_eq!(result.bytes, expected);
        assert_eq!(
            result.report.input_normalization,
            "removed-512-byte-copier-header"
        );
        assert_eq!(result.report.input_kind, "canonical");
    }

    #[test]
    fn does_not_strip_arbitrary_unsupported_prefix() {
        let (mut data, recipe_json) = fixture();
        let recipe = parse_recipe(&recipe_json).unwrap();
        data.reverse();
        let mut supplied = vec![0; COPIER_HEADER_SIZE];
        supplied.extend_from_slice(&data);
        assert!(apply(&recipe, None, &supplied).is_err());
    }

    #[test]
    fn rejects_modified_write_sites() {
        let (mut data, recipe_json) = fixture();
        let recipe = parse_recipe(&recipe_json).unwrap();
        data[16] = 0xff;
        assert!(
            apply(&recipe, None, &data)
                .unwrap_err()
                .contains("writes[0] mismatch")
        );
    }

    #[test]
    fn rejects_unknown_config_fields() {
        assert!(parse_config(r#"{"schema":1,"game":"red","wipe_mode":"soft"}"#).is_err());
        assert!(parse_config(r#"{"schema":1,"game":"red","surprise":true}"#).is_err());
    }

    #[test]
    fn source_copy_relocates_and_xors_without_target_literals() {
        let (data, recipe_json) = fixture();
        let mut value: serde_json::Value = serde_json::from_str(&recipe_json).unwrap();
        let delta = data[16..20]
            .iter()
            .zip(b"QLCK")
            .map(|(source, target)| source ^ target)
            .collect::<Vec<_>>();
        value["writes"] = serde_json::json!([]);
        value["source_copy"] = serde_json::json!({
            "encoding": "source-copy-v1",
            "output_size": data.len(),
            "literal_bytes": delta.len(),
            "operations": [
                {"source_offset": 0, "length": 16},
                {"xor_b64": BASE64.encode(delta)},
                {"source_offset": 20, "length": data.len() - 20}
            ]
        });
        let recipe = parse_recipe(&value.to_string()).unwrap();
        let result = apply(&recipe, None, &data).unwrap();
        let mut expected = data;
        expected[16..20].copy_from_slice(b"QLCK");
        assert_eq!(result.bytes, expected);
    }

    #[test]
    fn repairs_game_boy_global_checksum() {
        let mut output = (0_u16..0x200).map(|value| value as u8).collect::<Vec<_>>();
        output[0x14e..0x150].fill(0);
        let expected = output[..0x14e]
            .iter()
            .chain(&output[0x150..])
            .fold(0_u16, |sum, byte| sum.wrapping_add(u16::from(*byte)));
        repair_cartridge_checksum(&mut output, "crystal");
        assert_eq!(&output[0x14e..0x150], &expected.to_be_bytes());
    }
}
