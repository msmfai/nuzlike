// Copyright (C) 2026 NuzLike contributors
// SPDX-License-Identifier: GPL-3.0-or-later
//! Dependency-free Emerald piecewise experience generator.

pub const LEVEL_COUNT: usize = 101;
pub const GROWTH_GROUPS: usize = 8;
pub const TABLE_BYTES: usize = GROWTH_GROUPS * LEVEL_COUNT * 4;
const QUOTAS: [u32; 9] = [1, 2, 3, 4, 5, 6, 6, 6, 6];

pub fn read_tables(data: &[u8], offset: usize) -> Result<Vec<Vec<u32>>, String> {
    let bytes = data
        .get(offset..offset + TABLE_BYTES)
        .ok_or_else(|| "Emerald vanilla experience tables extend beyond the input".to_string())?;
    let mut tables = vec![vec![0_u32; LEVEL_COUNT]; GROWTH_GROUPS];
    for (index, chunk) in bytes.chunks_exact(4).enumerate() {
        tables[index / LEVEL_COUNT][index % LEVEL_COUNT] =
            u32::from_le_bytes(chunk.try_into().unwrap());
    }
    Ok(tables)
}

pub fn generate(
    vanilla: &[Vec<u32>],
    caps: &[u8; 9],
    budgets: &[u32],
    family_growth_groups: &[Vec<u8>],
) -> Result<Vec<u8>, String> {
    if vanilla.len() != GROWTH_GROUPS
        || vanilla.iter().any(|table| table.len() != LEVEL_COUNT)
        || budgets.len() != 9
        || family_growth_groups.len() != 9
    {
        return Err("Emerald curve inputs have invalid dimensions".into());
    }
    let mut output = vec![vec![0_u32; LEVEL_COUNT]; GROWTH_GROUPS];
    for growth in 0..GROWTH_GROUPS {
        output[growth][..6].copy_from_slice(&vanilla[growth][..6]);
    }
    let mut floor = 5_usize;
    for chapter in 0..9 {
        let cap = usize::from(caps[chapter]);
        if cap < floor || cap >= 100 {
            return Err(format!(
                "chapter {} cap must be from {floor} through 99",
                chapter + 1
            ));
        }
        let groups = &family_growth_groups[chapter];
        if groups.is_empty()
            || groups
                .iter()
                .any(|group| usize::from(*group) >= GROWTH_GROUPS)
        {
            return Err(format!("chapter {} family groups are invalid", chapter + 1));
        }
        let base_cost_sum = groups.iter().try_fold(0_u128, |sum, group| {
            let table = &vanilla[usize::from(*group)];
            sum.checked_add(u128::from(table[cap] - table[floor]))
                .ok_or_else(|| "Emerald family cost overflow".to_string())
        })?;
        let budget = u128::from(budgets[chapter]);
        let (scale_num, scale_den) = if cap == floor || base_cost_sum == 0 || budget == 0 {
            (1_u128, 1_u128)
        } else {
            (
                budget * groups.len() as u128,
                u128::from(QUOTAS[chapter]) * base_cost_sum,
            )
        };
        for growth in 0..GROWTH_GROUPS {
            for level in floor + 1..=cap {
                let delta = u128::from(vanilla[growth][level] - vanilla[growth][level - 1]);
                let scaled = (delta * scale_num * 2 + scale_den) / (scale_den * 2);
                let scaled = u32::try_from(scaled.max(1))
                    .map_err(|_| "generated Emerald experience delta overflows u32")?;
                output[growth][level] =
                    output[growth][level - 1]
                        .checked_add(scaled)
                        .ok_or_else(|| {
                            "generated Emerald experience threshold overflows u32".to_string()
                        })?;
            }
        }
        floor = cap;
    }
    let champion_cap = usize::from(caps[8]);
    for growth in 0..GROWTH_GROUPS {
        for level in champion_cap + 1..LEVEL_COUNT {
            let delta = vanilla[growth][level] - vanilla[growth][level - 1];
            output[growth][level] = output[growth][level - 1]
                .checked_add(delta)
                .ok_or_else(|| "post-Champion Emerald threshold overflows u32".to_string())?;
        }
    }
    Ok(output
        .into_iter()
        .flatten()
        .flat_map(u32::to_le_bytes)
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preserves_vanilla_deltas_after_champion_cap() {
        let vanilla = (1_u32..=8)
            .map(|growth| (0_u32..=100).map(|level| growth * level.pow(3)).collect())
            .collect::<Vec<Vec<u32>>>();
        let caps = [15, 19, 24, 29, 31, 33, 42, 46, 58];
        let groups = vec![vec![0, 1, 2, 3, 4, 5]; 9];
        let bytes = generate(&vanilla, &caps, &[10_000; 9], &groups).unwrap();
        let tables = read_tables(&bytes, 0).unwrap();
        assert_eq!(
            tables[3][59] - tables[3][58],
            vanilla[3][59] - vanilla[3][58]
        );
        assert_ne!(tables[3][15], vanilla[3][15]);
    }
}
