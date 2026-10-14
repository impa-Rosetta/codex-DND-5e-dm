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
        self.assertEqual({c["id"] for c in value["classes"] if c["status"] == "buildable"},
                         {"fighter", "barbarian", "rogue", "monk", "paladin"})
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

    def test_human_barbarian_fixed_greataxe_route(self):
        data = hero()
        data.update(**{"class": "barbarian", "class_skills": ["athletics", "perception"],
                       "armor": "none", "shield": False, "weapon": "greataxe"})
        del data["fighting_style"]
        card = character.build(data)
        self.assertEqual(card["derived"]["max_hp"], 14)
        self.assertEqual(card["derived"]["ac"], 14)
        self.assertEqual(card["derived"]["hit_die"], "d12")
        self.assertEqual(card["derived"]["attacks"][0]["damage_die"], 12)
        self.assertEqual(card["resources"]["rage"]["current"], 2)
        self.assertEqual(card["resources"]["hit_dice_d12"]["current"], 1)
        self.assertIn("class.barbarian.rage", card["rule_ids"])
        self.assertIn({"id": "javelin", "quantity": 4}, card["equipment"])

    def test_barbarian_rejects_fighter_style_or_illegal_skill(self):
        data = hero()
        data.update(**{"class": "barbarian", "class_skills": ["athletics", "perception"],
                       "armor": "none", "shield": False, "weapon": "greataxe"})
        with self.assertRaises(character.CharacterError):
            character.build(data)

    def test_human_rogue_expertise_and_rapier(self):
        data = hero()
        data.update(**{"class": "rogue", "class_skills": ["acrobatics", "athletics", "perception", "stealth"],
                       "expertise": ["perception", "stealth"], "armor": "leather_armor",
                       "shield": False, "weapon": "rapier"})
        del data["fighting_style"]
        card = character.build(data)
        self.assertEqual(card["derived"]["max_hp"], 10)
        self.assertEqual(card["derived"]["ac"], 13)
        self.assertEqual(card["derived"]["hit_die"], "d8")
        self.assertEqual(card["derived"]["skills"]["perception"], 4)
        self.assertEqual(card["derived"]["saving_throws"]["dex"], 4)
        self.assertEqual(card["derived"]["attacks"][0]["attack_bonus"], 4)
        self.assertIn("thieves_cant", card["derived"]["languages"])
        self.assertIn("class.rogue.sneak_attack", card["rule_ids"])

    def test_rogue_rejects_invalid_expertise(self):
        data = hero()
        data.update(**{"class": "rogue", "class_skills": ["acrobatics", "athletics", "perception", "stealth"],
                       "expertise": ["perception", "arcana"], "armor": "leather_armor",
                       "shield": False, "weapon": "rapier"})
        del data["fighting_style"]
        with self.assertRaises(character.CharacterError):
            character.build(data)

    def test_human_monk_unarmored_martial_arts(self):
        data = hero()
        data.update(**{"class": "monk", "class_skills": ["acrobatics", "stealth"],
                       "monk_tool": "flute", "armor": "none", "shield": False,
                       "weapon": "shortsword"})
        del data["fighting_style"]
        card = character.build(data)
        self.assertEqual(card["derived"]["hit_die"], "d8")
        self.assertEqual(card["derived"]["max_hp"], 10)
        self.assertEqual(card["derived"]["ac"], 12)
        self.assertEqual(card["derived"]["attacks"][1]["damage_die"], 4)
        self.assertIn("class.monk.martial_arts", card["rule_ids"])
        self.assertIn("flute", card["derived"]["tool_proficiencies"])
        self.assertNotIn({"id": "flute", "quantity": 1}, card["equipment"])

    def test_human_paladin_lay_on_hands_and_divine_sense(self):
        data = hero()
        data.update(**{"class": "paladin", "class_skills": ["athletics", "medicine"],
                       "armor": "chain_mail", "shield": True, "weapon": "longsword"})
        del data["fighting_style"]
        data["base_abilities"]["cha"], data["base_abilities"]["int"] = 12, 8
        card = character.build(data)
        self.assertEqual(card["derived"]["ac"], 18)
        self.assertEqual(card["derived"]["hit_die"], "d10")
        self.assertEqual(card["derived"]["saving_throws"]["wis"], 2)
        self.assertEqual(card["resources"]["lay_on_hands"]["current"], 5)
        self.assertEqual(card["resources"]["divine_sense"]["current"], 2)
        self.assertNotIn("second_wind", card["resources"])


if __name__ == "__main__":
    unittest.main()
