import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("character", ROOT / "skills/codex-5e-dm/scripts/character.py")
character = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(character)


def hero():
    return {"schema_version": 1, "ruleset": "srd-5.1-2014", "name": "阿澜",
            "race": "human", "class": "fighter", "background": "acolyte",
            "ability_method": "standard_array",
            "base_abilities": {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8},
            "class_skills": ["athletics", "perception"],
            "background_languages": ["elvish", "dwarvish"],
            "fighting_style": "defense", "armor": "chain_mail", "shield": True}


class CharacterTests(unittest.TestCase):
    def test_standard_human_fighter(self):
        result = character.build(hero())
        self.assertEqual(result["derived"]["abilities"]["str"], 16)
        self.assertEqual(result["derived"]["modifiers"]["con"], 2)
        self.assertEqual(result["derived"]["ac"], 19)
        self.assertEqual(result["derived"]["max_hp"], 12)
        self.assertEqual(result["resources"]["second_wind"]["current"], 1)

    def test_all_base_classes_listed_but_not_falsely_buildable(self):
        value = character.options()
        self.assertEqual(len(value["classes"]), 12)
        self.assertEqual([c["id"] for c in value["classes"] if c["status"] == "buildable"], ["fighter"])
        data = hero(); data["class"] = "wizard"
        with self.assertRaises(character.CharacterError) as caught:
            character.build(data)
        self.assertEqual(caught.exception.code, "unsupported_option")

    def test_standard_array_rejects_duplicate(self):
        data = hero(); data["base_abilities"]["cha"] = 10
        with self.assertRaises(character.CharacterError):
            character.build(data)

    def test_point_buy_checks_cost(self):
        data = hero(); data["ability_method"] = "point_buy"
        data["base_abilities"] = dict.fromkeys(character.ABILITIES, 15)
        with self.assertRaises(character.CharacterError):
            character.build(data)
        data["base_abilities"] = {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8}
        self.assertEqual(character.build(data)["derived"]["max_hp"], 12)

    def test_acolyte_skill_cannot_be_stacked(self):
        data = hero(); data["class_skills"] = ["insight", "perception"]
        with self.assertRaises(character.CharacterError):
            character.build(data)

    def test_unknown_mechanical_field_rejected(self):
        data = hero(); data["extra_hp"] = 50
        with self.assertRaises(character.CharacterError):
            character.build(data)


if __name__ == "__main__":
    unittest.main()
