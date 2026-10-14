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

    def test_inventory_does_not_claim_equipment_or_spells_are_fully_frozen(self):
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
        equipment = inventory["equipment_branches"]
        self.assertEqual(equipment["status"], "partial_index")
        self.assertEqual(equipment["data_file"], "level1-martial-creation-choices.json")
        self.assertEqual(set(equipment["indexed_class_ids"]),
                         {"barbarian", "fighter", "monk", "rogue"})
        self.assertEqual(set(equipment["indexed_class_ids"]) |
                         set(equipment["missing_class_ids"]), CLASSES)
        self.assertFalse(set(equipment["indexed_class_ids"]) &
                         set(equipment["missing_class_ids"]))
        self.assertEqual(inventory["cantrips_and_level1_spells"]["status"], "partial_index")
        self.assertEqual(inventory["cantrips_and_level1_spells"]["data_file"], "level1-spell-lists.json")
        self.assertEqual(inventory["other_level1_choices"]["status"], "partial_index")

    def test_four_martial_starting_packages_have_complete_branch_shapes(self):
        data = json.loads((DATA / "level1-martial-creation-choices.json").read_text(encoding="utf-8"))
        inventory = json.loads((DATA / "level1-inventory.json").read_text(encoding="utf-8"))
        self.assertEqual(data["ruleset"], inventory["ruleset"])
        self.assertEqual(data["status"], "indexed_only")
        classes = {entry["class_id"]: entry for entry in data["classes"]}
        self.assertEqual(len(classes), len(data["classes"]))
        self.assertEqual(set(classes), set(inventory["equipment_branches"]["indexed_class_ids"]))
        expected_branch_counts = {"barbarian": 2, "fighter": 4, "monk": 2, "rogue": 3}
        expected_skill_counts = {"barbarian": 2, "fighter": 2, "monk": 2, "rogue": 4}
        expected_alternatives = {
            "barbarian.weapon": {"greataxe", "martial_melee_weapon"},
            "barbarian.secondary": {"two_handaxes", "simple_weapon"},
            "fighter.armor": {"chain_mail", "leather_and_longbow"},
            "fighter.weapons": {"weapon_and_shield", "two_weapons"},
            "fighter.ranged": {"crossbow", "two_handaxes"},
            "fighter.pack": {"dungeoneers_pack", "explorers_pack"},
            "monk.weapon": {"shortsword", "simple_weapon"},
            "monk.pack": {"dungeoneers_pack", "explorers_pack"},
            "rogue.melee": {"rapier", "shortsword"},
            "rogue.secondary": {"shortbow", "shortsword"},
            "rogue.pack": {"burglars_pack", "dungeoneers_pack", "explorers_pack"},
        }
        observed_branches = {}
        for class_id, entry in classes.items():
            with self.subTest(class_id=class_id):
                self.assertEqual(len(entry["equipment_choices"]), expected_branch_counts[class_id])
                self.assertEqual(entry["skill_choice"]["count"], expected_skill_counts[class_id])
                self.assertEqual(len(set(entry["skill_choice"]["from"])),
                                 len(entry["skill_choice"]["from"]))
                self.assertGreaterEqual(len(entry["skill_choice"]["from"]),
                                        entry["skill_choice"]["count"])
                branch_ids = [branch["id"] for branch in entry["equipment_choices"]]
                self.assertEqual(len(branch_ids), len(set(branch_ids)))
                for branch in entry["equipment_choices"]:
                    observed_branches[branch["id"]] = branch
                    self.assertGreaterEqual(len(branch["alternatives"]), 2)
                    alternative_ids = [option["id"] for option in branch["alternatives"]]
                    self.assertEqual(len(alternative_ids), len(set(alternative_ids)))
                    self.assertEqual(set(alternative_ids), expected_alternatives[branch["id"]])
                    for option in branch["alternatives"]:
                        self.assertTrue(option.get("items") or option.get("selectors"))
                        for item in option.get("items", []):
                            self.assertGreater(item["quantity"], 0)
                        for selector in option.get("selectors", []):
                            self.assertGreater(selector["count"], 0)
                for item in entry["fixed_equipment"]:
                    self.assertGreater(item["quantity"], 0)

        self.assertEqual(set(observed_branches), set(expected_alternatives))
        fighter_weapons = observed_branches["fighter.weapons"]["alternatives"]
        self.assertEqual(fighter_weapons[0]["items"], [{"id": "shield", "quantity": 1}])
        self.assertEqual(fighter_weapons[0]["selectors"],
                         [{"category": "martial_weapon", "count": 1}])
        self.assertEqual(fighter_weapons[1]["selectors"],
                         [{"category": "martial_weapon", "count": 2}])
        rogue_bow = observed_branches["rogue.secondary"]["alternatives"][0]
        self.assertEqual(rogue_bow["items"], [
            {"id": "shortbow", "quantity": 1}, {"id": "quiver", "quantity": 1},
            {"id": "arrow", "quantity": 20}])

        self.assertEqual(classes["barbarian"]["fixed_equipment"], [
            {"id": "explorers_pack", "quantity": 1}, {"id": "javelin", "quantity": 4}])
        self.assertEqual(classes["monk"]["fixed_equipment"], [{"id": "dart", "quantity": 10}])
        self.assertEqual(classes["rogue"]["fixed_equipment"], [
            {"id": "leather_armor", "quantity": 1}, {"id": "dagger", "quantity": 2},
            {"id": "thieves_tools", "quantity": 1}])
        self.assertEqual(classes["monk"]["tool_choice"]["from_categories"],
                         ["artisans_tools", "musical_instrument"])

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
