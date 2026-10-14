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
            "fighting_style": "defense", "armor": "chain_mail", "shield": True,
            "weapon": "longsword"}


class CharacterTests(unittest.TestCase):
    def test_standard_human_fighter(self):
        result = character.build(hero())
        self.assertEqual(result["derived"]["abilities"]["str"], 16)
        self.assertEqual(result["derived"]["modifiers"]["con"], 2)
        self.assertEqual(result["derived"]["ac"], 19)
        self.assertEqual(result["derived"]["max_hp"], 12)
        self.assertEqual(result["resources"]["second_wind"]["current"], 1)
        self.assertEqual(result["derived"]["attacks"][0]["attack_bonus"], 5)

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

    def test_unimplemented_fighting_style_rejected(self):
        data = hero(); data["fighting_style"] = "protection"
        with self.assertRaises(character.CharacterError) as caught:
            character.build(data)
        self.assertEqual(caught.exception.code, "unsupported_option")

    def test_dueling_uses_one_handed_longsword_without_changing_attack_bonus(self):
        data = hero(); data["fighting_style"] = "dueling"
        result = character.build(data)
        self.assertEqual(result["derived"]["ac"], 18)
        self.assertEqual(result["derived"]["attacks"][0]["attack_bonus"], 5)
        self.assertEqual(result["derived"]["attacks"][0]["damage_bonus"], 5)
        self.assertEqual(result["derived"]["attacks"][1]["damage_bonus"], 3)
        styles = {item["id"]: item["status"] for item in character.options()["fighting_styles"]}
        self.assertEqual(styles["dueling"], "buildable")
        self.assertEqual(styles["protection"], "indexed_only")

    def test_human_fighter_archer_has_legal_leather_package_and_ammunition(self):
        data = hero()
        data.update(fighting_style="archery", armor="leather_armor", shield=False,
                    weapon="longbow")
        card = character.build(data)
        self.assertEqual(card["derived"]["ac"], 13)
        self.assertEqual(card["derived"]["speed"], 30)
        bow = next(attack for attack in card["derived"]["attacks"] if attack["id"] == "longbow")
        self.assertEqual(bow["attack_bonus"], 6)
        self.assertEqual(bow["damage_bonus"], 2)
        self.assertEqual((bow["range_normal"], bow["range_long"]), (150, 600))
        self.assertEqual(card["resources"]["ammunition_arrow"]["current"], 20)
        self.assertIn({"id": "arrow", "quantity": 20}, card["equipment"])
        self.assertIn({"id": "shield", "quantity": 1}, card["equipment"])

    def test_archer_cannot_wield_bow_with_donned_shield_or_chain_package(self):
        data = hero()
        data.update(fighting_style="archery", armor="leather_armor", shield=True,
                    weapon="longbow")
        with self.assertRaises(character.CharacterError):
            character.build(data)
        data["shield"] = False
        data["armor"] = "chain_mail"
        with self.assertRaises(character.CharacterError):
            character.build(data)


if __name__ == "__main__":
    unittest.main()
