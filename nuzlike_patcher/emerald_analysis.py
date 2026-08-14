# Copyright (C) 2026 NuzLike contributors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Deterministic clean-ROM chapter analysis for Pokemon Emerald.

The topology template is generated from the pinned decomp, but mutable game
data is decoded from the ROM passed to :func:`analyse_emerald`.  This is the
reference implementation that the Rust patcher must match byte for byte.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable


ROM_ADDRESS = 0x08000000
SPECIES_RECORD_SIZE = 28
TRAINER_RECORD_SIZE = 40
EVOLUTION_RECORD_SIZE = 8
EVOLUTIONS_PER_SPECIES = 5
LEVEL_COUNT = 101
GROWTH_GROUP_COUNT = 8
QUOTAS = (1, 2, 3, 4, 5, 6, 6, 6, 6)


class EmeraldAnalysisError(ValueError):
    """The ROM or template cannot produce a trustworthy analysis."""


@dataclass(frozen=True)
class Species:
    id: int
    base_exp: int
    growth_group: int


@dataclass(frozen=True)
class TrainerMon:
    level: int
    species: int


@dataclass(frozen=True)
class Trainer:
    id: int
    party_flags: int
    party: tuple[TrainerMon, ...]


@dataclass(frozen=True)
class Evolution:
    source: int
    method: int
    parameter: int
    target: int


