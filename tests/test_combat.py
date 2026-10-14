import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/codex-5e-dm/scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("combat", SCRIPTS / "combat.py")
combat = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(combat)


class CombatTests(unittest.TestCase):
    def setUp(self):
        self.fight = {"turn_index": 0, "action_used": False, "combatants": [
            {"combatant_id": "hero", "name": "勇者", "hp": 12, "temp_hp": 0, "ac": 16},
            {"combatant_id": "goblin", "name": "哥布林", "hp": 7, "temp_hp": 3, "ac": 15}]}
        self.weapon = {"name": "长剑", "attack_bonus": 5, "damage_bonus": 3, "damage_die": 8}

    def test_hit_and_temporary_hp(self):
        values = iter([14, 6])
        result = combat.resolve_attack(self.fight, "hero", "goblin", self.weapon,
                                       roller=lambda _: next(values))
        self.assertTrue(result["hit"])
        self.assertEqual(result["damage"], 9)
        self.assertEqual(result["temp_hp_after"], 0)
        self.assertEqual(result["hp_after"], 1)

    def test_natural_one_misses_even_with_high_bonus(self):
        self.weapon["attack_bonus"] = 50
        result = combat.resolve_attack(self.fight, "hero", "goblin", self.weapon,
                                       roller=lambda _: 1)
        self.assertFalse(result["hit"])
        self.assertEqual(result["dice"][0]["natural_d20"], 1)

    def test_natural_twenty_doubles_dice_not_modifier(self):
        values = iter([20, 4, 5])
        result = combat.resolve_attack(self.fight, "hero", "goblin", self.weapon,
                                       roller=lambda _: next(values))
        self.assertTrue(result["critical"])
        self.assertEqual(result["damage"], 12)
        self.assertEqual(result["dice"][1]["raw"], [4, 5])

    def test_other_turn_and_used_action_rejected(self):
        with self.assertRaises(combat.CombatError):
            combat.resolve_attack(self.fight, "goblin", "hero", self.weapon)
        self.fight["action_used"] = True
        with self.assertRaises(combat.CombatError):
            combat.resolve_attack(self.fight, "hero", "goblin", self.weapon)

    def test_initiative_order(self):
        units = [{"combatant_id": "a", "initiative_bonus": 1},
                 {"combatant_id": "b", "initiative_bonus": 3}]
        values = iter([10, 10])
        result = combat.make_initiative(units, roller=lambda _: next(values))
        self.assertEqual(result["combatants"][0]["combatant_id"], "b")

    def test_tie_preserves_dm_selected_order_instead_of_dex_tiebreak(self):
        units = [{"combatant_id": "hero", "initiative_bonus": 1},
                 {"combatant_id": "goblin", "initiative_bonus": 3}]
        values = iter([12, 10])
        result = combat.make_initiative(units, roller=lambda _: next(values))
        self.assertEqual([unit["combatant_id"] for unit in result["combatants"]],
                         ["hero", "goblin"])

    def test_one_advantage_cancels_multiple_disadvantages(self):
        self.fight["combatants"][1]["dodging"] = True
        values = iter([14, 3])
        result = combat.resolve_attack(self.fight, "hero", "goblin", self.weapon,
                                       mode="advantage", extra_disadvantage=True,
                                       roller=lambda _: next(values))
        self.assertEqual(result["dice"][0]["raw"], [14])
        self.assertTrue(result["hit"])

    def test_sneak_attack_adds_die_only_on_effective_advantage(self):
        values = iter([10, 15, 2, 3])
        result = combat.resolve_attack(self.fight, "hero", "goblin", self.weapon,
                                       mode="advantage", sneak_attack_on_advantage=True,
                                       roller=lambda _: next(values))
        self.assertTrue(result["sneak_attack_used"])
        self.assertEqual(result["rolled_damage"], 8)
        self.fight["combatants"][1]["dodging"] = True
        values = iter([15, 2])
        canceled = combat.resolve_attack(self.fight, "hero", "goblin", self.weapon,
                                         mode="advantage", sneak_attack_on_advantage=True,
                                         roller=lambda _: next(values))
        self.assertFalse(canceled["sneak_attack_used"])
        self.assertEqual(len(canceled["dice"]), 2)

    def test_critical_sneak_attack_doubles_extra_die(self):
        values = iter([20, 10, 2, 3, 4, 5])
        result = combat.resolve_attack(self.fight, "hero", "goblin", self.weapon,
                                       mode="advantage", sneak_attack_on_advantage=True,
                                       roller=lambda _: next(values))
        self.assertTrue(result["critical"])
        self.assertEqual(result["dice"][-1]["raw"], [4, 5])
        self.assertEqual(result["rolled_damage"], 17)


if __name__ == "__main__":
    unittest.main()
