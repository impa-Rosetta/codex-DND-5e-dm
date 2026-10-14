import importlib.util
import unittest
from pathlib import Path

from test_character import character, hero

SCRIPT = Path(__file__).resolve().parents[1] / "skills/codex-5e-dm/scripts/spells.py"
SPEC = importlib.util.spec_from_file_location("spells", SCRIPT)
spells = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(spells)


class SpellTests(unittest.TestCase):
    def setUp(self):
        choices = hero()
        choices.update(**{"class": "warlock", "class_skills": ["arcana", "deception"],
                          "patron": "fiend", "cantrips": ["eldritch_blast", "poison_spray"],
                          "spells_known": ["burning_hands", "comprehend_languages"],
                          "armor": "leather_armor", "shield": False, "weapon": "dagger"})
        del choices["fighting_style"]
        choices["base_abilities"]["str"], choices["base_abilities"]["cha"] = 8, 15
        self.caster = character.build(choices)
        self.caster["id"] = "hero"
        self.target = {"combatant_id": "goblin", "name": "哥布林", "ac": 15,
                       "hp": 7, "temp_hp": 0}

    def test_poison_spray_successful_save_negates_damage(self):
        rolls = iter([15, 10])
        outcome = spells.resolve_save_spell("poison_spray", self.caster, self.target, 0,
                                            roller=lambda _: next(rolls))
        self.assertTrue(outcome["saved"])
        self.assertEqual(outcome["damage"], 0)
        self.assertEqual(outcome["hp_after"], 7)
        self.assertEqual([die["raw"] for die in outcome["dice"]], [[15], [10]])

    def test_burning_hands_halves_after_successful_save(self):
        rolls = iter([11, 3, 3, 3])
        outcome = spells.resolve_save_spell("burning_hands", self.caster, self.target, 2,
                                            roller=lambda _: next(rolls))
        self.assertTrue(outcome["saved"])
        self.assertEqual(outcome["rolled_damage"], 9)
        self.assertEqual(outcome["damage"], 4)
        self.assertEqual(outcome["hp_after"], 3)

    def test_magic_missile_three_audited_darts(self):
        rolls = iter([1, 2, 3])
        outcome = spells.resolve_magic_missile(self.caster, self.target,
                                               roller=lambda _: next(rolls))
        self.assertEqual([die["raw"] for die in outcome["dice"]], [[1], [2], [3]])
        self.assertEqual(outcome["damage"], 9)
        self.assertEqual(outcome["hp_after"], 0)


if __name__ == "__main__":
    unittest.main()
