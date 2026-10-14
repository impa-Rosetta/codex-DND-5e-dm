"""Guard the frozen SRD 5.1 race/class option index against omissions."""

import json
import unittest
from pathlib import Path


DATA = Path(__file__).resolve().parents[1] / "skills/codex-5e-dm/data"
RACES = {
    "dwarf_hill", "dwarf_mountain", "elf_high", "elf_wood", "elf_drow",
    "halfling_lightfoot", "halfling_stout", "human", "dragonborn",
    "gnome_forest", "gnome_rock", "half_elf", "half_orc", "tiefling",
}
CLASSES = {
    "barbarian", "bard", "cleric", "druid", "fighter", "monk",
    "paladin", "ranger", "rogue", "sorcerer", "warlock", "wizard",
}
DRAGONS = {"black", "blue", "brass", "bronze", "copper", "gold",
           "green", "red", "silver", "white"}
FIGHTING_STYLES = {"archery", "defense", "dueling", "great_weapon_fighting",
                   "protection", "two_weapon_fighting"}


class LevelOneInventoryTests(unittest.TestCase):
    def test_all_srd_race_and_class_options_have_individual_rule_ids(self):
        catalog = json.loads((DATA / "character-options.json").read_text(encoding="utf-8"))
        rules = json.loads((DATA / "rules-index.json").read_text(encoding="utf-8"))
        self.assertEqual({entry["id"] for entry in catalog["races"]}, RACES)
        self.assertEqual({entry["id"] for entry in catalog["classes"]}, CLASSES)
        self.assertEqual(rules["ruleset"], catalog["ruleset"])
        entries = {entry["id"]: entry for entry in rules["rules"]}
        self.assertEqual(len(entries), len(rules["rules"]))
        for group, names, prefix in (("races", RACES, "race"),
                                     ("classes", CLASSES, "class")):
            for item in catalog[group]:
                with self.subTest(item=item["id"]):
                    rule = entries[f"{prefix}.{item['id']}"]
                    self.assertEqual(rule["kind"], "entry")
                    self.assertEqual(rule["section"], item["section"])
                    self.assertTrue(rule["m2_required"])
                    self.assertEqual(rule["status"], "indexed_only")

    def test_inventory_does_not_claim_equipment_or_spells_are_frozen(self):
        inventory = json.loads((DATA / "level1-inventory.json").read_text(encoding="utf-8"))
        rules = json.loads((DATA / "rules-index.json").read_text(encoding="utf-8"))
        self.assertEqual(inventory["ruleset"], "srd-5.1-2014")
        self.assertEqual(inventory["status"], "partial_index")
        self.assertEqual(set(inventory["race_ids"]), RACES)
        self.assertEqual(set(inventory["class_ids"]), CLASSES)
        self.assertEqual(set(inventory["background_ids"]), {"acolyte", "custom_background"})
        self.assertEqual(set(inventory["level1_subclass_ids"]), {
            "class.cleric.life_domain", "class.sorcerer.draconic_bloodline",
            "class.warlock.fiend",
        })
        indexed = {entry["id"] for entry in rules["rules"]}
        self.assertTrue(set(inventory["level1_subclass_ids"]) <= indexed)
        self.assertEqual(inventory["equipment_branches"]["status"], "not_frozen")
        self.assertEqual(inventory["cantrips_and_level1_spells"]["status"], "not_frozen")
        self.assertEqual(inventory["other_level1_choices"]["status"], "not_frozen")

    def test_dragon_ancestry_and_fighter_styles_are_individual_choices(self):
        inventory = json.loads((DATA / "level1-inventory.json").read_text(encoding="utf-8"))
        rules = json.loads((DATA / "rules-index.json").read_text(encoding="utf-8"))
        self.assertEqual(set(inventory["dragonborn_ancestry_ids"]), DRAGONS)
        self.assertEqual(set(inventory["fighter_style_ids"]), FIGHTING_STYLES)
        indexed = {entry["id"]: entry for entry in rules["rules"]}
        for ancestry in DRAGONS:
            self.assertIn(f"race.dragonborn.ancestry.{ancestry}", indexed)
        for style in FIGHTING_STYLES:
            self.assertIn(f"class.fighter.style.{style}", indexed)


if __name__ == "__main__":
    unittest.main()
