// Copyright (C) 2026 NuzLike contributors
// SPDX-License-Identifier: GPL-3.0-or-later
//! Linker-light parity probe for the dependency-free Emerald curve generator.

#[path = "../src-tauri/src/emerald_curve.rs"]
mod emerald_curve;

use std::{env, fs, io::Write};

fn numbers<T: std::str::FromStr>(value: &str) -> Result<Vec<T>, String> {
    value
        .split(',')
        .filter(|part| !part.is_empty())
        .map(|part| part.parse().map_err(|_| format!("invalid integer {part}")))
        .collect()
}

fn main() -> Result<(), String> {
    let args = env::args().collect::<Vec<_>>();
    if args.len() != 6 {
        return Err("usage: probe ROM VANILLA_OFFSET CAPS BUDGETS GROUPS".into());
    }
    let rom = fs::read(&args[1]).map_err(|error| error.to_string())?;
    let offset = args[2].parse::<usize>().map_err(|error| error.to_string())?;
    let cap_values = numbers::<u8>(&args[3])?;
    let caps: [u8; 9] = cap_values.try_into().map_err(|_| "nine caps required")?;
    let budgets = numbers::<u32>(&args[4])?;
    let groups = args[5]
        .split(';')
        .map(numbers::<u8>)
        .collect::<Result<Vec<_>, _>>()?;
    let vanilla = emerald_curve::read_tables(&rom, offset)?;
    let output = emerald_curve::generate(&vanilla, &caps, &budgets, &groups)?;
    std::io::stdout()
        .write_all(&output)
        .map_err(|error| error.to_string())?;
    Ok(())
}