@dataclass(frozen=True)
class WildSlot:
    minimum_level: int
    maximum_level: int
    species: int


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _integer(value: Any, field: str, *, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise EmeraldAnalysisError(f"{field} must be an integer >= {minimum}")
    return value


def _slice(data: bytes, offset: int, size: int, field: str) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise EmeraldAnalysisError(f"{field} extends outside the ROM")
    return data[offset : offset + size]


def _u16(data: bytes, offset: int, field: str) -> int:
    return struct.unpack_from("<H", _slice(data, offset, 2, field))[0]


def _u32(data: bytes, offset: int, field: str) -> int:
    return struct.unpack_from("<I", _slice(data, offset, 4, field))[0]


def _pointer_offset(pointer: int, rom_size: int, field: str) -> int:
    if not ROM_ADDRESS <= pointer < ROM_ADDRESS + rom_size:
        raise EmeraldAnalysisError(f"{field} is not a ROM pointer: 0x{pointer:08x}")
    return pointer - ROM_ADDRESS


def load_emerald_template(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EmeraldAnalysisError(f"cannot read Emerald analysis template: {error}") from error
    if not isinstance(value, dict) or value.get("schema") != 1 or value.get("game") != "emerald":
        raise EmeraldAnalysisError("Emerald analysis template must use schema 1")
    for field in (
        "accepted_sha1",
        "regions",
        "species_names",
        "trainer_names",
        "topology",
        "acquisitions",
        "evolution_methods",
    ):
        if field not in value:
            raise EmeraldAnalysisError(f"Emerald analysis template is missing {field}")
    return value


def validate_emerald_rom(data: bytes, template: dict[str, Any]) -> None:
    sha1 = hashlib.sha1(data).hexdigest()
    accepted = template.get("accepted_sha1")
    if not isinstance(accepted, list) or sha1 not in accepted:
        raise EmeraldAnalysisError(f"unsupported Emerald ROM SHA-1 {sha1}")
    regions = template.get("regions")
    if not isinstance(regions, dict):
        raise EmeraldAnalysisError("regions must be an object")
    for name, region in sorted(regions.items()):
        if not isinstance(region, dict):
            raise EmeraldAnalysisError(f"regions.{name} must be an object")
        offset = _integer(region.get("offset"), f"regions.{name}.offset")
        size = _integer(region.get("size"), f"regions.{name}.size", minimum=1)
        expected = region.get("sha256")
        if not isinstance(expected, str) or len(expected) != 64:
            raise EmeraldAnalysisError(f"regions.{name}.sha256 must be a SHA-256 string")
        actual = _sha256(_slice(data, offset, size, f"regions.{name}"))
        if actual != expected:
            raise EmeraldAnalysisError(
                f"Emerald ROM region {name} changed: expected {expected}, got {actual}"
            )


def decode_species(data: bytes, template: dict[str, Any]) -> dict[int, Species]:
    region = template["regions"]["species"]
    offset = _integer(region["offset"], "regions.species.offset")
    names = template["species_names"]
    if not isinstance(names, list):
        raise EmeraldAnalysisError("species_names must be a list")
    result: dict[int, Species] = {}
    for species_id in range(len(names)):
        start = offset + species_id * SPECIES_RECORD_SIZE
        record = _slice(data, start, SPECIES_RECORD_SIZE, f"species[{species_id}]")
        growth = record[0x13]
        if growth >= GROWTH_GROUP_COUNT:
            raise EmeraldAnalysisError(f"species {species_id} has invalid growth group {growth}")
        result[species_id] = Species(species_id, record[0x09], growth)
    return result


_PARTY_LAYOUTS = {
    # The original ARM ABI rounds these party structs to four-byte alignment,
    # including the nominally six- and fourteen-byte C layouts.
    0: (8, 2, 4),
    1: (16, 2, 4),
    2: (8, 2, 4),
    3: (16, 2, 4),
}


def decode_trainers(data: bytes, template: dict[str, Any]) -> dict[int, Trainer]:
    region = template["regions"]["trainers"]
    offset = _integer(region["offset"], "regions.trainers.offset")
    names = template["trainer_names"]
    if not isinstance(names, list):
        raise EmeraldAnalysisError("trainer_names must be a list")
    result: dict[int, Trainer] = {}
    for trainer_id in range(len(names)):
        start = offset + trainer_id * TRAINER_RECORD_SIZE
        record = _slice(data, start, TRAINER_RECORD_SIZE, f"trainer[{trainer_id}]")
        flags = record[0]
        if flags not in _PARTY_LAYOUTS:
            raise EmeraldAnalysisError(f"trainer {trainer_id} has unsupported party flags {flags}")
        party_size = record[0x20]
        if party_size > 6:
            raise EmeraldAnalysisError(f"trainer {trainer_id} has invalid party size {party_size}")
        pointer = struct.unpack_from("<I", record, 0x24)[0]
        party: list[TrainerMon] = []
        if party_size:
            party_offset = _pointer_offset(pointer, len(data), f"trainer[{trainer_id}].party")
            stride, level_at, species_at = _PARTY_LAYOUTS[flags]
            for index in range(party_size):
                mon_offset = party_offset + index * stride
                level = _slice(data, mon_offset + level_at, 1, "trainer mon level")[0]
                species = _u16(data, mon_offset + species_at, "trainer mon species")
                party.append(TrainerMon(level, species))
        result[trainer_id] = Trainer(trainer_id, flags, tuple(party))
    return result


def decode_evolutions(data: bytes, template: dict[str, Any], species_count: int) -> list[Evolution]:
    region = template["regions"]["evolutions"]
    offset = _integer(region["offset"], "regions.evolutions.offset")
    result: list[Evolution] = []
    for source in range(species_count):
        for slot in range(EVOLUTIONS_PER_SPECIES):
            start = offset + (source * EVOLUTIONS_PER_SPECIES + slot) * EVOLUTION_RECORD_SIZE
            method, parameter, target = struct.unpack_from(
                "<HHH", _slice(data, start, EVOLUTION_RECORD_SIZE, "evolution")
            )
            if method and target:
                result.append(Evolution(source, method, parameter, target))
    return result


def decode_experience_tables(data: bytes, template: dict[str, Any]) -> list[list[int]]:
    region = template["regions"]["experience"]
    offset = _integer(region["offset"], "regions.experience.offset")
    tables = []
    for growth in range(GROWTH_GROUP_COUNT):
        start = offset + growth * LEVEL_COUNT * 4
        table = list(struct.unpack_from("<101I", data, start))
        if any(after <= before for before, after in zip(table[1:100], table[2:101])):
            raise EmeraldAnalysisError(f"growth table {growth} is not strictly increasing")
        tables.append(table)
    return tables


def _decode_wild_info(data: bytes, pointer: int, slots: int, field: str) -> tuple[WildSlot, ...]:
    if pointer == 0:
        return ()
    info = _pointer_offset(pointer, len(data), field)
    slot_pointer = _u32(data, info + 4, f"{field}.slots")
    slot_offset = _pointer_offset(slot_pointer, len(data), f"{field}.slots")
    values = []
    for index in range(slots):
        start = slot_offset + index * 4
        values.append(
            WildSlot(
                _slice(data, start, 1, field)[0],
                _slice(data, start + 1, 1, field)[0],
                _u16(data, start + 2, field),
            )
        )
    return tuple(values)


def decode_wild_encounters(data: bytes, template: dict[str, Any]) -> list[dict[str, Any]]:
    region = template["regions"]["wild_headers"]
    offset = _integer(region["offset"], "regions.wild_headers.offset")
    size = _integer(region["size"], "regions.wild_headers.size", minimum=20)
    if size % 20:
        raise EmeraldAnalysisError("wild header region is not a multiple of 20 bytes")
    result = []
    for index in range(size // 20):
        start = offset + index * 20
        group, number = _slice(data, start, 2, "wild header")
        if group == 0xFF and number == 0xFF:
            break
        pointers = struct.unpack_from("<4I", data, start + 4)
        result.append(
            {
                "map_group": group,
                "map_number": number,
                "land": _decode_wild_info(data, pointers[0], 12, "wild.land"),
                "water": _decode_wild_info(data, pointers[1], 5, "wild.water"),
                "rock_smash": _decode_wild_info(data, pointers[2], 5, "wild.rock_smash"),
                "fishing": _decode_wild_info(data, pointers[3], 10, "wild.fishing"),
            }
        )
    return result


def decode_ingame_trades(data: bytes, template: dict[str, Any]) -> list[dict[str, int]]:
    region = template["regions"]["ingame_trades"]
    offset = _integer(region["offset"], "regions.ingame_trades.offset")
    size = _integer(region["size"], "regions.ingame_trades.size", minimum=60)
    if size % 60:
        raise EmeraldAnalysisError("in-game trade region is not a multiple of 60 bytes")
    return [
        {
            "index": index,
            "species": _u16(data, offset + index * 60 + 12, "trade species"),
            "requested_species": _u16(
                data, offset + index * 60 + 54, "trade requested species"
            ),
        }
        for index in range(size // 60)
    ]


def trainer_experience(trainer: Trainer, species: dict[int, Species]) -> int:
    total = 0
    for mon in trainer.party:
        record = species.get(mon.species)
        if record is None:
            raise EmeraldAnalysisError(
                f"trainer {trainer.id} references unknown species {mon.species}"
            )
        total += record.base_exp * mon.level * 3 // 14
    return total


def _requirements(value: Any, field: str) -> frozenset[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise EmeraldAnalysisError(f"{field} must be a list of fact names")
    return frozenset(value)


def solve_reachability(template: dict[str, Any]) -> dict[str, Any]:
    """Assign topology content to the earliest chapter with predecessor witnesses."""
    topology = template["topology"]
    if not isinstance(topology, dict):
        raise EmeraldAnalysisError("topology must be an object")
    zones = topology.get("zones")
    edges = topology.get("edges")
    actions = topology.get("actions")
    milestones = topology.get("milestones")
    if not all(isinstance(value, list) for value in (zones, edges, actions, milestones)):
        raise EmeraldAnalysisError("topology lists are malformed")
    zone_ids = {row.get("id") for row in zones if isinstance(row, dict)}
    if None in zone_ids or len(zone_ids) != len(zones):
        raise EmeraldAnalysisError("topology zones must have unique ids")
    start = topology.get("start")
    if start not in zone_ids:
        raise EmeraldAnalysisError("topology start zone is unknown")
    if len(milestones) != 9:
        raise EmeraldAnalysisError("Emerald topology must declare nine milestones")

    adjacency: dict[str, list[tuple[str, frozenset[str], str]]] = {zone: [] for zone in zone_ids}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict) or edge.get("from") not in zone_ids or edge.get("to") not in zone_ids:
            raise EmeraldAnalysisError(f"topology edge {index} is malformed")
        req = _requirements(edge.get("requires", []), f"topology.edges[{index}].requires")
        adjacency[edge["from"]].append((edge["to"], req, str(edge.get("id", index))))
        if edge.get("bidirectional", False):
            adjacency[edge["to"]].append((edge["from"], req, str(edge.get("id", index))))
    for values in adjacency.values():
        values.sort(key=lambda row: (row[0], tuple(sorted(row[1])), row[2]))

    facts = set(_requirements(topology.get("initial_facts", []), "topology.initial_facts"))
    reachable = {start}
    predecessor: dict[str, dict[str, str] | None] = {start: None}
    applied: set[str] = set()
    chapter_results = []

    def close(excluded_action: str) -> None:
        changed = True
        while changed:
            changed = False
            queue = sorted(reachable)
            for zone in queue:
                for target, req, edge_id in adjacency[zone]:
                    if target not in reachable and req <= facts:
                        reachable.add(target)
                        predecessor[target] = {"zone": zone, "edge": edge_id}
                        changed = True
            for index, action in enumerate(actions):
                if not isinstance(action, dict):
                    raise EmeraldAnalysisError(f"topology action {index} is malformed")
                action_id = action.get("id")
                if not isinstance(action_id, str) or not action_id:
                    raise EmeraldAnalysisError(f"topology action {index} has no id")
                if action_id in applied or action_id == excluded_action:
                    continue
                req = _requirements(action.get("requires", []), f"action {action_id}.requires")
                if action.get("zone") in reachable and req <= facts:
                    facts.update(_requirements(action.get("grants", []), f"action {action_id}.grants"))
                    applied.add(action_id)
                    changed = True

    def witness(zone: str) -> list[dict[str, str]]:
        result = []
        current = zone
        while predecessor.get(current) is not None:
            step = predecessor[current]
            assert step is not None
            result.append({"from": step["zone"], "edge": step["edge"], "to": current})
            current = step["zone"]
        result.reverse()
        return result

    for chapter_index, milestone in enumerate(milestones, 1):
        if not isinstance(milestone, dict):
            raise EmeraldAnalysisError(f"milestone {chapter_index} is malformed")
        action_id = milestone.get("action")
        zone = milestone.get("zone")
        close(str(action_id))
        if zone not in reachable:
            raise EmeraldAnalysisError(f"milestone {milestone.get('id')} is unreachable")
        chapter_results.append(
            {
                "index": chapter_index,
                "id": milestone.get("id"),
                "facts": sorted(facts),
                "reachable_zones": sorted(reachable),
                "milestone_witness": witness(str(zone)),
                "zone_witnesses": {name: witness(name) for name in sorted(reachable)},
            }
        )
        matching = [action for action in actions if action.get("id") == action_id]
        if len(matching) != 1:
            raise EmeraldAnalysisError(f"milestone action {action_id} is not unique")
        facts.update(_requirements(matching[0].get("grants", []), f"action {action_id}.grants"))
        applied.add(str(action_id))
    return {"chapters": chapter_results, "facts": sorted(facts)}


def _round_fraction(value: Fraction) -> int:
    return (value.numerator * 2 + value.denominator) // (2 * value.denominator)


def generate_piecewise_tables(
    vanilla: list[list[int]],
    caps: Iterable[int],
    chapter_xp: Iterable[int],
    family_growth_groups: Iterable[Iterable[int]],
) -> tuple[list[list[int]], list[dict[str, Any]]]:
    cap_values = tuple(caps)
    xp_values = tuple(chapter_xp)
    weights = tuple(tuple(groups) for groups in family_growth_groups)
    if not (len(cap_values) == len(xp_values) == len(weights) == len(QUOTAS)):
        raise EmeraldAnalysisError("piecewise curve inputs must contain nine chapters")
    previous = 5
    for index, cap in enumerate(cap_values):
        if not isinstance(cap, int) or isinstance(cap, bool) or not previous <= cap < 100:
            raise EmeraldAnalysisError(f"chapter {index + 1} cap must be from {previous} through 99")
        previous = cap
    if len(vanilla) != GROWTH_GROUP_COUNT or any(len(table) != LEVEL_COUNT for table in vanilla):
        raise EmeraldAnalysisError("vanilla experience table dimensions are invalid")

    output = [[0] * LEVEL_COUNT for _ in range(GROWTH_GROUP_COUNT)]
    for growth in range(GROWTH_GROUP_COUNT):
        output[growth][:6] = vanilla[growth][:6]
    diagnostics = []
    floor = 5
    for index, (cap, budget, groups, quota) in enumerate(
        zip(cap_values, xp_values, weights, QUOTAS), 1
    ):
        if budget < 0:
            raise EmeraldAnalysisError(f"chapter {index} XP budget cannot be negative")
        if not groups or any(group < 0 or group >= GROWTH_GROUP_COUNT for group in groups):
            raise EmeraldAnalysisError(f"chapter {index} has invalid family growth groups")
        base_cost_sum = sum(vanilla[group][cap] - vanilla[group][floor] for group in groups)
        if cap == floor:
            scale = Fraction(1, 1)
            warning = "positive budget has no level band" if budget else None
        elif base_cost_sum == 0 or budget == 0:
            scale = Fraction(1, 1)
            warning = "positive level band has no trainer XP" if budget == 0 else None
        else:
            scale = Fraction(budget * len(groups), quota * base_cost_sum)
            warning = None
        for growth in range(GROWTH_GROUP_COUNT):
            for level in range(floor + 1, cap + 1):
                vanilla_delta = vanilla[growth][level] - vanilla[growth][level - 1]
                output[growth][level] = output[growth][level - 1] + max(
                    1, _round_fraction(vanilla_delta * scale)
                )
        represented_costs = [output[group][cap] - output[group][floor] for group in groups]
        represented_mean = Fraction(sum(represented_costs), len(represented_costs))
        target = Fraction(budget, quota)
        diagnostics.append(
            {
                "chapter": index,
                "floor": floor,
                "cap": cap,
                "quota": quota,
                "budget": budget,
                "family_count": len(groups),
                "scale": {"numerator": scale.numerator, "denominator": scale.denominator},
                "target_mean_cost": {
                    "numerator": target.numerator,
                    "denominator": target.denominator,
                },
                "represented_mean_cost": {
                    "numerator": represented_mean.numerator,
                    "denominator": represented_mean.denominator,
                },
                "residual_numerator": abs(
                    represented_mean.numerator * target.denominator
                    - target.numerator * represented_mean.denominator
                ),
                "warning": warning,
            }
        )
        floor = cap
    champion_cap = cap_values[-1]
    for growth in range(GROWTH_GROUP_COUNT):
        for level in range(champion_cap + 1, LEVEL_COUNT):
            vanilla_delta = vanilla[growth][level] - vanilla[growth][level - 1]
            output[growth][level] = output[growth][level - 1] + vanilla_delta
        if any(after <= before for before, after in zip(output[growth][1:100], output[growth][2:101])):
            raise EmeraldAnalysisError(f"generated growth table {growth} is not monotone")
    return output, diagnostics


def serialize_experience_tables(tables: list[list[int]]) -> bytes:
    if len(tables) != GROWTH_GROUP_COUNT or any(len(table) != LEVEL_COUNT for table in tables):
        raise EmeraldAnalysisError("generated experience table dimensions are invalid")
    return b"".join(struct.pack("<101I", *table) for table in tables)


def _earliest_chapter_for_content(
    content: dict[str, Any], reachability: dict[str, Any], field: str
) -> tuple[int, dict[str, Any]]:
    zone = content.get("zone")
    if not isinstance(zone, str) or not zone:
        raise EmeraldAnalysisError(f"{field}.zone must be a non-empty string")
    requirements = _requirements(content.get("requires", []), f"{field}.requires")
    for chapter in reachability["chapters"]:
        if zone in chapter["reachable_zones"] and requirements <= set(chapter["facts"]):
            return int(chapter["index"]), {
                "zone": zone,
                "path": chapter["zone_witnesses"][zone],
                "requirements": sorted(requirements),
            }
    raise EmeraldAnalysisError(f"{field} in {zone} is unreachable before the Champion")


def classify_trainers(
    template: dict[str, Any],
    reachability: dict[str, Any],
    trainers: dict[int, Trainer],
    species: dict[int, Species],
) -> list[dict[str, Any]]:
    instances = template.get("trainer_instances")
    if not isinstance(instances, list):
        raise EmeraldAnalysisError("trainer_instances must be a list")
    result = []
    seen: set[str] = set()
    for index, instance in enumerate(instances):
        field = f"trainer_instances[{index}]"
        if not isinstance(instance, dict):
            raise EmeraldAnalysisError(f"{field} must be an object")
        instance_id = instance.get("id")
        if not isinstance(instance_id, str) or not instance_id or instance_id in seen:
            raise EmeraldAnalysisError(f"{field}.id must be unique")
        seen.add(instance_id)
        trainer_id = _integer(instance.get("trainer_id"), f"{field}.trainer_id")
        if trainer_id not in trainers:
            raise EmeraldAnalysisError(f"{field} references unknown trainer {trainer_id}")
        if instance.get("repeatable", False):
            continue
        chapter, witness = _earliest_chapter_for_content(instance, reachability, field)
        result.append(
            {
                "id": instance_id,
                "trainer_id": trainer_id,
                "trainer": template["trainer_names"][trainer_id],
                "chapter": chapter,
                "xp": trainer_experience(trainers[trainer_id], species),
                "choice_group": instance.get("choice_group"),
                "milestone": instance.get("milestone"),
                "source": instance.get("source"),
                "witness": witness,
            }
        )
    return result


def chapter_trainer_budgets(
    classifications: list[dict[str, Any]], template: dict[str, Any]
) -> tuple[list[int], list[list[dict[str, Any]]]]:
    milestone_ids = [row["id"] for row in template["topology"]["milestones"]]
    budgets = []
    chapter_rows = []
    for chapter in range(1, 10):
        rows = [row for row in classifications if row["chapter"] == chapter]
        ending = milestone_ids[chapter - 1]
        eligible = [row for row in rows if row.get("milestone") != ending]
        ordinary = [row for row in eligible if row.get("choice_group") is None]
        choices: dict[str, list[dict[str, Any]]] = {}
        for row in eligible:
            group = row.get("choice_group")
            if group is not None:
                choices.setdefault(str(group), []).append(row)
        chosen = [
            max(values, key=lambda row: (row["xp"], row["id"]))
            for _, values in sorted(choices.items())
        ]
        included = sorted(ordinary + chosen, key=lambda row: row["id"])
        budgets.append(sum(row["xp"] for row in included))
        chapter_rows.append(included)
    return budgets, chapter_rows


def _family_components(species_ids: Iterable[int], evolutions: list[Evolution]) -> dict[int, int]:
    parents = {species: species for species in species_ids}

    def find(value: int) -> int:
        while parents[value] != value:
            parents[value] = parents[parents[value]]
            value = parents[value]
        return value

    def union(left: int, right: int) -> None:
        if left not in parents or right not in parents:
            return
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parents[max(left_root, right_root)] = min(left_root, right_root)

    for evolution in evolutions:
        union(evolution.source, evolution.target)
    return {species: find(species) for species in parents}


def _evolution_is_legal(
    evolution: Evolution,
    floor: int,
    facts: set[str],
    methods: dict[str, Any],
) -> bool:
    method = methods.get(str(evolution.method))
    if not isinstance(method, dict) or not isinstance(method.get("kind"), str):
        raise EmeraldAnalysisError(f"evolution method {evolution.method} is not declared")
    requirements = _requirements(method.get("requires", []), "evolution method requirements")
    if not requirements <= facts:
        return False
    kind = method["kind"]
    if kind == "level":
        return evolution.parameter <= floor
    if kind == "item":
        return f"item:{evolution.parameter}" in facts
    if kind == "trade_item":
        return "trading" in facts and f"item:{evolution.parameter}" in facts
    if kind == "trade":
        return "trading" in facts
    if kind == "friendship":
        return "friendship" in facts
    if kind == "beauty":
        return "beauty" in facts
    raise EmeraldAnalysisError(f"unsupported evolution method kind {kind}")


def _ordinary_acquisitions(
    data: bytes,
    template: dict[str, Any],
    wild: list[dict[str, Any]],
    trades: list[dict[str, int]],
) -> list[dict[str, Any]]:
    declarations = template.get("acquisitions")
    if not isinstance(declarations, list):
        raise EmeraldAnalysisError("acquisitions must be a list")
    wild_by_map = {(row["map_group"], row["map_number"]): row for row in wild}
    result = []
    for index, declaration in enumerate(declarations):
        field = f"acquisitions[{index}]"
        if not isinstance(declaration, dict):
            raise EmeraldAnalysisError(f"{field} must be an object")
        kind = declaration.get("kind")
        common = {
            key: declaration.get(key)
            for key in ("id", "zone", "requires", "choice_group", "source")
        }
        if kind == "wild":
            map_key = (
                _integer(declaration.get("map_group"), f"{field}.map_group"),
                _integer(declaration.get("map_number"), f"{field}.map_number"),
            )
            method = declaration.get("method")
            header = wild_by_map.get(map_key)
            if method not in {"land", "water", "rock_smash", "fishing"}:
                raise EmeraldAnalysisError(f"{field} does not resolve to a wild table")
            if header is None or not header[method]:
                continue
            for species_id in sorted({slot.species for slot in header[method]}):
                result.append({**common, "id": f"{common['id']}:{species_id}", "species": species_id})
        elif kind == "ingame_trade":
            trade_index = _integer(declaration.get("trade_index"), f"{field}.trade_index")
            if trade_index >= len(trades):
                raise EmeraldAnalysisError(f"{field} references unknown in-game trade")
            result.append(
                {
                    **common,
                    "species": trades[trade_index]["species"],
                    "requested_species": trades[trade_index]["requested_species"],
                }
            )
        elif kind in {"starter", "gift", "static", "fossil"}:
            value = declaration.get("species")
            if isinstance(value, int) and not isinstance(value, bool):
                species_id = value
            else:
                site = declaration.get("species_site")
                if not isinstance(site, dict):
                    raise EmeraldAnalysisError(f"{field} needs species or species_site")
                offset = _integer(site.get("offset"), f"{field}.species_site.offset")
                width = site.get("width")
                if width == 1:
                    species_id = _slice(data, offset, 1, field)[0]
                elif width == 2:
                    species_id = _u16(data, offset, field)
                else:
                    raise EmeraldAnalysisError(f"{field}.species_site.width must be 1 or 2")
            result.append({**common, "species": species_id})
        else:
            raise EmeraldAnalysisError(f"{field} has unsupported kind {kind!r}")
    return result


def classify_families(
    data: bytes,
    template: dict[str, Any],
    reachability: dict[str, Any],
    species: dict[int, Species],
    evolutions: list[Evolution],
    wild: list[dict[str, Any]],
    trades: list[dict[str, int]],
    caps: tuple[int, ...],
) -> tuple[list[list[dict[str, Any]]], list[list[int]]]:
    acquisitions = _ordinary_acquisitions(data, template, wild, trades)
    components = _family_components(species, evolutions)
    by_source: dict[int, list[Evolution]] = {}
    for evolution in evolutions:
        by_source.setdefault(evolution.source, []).append(evolution)
    for values in by_source.values():
        values.sort(key=lambda row: (row.target, row.method, row.parameter))
    methods = template["evolution_methods"]
    if not isinstance(methods, dict):
        raise EmeraldAnalysisError("evolution_methods must be an object")

    classified = []
    for index, acquisition in enumerate(acquisitions):
        chapter, witness = _earliest_chapter_for_content(
            acquisition, reachability, f"resolved acquisition {index}"
        )
        species_id = _integer(acquisition.get("species"), "acquisition species", minimum=1)
        if species_id not in species:
            raise EmeraldAnalysisError(f"acquisition references unknown species {species_id}")
        classified.append({**acquisition, "chapter": chapter, "witness": witness})

    chapter_families: list[list[dict[str, Any]]] = []
    chapter_growths: list[list[int]] = []
    available: list[dict[str, Any]] = []
    floor = 5
    for chapter_index in range(1, 10):
        available.extend(row for row in classified if row["chapter"] == chapter_index)
        facts = set(reachability["chapters"][chapter_index - 1]["facts"])
        # In-game trades become legal only when their donor family is already
        # represented by another obtainable source. Iterate to a fixed point.
        eligible = [row for row in available if "requested_species" not in row]
        changed = True
        while changed:
            changed = False
            family_ids = {components[row["species"]] for row in eligible}
            for row in available:
                donor = row.get("requested_species")
                if donor is not None and row not in eligible and components.get(donor) in family_ids:
                    eligible.append(row)
                    changed = True

        families: dict[int, dict[str, Any]] = {}
        for row in eligible:
            root = components[row["species"]]
            family = families.setdefault(root, {"id": root, "sources": [], "stages": set()})
            family["sources"].append(row["id"])
            family["stages"].add(row["species"])
        for root, family in families.items():
            reachable_stages = set(family["stages"])
            queue = sorted(reachable_stages)
            for current in queue:
                for evolution in by_source.get(current, []):
                    if _evolution_is_legal(evolution, floor, facts, methods) and evolution.target not in reachable_stages:
                        reachable_stages.add(evolution.target)
                        queue.append(evolution.target)
            stages = [
                current
                for current in sorted(reachable_stages)
                if not any(
                    evolution.target in reachable_stages
                    and _evolution_is_legal(evolution, floor, facts, methods)
                    for evolution in by_source.get(current, [])
                )
            ]
            growths = {species[value].growth_group for value in components if components[value] == root}
            if len(growths) != 1:
                raise EmeraldAnalysisError(f"family {root} has inconsistent growth groups")
            family["growth_group"] = next(iter(growths))
            family["sources"] = sorted(family["sources"])
            family["stages"] = stages
        rows = [families[key] for key in sorted(families)]
        chapter_families.append(rows)
        chapter_growths.append([row["growth_group"] for row in rows])
        floor = caps[chapter_index - 1]
    return chapter_families, chapter_growths


def analyse_emerald(
    data: bytes,
    template: dict[str, Any],
    caps: Iterable[int],
) -> tuple[dict[str, Any], bytes]:
    """Run the clean-ROM Emerald reference pipeline and return manifest/table bytes."""
    validate_emerald_rom(data, template)
    cap_values = tuple(caps)
    if len(cap_values) != 9:
        raise EmeraldAnalysisError("Emerald analysis requires nine caps")
    species = decode_species(data, template)
    trainers = decode_trainers(data, template)
    evolutions = decode_evolutions(data, template, len(species))
    vanilla = decode_experience_tables(data, template)
    wild = decode_wild_encounters(data, template)
    trades = decode_ingame_trades(data, template)
    reachability = solve_reachability(template)
    trainer_rows = classify_trainers(template, reachability, trainers, species)
    budgets, chapter_trainers = chapter_trainer_budgets(trainer_rows, template)
    families, growths = classify_families(
        data,
        template,
        reachability,
        species,
        evolutions,
        wild,
        trades,
        cap_values,
    )
    tables, diagnostics = generate_piecewise_tables(vanilla, cap_values, budgets, growths)
    table_bytes = serialize_experience_tables(tables)
    lints: list[dict[str, Any]] = []
    prior_scale: Fraction | None = None
    prior_family_count = 0
    for diagnostic in diagnostics:
        scale = Fraction(diagnostic["scale"]["numerator"], diagnostic["scale"]["denominator"])
        chapter = diagnostic["chapter"]
        if prior_scale is not None and (scale * 2 < prior_scale or scale > prior_scale * 2):
            lints.append({
                "severity": "warning",
                "code": "adjacent-scale-ratio",
                "chapter": chapter,
                "message": "chapter scale differs from its predecessor by more than 2x",
            })
        if diagnostic["family_count"] < prior_family_count:
            lints.append({
                "severity": "warning",
                "code": "family-count-decreased",
                "chapter": chapter,
                "message": "obtainable family count decreased",
            })
        if diagnostic["warning"]:
            lints.append({
                "severity": "warning",
                "code": "degenerate-band",
                "chapter": chapter,
                "message": diagnostic["warning"],
            })
        prior_scale = scale
        prior_family_count = diagnostic["family_count"]
    manifest = {
        "schema": 1,
        "game": "emerald",
        "input_sha1": hashlib.sha1(data).hexdigest(),
        "input_sha256": _sha256(data),
        "template_sha256": _sha256(
            json.dumps(template, sort_keys=True, separators=(",", ":")).encode()
        ),
        "caps": list(cap_values),
        "quotas": list(QUOTAS),
        "chapters": [
            {
                "index": index,
                "id": template["topology"]["milestones"][index - 1]["id"],
                "floor": 5 if index == 1 else cap_values[index - 2],
                "cap": cap_values[index - 1],
                "trainer_xp": budgets[index - 1],
                "trainers": chapter_trainers[index - 1],
                "families": families[index - 1],
                "curve": diagnostics[index - 1],
            }
            for index in range(1, 10)
        ],
        "experience_tables_sha256": _sha256(table_bytes),
        "lints": lints,
    }
    return manifest, table_bytes
