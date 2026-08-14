import hashlib
import struct
import unittest
import json
from pathlib import Path

from nuzlike_patcher.emerald_analysis import (
    EmeraldAnalysisError,
    decode_evolutions,
    decode_experience_tables,
    decode_ingame_trades,
    decode_species,
    decode_trainers,
    decode_wild_encounters,
    generate_piecewise_tables,
    serialize_experience_tables,
    solve_reachability,
    trainer_experience,
    validate_emerald_rom,
    analyse_emerald,
)


def synthetic_rom_and_template():
    rom = bytearray(0x2000)

    species_offset = 0x100
    for species, (base_exp, growth) in enumerate(((0, 0), (64, 2), (142, 2))):
        record = bytearray(28)
        record[9] = base_exp
        record[0x13] = growth
        rom[species_offset + species * 28 : species_offset + (species + 1) * 28] = record

    trainer_offset = 0x200
    party_offset = 0x300
    trainer = bytearray(40)
    trainer[0] = 0
    trainer[0x20] = 2
    struct.pack_into("<I", trainer, 0x24, 0x08000000 + party_offset)
    rom[trainer_offset + 40 : trainer_offset + 80] = trainer
    struct.pack_into("<HBxH", rom, party_offset, 0, 10, 1)
    struct.pack_into("<HBxH", rom, party_offset + 8, 0, 20, 2)

    experience_offset = 0x400
    vanilla = [[(growth + 1) * level**3 for level in range(101)] for growth in range(8)]
    rom[experience_offset : experience_offset + 8 * 101 * 4] = serialize_experience_tables(vanilla)

    evolution_offset = 0x1100
    struct.pack_into("<HHHxx", rom, evolution_offset + 1 * 5 * 8, 4, 16, 2)

    wild_offset = 0x1300
    wild_info = 0x1360
    wild_slots = 0x1380
    rom[wild_offset : wild_offset + 2] = bytes((0, 1))
    struct.pack_into("<I", rom, wild_offset + 4, 0x08000000 + wild_info)
    rom[wild_offset + 20 : wild_offset + 22] = b"\xff\xff"
    rom[wild_info] = 20
    struct.pack_into("<I", rom, wild_info + 4, 0x08000000 + wild_slots)
    for index in range(12):
        struct.pack_into("<BBH", rom, wild_slots + index * 4, 2, 4, 1 + index % 2)

    trade_offset = 0x1400
    struct.pack_into("<H", rom, trade_offset + 12, 2)
    struct.pack_into("<H", rom, trade_offset + 54, 1)

    regions = {
        "species": {"offset": species_offset, "size": 3 * 28},
        "trainers": {"offset": trainer_offset, "size": 2 * 40},
        "experience": {"offset": experience_offset, "size": 8 * 101 * 4},
        "evolutions": {"offset": evolution_offset, "size": 3 * 5 * 8},
        "wild_headers": {"offset": wild_offset, "size": 40},
        "ingame_trades": {"offset": trade_offset, "size": 60},
    }
    for region in regions.values():
        start = region["offset"]
        region["sha256"] = hashlib.sha256(rom[start : start + region["size"]]).hexdigest()

    zones = [{"id": "start"}] + [{"id": f"gym_{index}"} for index in range(1, 10)]
    edges = []
    actions = []
    milestones = []
    prior = "start"
    prior_fact = None
    for index in range(1, 10):
        requirements = [] if prior_fact is None else [prior_fact]
        edges.append(
            {
                "id": f"to_{index}",
                "from": prior,
                "to": f"gym_{index}",
                "requires": requirements,
                "bidirectional": True,
            }
        )
        fact = f"milestone_{index}"
        action = f"beat_{index}"
        actions.append(
            {
                "id": action,
                "zone": f"gym_{index}",
                "requires": requirements,
                "grants": [fact],
            }
        )
        milestones.append({"id": f"leader_{index}", "zone": f"gym_{index}", "action": action})
        prior = f"gym_{index}"
        prior_fact = fact

    template = {
        "schema": 1,
        "game": "emerald",
        "accepted_sha1": [hashlib.sha1(rom).hexdigest()],
        "regions": regions,
        "species_names": ["NONE", "FIRST", "SECOND"],
        "trainer_names": ["NONE", "TEST"],
        "topology": {
            "start": "start",
            "initial_facts": [],
            "zones": zones,
            "edges": edges,
            "actions": actions,
            "milestones": milestones,
        },
        "trainer_instances": [
            {
                "id": "ordinary-test",
                "trainer_id": 1,
                "zone": "start",
                "requires": [],
                "source": "synthetic",
            }
        ],
        "acquisitions": [
            {
                "id": "starter-test",
                "kind": "starter",
                "species": 1,
                "zone": "start",
                "requires": [],
                "source": "synthetic",
            }
        ],
        "evolution_methods": {"4": {"kind": "level"}},
    }
    return bytes(rom), template, vanilla


