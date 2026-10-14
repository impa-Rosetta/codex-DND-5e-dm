import importlib.util
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from test_character import hero

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/codex-5e-dm/scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("game_session", SCRIPTS / "session.py")
session = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session)
import state


def operation():
    return str(uuid.uuid4())


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "game"
        state.create(self.path, "旧磨坊")
        self.created, self.snapshot = state.confirm_character(self.path, operation(), hero())
        self.hero_id = self.snapshot["character"]["id"]

    def _reach_forest(self):
        event, snapshot = session.check(self.path, operation(), "find_forest_path", roller=lambda _: 15)
        self.assertTrue(event["payload"]["success"])
        self.assertIn("forest_path", snapshot["scene"]["discovered_locations"])
        session.move_scene(self.path, operation(), "forest_path")

    def test_full_original_encounter_and_reload(self):
        declaration, _ = session.declare(self.path, operation(), "我先询问磨坊主的女儿。")
        self.assertEqual(declaration["type"], "player.declared")
        self._reach_forest()
        values = iter([20, 1])
        started, snapshot = session.start_encounter(self.path, operation(), roller=lambda _: next(values))
        self.assertEqual(started["type"], "combat.started")
        self.assertEqual(snapshot["combat"]["combatants"][0]["combatant_id"], self.hero_id)
        goblin_id = next(unit["combatant_id"] for unit in snapshot["combat"]["combatants"]
                         if unit["combatant_id"] != self.hero_id)
        attack_values = iter([14, 7])
        hit, snapshot = session.attack(self.path, operation(), goblin_id,
                                       roller=lambda _: next(attack_values))
        self.assertEqual(hit["payload"]["hp_after"], 0)
        self.assertEqual(snapshot["combat"]["combatants"][1]["hp"], 0)
        ended, snapshot = session.end_encounter(self.path, operation())
        self.assertEqual(ended["type"], "combat.ended")
        self.assertIsNone(snapshot["combat"])
        rested, snapshot = session.short_rest(self.path, operation(), spend_hit_die=False)
        self.assertEqual(rested["type"], "rest.short_completed")
        self.assertEqual(snapshot["world_time"], 60)
        manifest, reloaded, events = state.load(self.path)
        public = state.public_snapshot(reloaded, manifest)
        self.assertEqual(public["revision"], len(events))
        self.assertEqual(public["last_applied_event_id"], rested["event_id"])
        self.assertEqual(public["scene"]["location_id"], "forest_path")

    def test_check_does_not_auto_succeed_on_natural_twenty_or_one(self):
        failed, snapshot = session.check(self.path, operation(), "find_forest_path", roller=lambda _: 1)
        self.assertFalse(failed["payload"]["success"])
        self.assertNotIn("forest_path", snapshot["scene"]["discovered_locations"])
        succeeded, _ = session.check(self.path, operation(), "find_forest_path", roller=lambda _: 20)
        self.assertTrue(succeeded["payload"]["success"])

    def test_second_wind_uses_bonus_action_and_retry_does_not_reroll(self):
        self._reach_forest()
        values = iter([1, 20])
        _, snapshot = session.start_encounter(self.path, operation(), roller=lambda _: next(values))
        self.assertNotEqual(snapshot["combat"]["combatants"][0]["combatant_id"], self.hero_id)
        goblin_attack = iter([20, 2, 3])
        _, snapshot = session.attack(self.path, operation(), self.hero_id,
                                     roller=lambda _: next(goblin_attack))
        self.assertLess(snapshot["character"]["resources"]["hp"]["current"], 12)
        session.advance_turn(self.path, operation())
        wind_op = operation()
        wind, snapshot = session.second_wind(self.path, wind_op, roller=lambda _: 5)
        self.assertEqual(wind["payload"]["dice"][0]["total"], 6)
        self.assertEqual(snapshot["character"]["resources"]["second_wind"]["current"], 0)
        repeated, _ = session.second_wind(self.path, wind_op,
                                          roller=lambda _: self.fail("rerolled"))
        self.assertEqual(wind["event_id"], repeated["event_id"])
        with self.assertRaises(session.SessionError):
            session.second_wind(self.path, operation(), roller=lambda _: 5)

    def test_cannot_start_encounter_before_discovery(self):
        with self.assertRaises(session.SessionError):
            session.start_encounter(self.path, operation(), roller=lambda _: 10)

    def test_short_rest_spends_one_hit_die_and_restores_second_wind(self):
        self._reach_forest()
        values = iter([1, 20])
        _, snapshot = session.start_encounter(self.path, operation(), roller=lambda _: next(values))
        goblin_attack = iter([14, 2])
        session.attack(self.path, operation(), self.hero_id,
                       roller=lambda _: next(goblin_attack))
        session.advance_turn(self.path, operation())
        session.second_wind(self.path, operation(), roller=lambda _: 1)
        self.assertEqual(state.load(self.path)[1]["character"]["resources"]["second_wind"]["current"], 0)
        with self.assertRaises(session.SessionError):
            session.short_rest(self.path, operation(), spend_hit_die=True, roller=lambda _: 5)
        hero_attack = iter([20, 8, 8])
        _, snapshot = session.attack(self.path, operation(),
                                     next(unit["combatant_id"] for unit in snapshot["combat"]["combatants"]
                                          if unit["combatant_id"] != self.hero_id),
                                     roller=lambda _: next(hero_attack))
        session.end_encounter(self.path, operation())
        rest, snapshot = session.short_rest(self.path, operation(), spend_hit_die=True,
                                            roller=lambda _: 5)
        self.assertEqual(rest["payload"]["dice"][0]["raw"], [5])
        self.assertEqual(snapshot["character"]["resources"]["hit_dice_d10"]["current"], 0)
        self.assertEqual(snapshot["character"]["resources"]["second_wind"]["current"], 1)

    def _knock_hero_unconscious(self):
        self._reach_forest()
        values = iter([1, 20])
        session.start_encounter(self.path, operation(), roller=lambda _: next(values))
        hit = iter([20, 6, 6])
        _, snapshot = session.attack(self.path, operation(), self.hero_id,
                                     roller=lambda _: next(hit))
        self.assertEqual(snapshot["character"]["resources"]["hp"]["current"], 0)
        return session.advance_turn(self.path, operation())[1]

    def test_death_save_one_counts_two_failures_and_third_failure_ends_run(self):
        snapshot = self._knock_hero_unconscious()
        self.assertEqual(snapshot["combat"]["combatants"][snapshot["combat"]["turn_index"]]
                         ["combatant_id"], self.hero_id)
        save_op = operation()
        saved, snapshot = session.death_save(self.path, save_op, roller=lambda _: 1)
        self.assertEqual(snapshot["combat"]["death_saves"]["failures"], 2)
        public = state.public_snapshot(snapshot, state.load(self.path)[0])
        self.assertEqual(public["combat"]["death_saves"]["failures"], 2)
        repeated, _ = session.death_save(self.path, save_op,
                                         roller=lambda _: self.fail("rerolled"))
        self.assertEqual(repeated["event_id"], saved["event_id"])
        with self.assertRaises(session.SessionError):
            session.death_save(self.path, operation(), roller=lambda _: 10)
        session.advance_turn(self.path, operation())
        session.advance_turn(self.path, operation())
        _, snapshot = session.death_save(self.path, operation(), roller=lambda _: 9)
        self.assertTrue(snapshot["combat"]["death_saves"]["dead"])
        ended, snapshot = session.end_encounter(self.path, operation())
        self.assertEqual(ended["payload"]["outcome"], "defeat_dead")
        self.assertEqual(snapshot["character"]["life_state"], "dead")
        self.assertEqual(state.load(self.path)[1]["character"]["life_state"], "dead")

    def test_natural_twenty_death_save_revives_at_one_hp(self):
        self._knock_hero_unconscious()
        _, snapshot = session.death_save(self.path, operation(), roller=lambda _: 20)
        self.assertEqual(snapshot["character"]["resources"]["hp"]["current"], 1)
        self.assertIsNone(snapshot["combat"]["death_saves"])

    def test_cannot_skip_required_death_save(self):
        self._knock_hero_unconscious()
        with self.assertRaises(session.SessionError):
            session.advance_turn(self.path, operation())

    def test_massive_damage_causes_instant_death(self):
        self._reach_forest()
        initiative = iter([1, 20])
        session.start_encounter(self.path, operation(), roller=lambda _: next(initiative))
        first = iter([20, 2, 2])
        session.attack(self.path, operation(), self.hero_id,
                       roller=lambda _: next(first))
        session.advance_turn(self.path, operation())
        session.advance_turn(self.path, operation())
        second = iter([15, 3])
        session.attack(self.path, operation(), self.hero_id,
                       roller=lambda _: next(second))
        session.advance_turn(self.path, operation())
        session.advance_turn(self.path, operation())
        final = iter([20, 6, 6])
        _, snapshot = session.attack(self.path, operation(), self.hero_id,
                                     roller=lambda _: next(final))
        self.assertTrue(snapshot["combat"]["death_saves"]["dead"])
        _, snapshot = session.end_encounter(self.path, operation())
        self.assertEqual(snapshot["character"]["life_state"], "dead")

    def test_three_successes_stabilize_and_allow_defeat_exit(self):
        self._knock_hero_unconscious()
        for index in range(3):
            if index:
                session.advance_turn(self.path, operation())
                session.advance_turn(self.path, operation())
            _, snapshot = session.death_save(self.path, operation(), roller=lambda _: 10)
        self.assertTrue(snapshot["combat"]["death_saves"]["stable"])
        self.assertEqual(snapshot["combat"]["death_saves"]["successes"], 0)
        _, snapshot = session.end_encounter(self.path, operation())
        self.assertEqual(snapshot["character"]["life_state"], "stable")


if __name__ == "__main__":
    unittest.main()
