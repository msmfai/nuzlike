// Copyright (C) 2026 Quicklocke contributors
// SPDX-License-Identifier: GPL-3.0-or-later
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::Serialize;

#[derive(Debug)]
pub struct FvxOutput {
    pub randomized: Vec<u8>,
    pub manifest_json: String,
    pub log: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FvxResponseMetadata<'a> {
    pub manifest_json: &'a str,
    pub log: &'a str,
}

fn bundled_path(resource_dir: &Path, relative: &str) -> PathBuf {
    resource_dir.join(relative)
}

fn engine_paths(resource_dir: &Path) -> (PathBuf, PathBuf) {
    let java = std::env::var_os("QUICKLOCKE_JAVA")
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            bundled_path(
                resource_dir,
                if cfg!(target_os = "windows") {
                    "runtime/bin/java.exe"
                } else {
                    "runtime/bin/java"
                },
            )
        });
    let jar = std::env::var_os("QUICKLOCKE_FVX_JAR")
        .map(PathBuf::from)
        .unwrap_or_else(|| bundled_path(resource_dir, "engines/UPR-FVX.jar"));
    (java, jar)
}

#[cfg(not(target_os = "android"))]
pub fn randomize(
    resource_dir: &Path,
    clean_rom: &[u8],
    settings: &str,
    seed: i64,
) -> Result<FvxOutput, String> {
    if settings.is_empty() {
        return Err("FVX settings string must not be empty".into());
    }
    let (java, jar) = engine_paths(resource_dir);
    if !java.is_file() {
        return Err(format!(
            "bundled Java runtime is missing at {}; reinstall this Quicklocke build",
            java.display()
        ));
    }
    if !jar.is_file() {
        return Err(format!(
            "bundled FVX engine is missing at {}; reinstall this Quicklocke build",
            jar.display()
        ));
    }
    let workspace = tempfile::Builder::new()
        .prefix("quicklocke-fvx-")
        .tempdir()
        .map_err(|error| format!("cannot create private FVX workspace: {error}"))?;
    let input = workspace.path().join("clean.rom");
    let randomized = workspace.path().join("randomized.rom");
    let manifest = workspace.path().join("manifest.json");
    let log = workspace.path().join("randomizer.log");
    std::fs::write(&input, clean_rom)
        .map_err(|error| format!("cannot stage input for FVX: {error}"))?;

    let output = Command::new(&java)
        .arg("-jar")
        .arg(&jar)
        .arg("quicklocke")
        .arg("-i")
        .arg(&input)
        .arg("-o")
        .arg(&randomized)
        .arg("-S")
        .arg(settings)
        .arg("-z")
        .arg(seed.to_string())
        .arg("--manifest")
        .arg(&manifest)
        .arg("--log")
        .arg(&log)
        .output()
        .map_err(|error| format!("cannot start bundled FVX engine: {error}"))?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(if stderr.is_empty() {
            format!("FVX exited with status {}", output.status)
        } else {
            format!("FVX failed: {stderr}")
        });
    }
    let randomized = std::fs::read(randomized)
        .map_err(|error| format!("FVX did not produce a readable randomized ROM: {error}"))?;
    let manifest_json = std::fs::read_to_string(manifest)
        .map_err(|error| format!("FVX did not produce a readable manifest: {error}"))?;
    let log = std::fs::read_to_string(log)
        .map_err(|error| format!("FVX did not produce a readable log: {error}"))?;
    Ok(FvxOutput {
        randomized,
        manifest_json,
        log,
    })
}

#[cfg(target_os = "android")]
pub fn randomize(
    _resource_dir: &Path,
    _clean_rom: &[u8],
    _settings: &str,
    _seed: i64,
) -> Result<FvxOutput, String> {
    Err("the FVX Android in-process adapter is not installed in this build".into())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bundled_engine_layout_is_stable() {
        let root = Path::new("/resources");
        let (java, jar) = engine_paths(root);
        if std::env::var_os("QUICKLOCKE_JAVA").is_none() {
            assert!(java.ends_with(if cfg!(target_os = "windows") {
                "runtime/bin/java.exe"
            } else {
                "runtime/bin/java"
            }));
        }
        if std::env::var_os("QUICKLOCKE_FVX_JAR").is_none() {
            assert!(jar.ends_with("engines/UPR-FVX.jar"));
        }
    }
}
