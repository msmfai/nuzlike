# Default level-cap research audit

Retrieved 2026-08-03. This audit covers NuzLike's supported pre-League games,
Red/Blue through Emerald and FireRed/LeafGreen.

## Method

NuzLike does not derive its patcher defaults from ROM trainer parties. A
value is a default when it appears in both comprehensive community tables below.
Game-specific Nuzlocke Tracker guides provide a third community source for Gym
caps and adjudicate disagreements.

- **NU:** [Nuzlocke University — Hardcore Nuzlocke Level Caps by Generation](https://nuzlockeuniversity.ca/2022/01/18/hardcore-nuzlocke-level-caps-by-generation/)
- **RN:** [r/nuzlocke — Level limits](https://www.reddit.com/r/nuzlocke/comments/8cejlk/level_limits/)
- **NT:** [Nuzlocke Tracker game guides](https://nuzlocketracker.org/guides)

These are community conventions, not official rules. Patcher fields remain
editable. Agreement in this audit means agreement between published community
tables; it does not mean every player uses the same house rules.

These researched values are the patcher's **Medium** preset. No comparable
community-wide Easy/Medium/Hard convention was found. NuzLike therefore
labels Easy and Hard as project-authored balance presets and stores their full
tables in `presets/level_caps.json`; it does not present those values as sourced
consensus or derive them with a fixed addition or subtraction.

## Adopted defaults

The values are listed in progression order as `Gym caps | Elite Four caps |
Champion cap`.

| Games | Community-consensus defaults | Sources |
|---|---|---|
| Red / Blue | `14, 21, 24, 29, 43, 43, 47, 50 | 56, 58, 60, 62 | 65` | NU, RN, [NT Red](https://nuzlocketracker.org/guides/red) |
| Yellow | `12, 21, 28, 32, 50, 50, 54, 55 | 56, 58, 60, 62 | 65` | NU, RN, [NT Yellow](https://nuzlocketracker.org/guides/yellow) |
| Crystal | `9, 16, 20, 25, 30, 31, 35, 40 | 42, 44, 46, 47 | 50` | NU, RN with adjudication, [NT Crystal](https://nuzlocketracker.org/guides/crystal) |
| Emerald | `15, 19, 24, 29, 31, 33, 42, 46 | 49, 51, 53, 55 | 58` | NU, RN, [NT Emerald](https://nuzlocketracker.org/guides/emerald) |
| FireRed / LeafGreen | `14, 21, 24, 29, 43, 43, 47, 50 | 54, 56, 58, 60 | 63` | NU, RN, [NT FireRed](https://nuzlocketracker.org/guides/fire-red) |

Red/Blue and FireRed/LeafGreen inherit paired tables because the cited sources
group them and the relevant boss levels are the same.

## Ambiguous and exceptional cases

### Yellow Lt. Surge

All three cap sources list level 28. Surge has only one Pokémon, a level-28
Raichu, which makes this a legitimate balance concern for NuzLike's full-party
training. However, the evidence found for level 26 was an individual player
voluntarily entering at 26, not a shared cap convention. The default is therefore
28. Players who want the stricter interpretation can set 26 in the patcher.

### Crystal Bugsy

RN lists level 15, while NU and NT list level 16. NuzLike uses 16, the value
supported by two of the three community sources.

### Johto mid-game order

The published cap values are Chuck 30, Jasmine 35, and Pryce 31. Community
discussion repeatedly recommends `Chuck -> Pryce -> Jasmine` to keep a monotonic
level curve. NuzLike adopts that order but does not change any of the three
community cap values:

- [r/nuzlocke discussion: level-cap ordering](https://www.reddit.com/r/nuzlocke/comments/8cejlk/level_limits/)
- [PokéBase community answer: Chuck, Pryce, Jasmine](https://pokemondb.net/pokebase/394167/which-gym-to-fight-after-morty-in-crystal-hardcore-nuzlocke)
- [r/nuzlocke discussion: Crystal level-cap order](https://www.reddit.com/r/nuzlocke/comments/z8je0t/question_about_crystal_level_cap_on_gyms/)

### Pokémon League handling

Community rules differ on whether the League uses one entry cap or separate
Elite Four and Champion milestones. NU and RN publish separate values for these
games. NuzLike keeps those separately configurable because its runtime can
advance the cap after each victory; no value is inferred from the current party.