class EmeraldRomDecoderTests(unittest.TestCase):
    def setUp(self):
        self.rom, self.template, self.vanilla = synthetic_rom_and_template()

    def test_fingerprints_bind_the_actual_rom(self):
        validate_emerald_rom(self.rom, self.template)
        changed = bytearray(self.rom)
        changed[0x109] ^= 1
        self.template["accepted_sha1"] = [hashlib.sha1(changed).hexdigest()]
        with self.assertRaisesRegex(EmeraldAnalysisError, "region species changed"):
            validate_emerald_rom(bytes(changed), self.template)

    def test_decodes_mutable_emerald_tables(self):
        species = decode_species(self.rom, self.template)
        trainers = decode_trainers(self.rom, self.template)
        evolutions = decode_evolutions(self.rom, self.template, len(species))
        wild = decode_wild_encounters(self.rom, self.template)
        trades = decode_ingame_trades(self.rom, self.template)
        self.assertEqual((species[2].base_exp, species[2].growth_group), (142, 2))
        self.assertEqual([(mon.level, mon.species) for mon in trainers[1].party], [(10, 1), (20, 2)])
        self.assertEqual(trainer_experience(trainers[1], species), 64 * 10 * 3 // 14 + 142 * 20 * 3 // 14)
        self.assertEqual((evolutions[0].source, evolutions[0].parameter, evolutions[0].target), (1, 16, 2))
        self.assertEqual(len(wild[0]["land"]), 12)
        self.assertEqual(trades, [{"index": 0, "species": 2, "requested_species": 1}])
        self.assertEqual(decode_experience_tables(self.rom, self.template), self.vanilla)

    def test_fixed_point_solver_records_each_milestone_witness(self):
        result = solve_reachability(self.template)
        self.assertEqual(len(result["chapters"]), 9)
        self.assertEqual(result["chapters"][0]["reachable_zones"], ["gym_1", "start"])
        self.assertIn("milestone_8", result["chapters"][8]["facts"])
        self.assertEqual(result["chapters"][8]["milestone_witness"][-1]["to"], "gym_9")

    def test_piecewise_tables_are_continuous_and_restore_vanilla_deltas(self):
        caps = (15, 19, 24, 29, 31, 33, 42, 46, 58)
        budgets = (10000, 16000, 36000, 43000, 11000, 101000, 132000, 159000, 116000)
        family_growths = tuple((0, 1, 2, 3, 4, 5) for _ in range(9))
        tables, diagnostics = generate_piecewise_tables(
            self.vanilla, caps, budgets, family_growths
        )
        self.assertEqual(len(diagnostics), 9)
        self.assertTrue(all(tables[0][level] > tables[0][level - 1] for level in range(2, 101)))
        self.assertEqual(
            tables[3][59] - tables[3][58],
            self.vanilla[3][59] - self.vanilla[3][58],
        )
        self.assertNotEqual(tables[3][15], self.vanilla[3][15])

    def test_complete_analysis_is_deterministic_and_uses_floor_stage(self):
        caps = (15, 19, 24, 29, 31, 33, 42, 46, 58)
        first, first_tables = analyse_emerald(self.rom, self.template, caps)
        second, second_tables = analyse_emerald(self.rom, self.template, caps)
        self.assertEqual((first, first_tables), (second, second_tables))
        self.assertIn("lints", first)
        self.assertIsInstance(first["lints"], list)
        self.assertEqual(first["chapters"][0]["trainer_xp"], 64 * 10 * 3 // 14 + 142 * 20 * 3 // 14)
        self.assertEqual(first["chapters"][0]["families"][0]["stages"], [1])
        self.assertEqual(first["chapters"][2]["families"][0]["stages"], [2])


class CheckedInEmeraldAnalysisTests(unittest.TestCase):
    def test_public_template_contains_source_witnessed_clean_reference_inputs(self):
        root = Path(__file__).resolve().parents[1]
        template = json.loads((root / "analysis/emerald.json").read_text(encoding="utf-8"))
        recipe = json.loads((root / "recipes/emerald.json").read_text(encoding="utf-8"))
        self.assertEqual(len(template["topology"]["milestones"]), 9)
        self.assertGreater(len(template["topology"]["zones"]), 300)
        self.assertGreater(len(template["trainer_instances"]), 500)
        self.assertGreater(len(template["acquisitions"]), 1000)
        self.assertTrue(all(row["source"] for row in template["trainer_instances"]))
        finite = [
            row for row in template["acquisitions"]
            if row["kind"] in {"starter", "gift", "static", "fossil"}
        ]
        self.assertTrue(finite)
        self.assertTrue(all("species_site" in row and "species" not in row for row in finite))
        analysis = recipe["emerald_chapter_xp"]
        self.assertEqual(len(analysis["budgets"]), 9)
        self.assertEqual(len(analysis["family_growth_groups"]), 9)
        self.assertTrue(all(analysis["family_growth_groups"]))


if __name__ == "__main__":
    unittest.main()
