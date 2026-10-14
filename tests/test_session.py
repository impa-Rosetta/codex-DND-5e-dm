import importlib.util
import json
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

    def test_dueling_damage_is_used_by_persisted_encounter(self):
        duel_path = Path(self.temp.name) / "duel"
        state.create(duel_path, "决斗样例")
        choices = hero(); choices["fighting_style"] = "dueling"
        _, snapshot = state.confirm_character(duel_path, operation(), choices)
        hero_id = snapshot["character"]["id"]
        session.check(duel_path, operation(), "find_forest_path", roller=lambda _: 15)
        session.move_scene(duel_path, operation(), "forest_path")
        initiative = iter([20, 1])
        _, snapshot = session.start_encounter(duel_path, operation(),
                                              roller=lambda _: next(initiative))
        goblin_id = next(unit["combatant_id"] for unit in snapshot["combat"]["combatants"]
                         if unit["combatant_id"] != hero_id)
        dice = iter([10, 1])
        event, snapshot = session.attack(duel_path, operation(), goblin_id,
                                         roller=lambda _: next(dice))
        self.assertEqual(event["payload"]["damage"], 6)
        self.assertEqual(event["payload"]["hp_after"], 1)
        self.assertEqual(state.load(duel_path)[1]["combat"]["combatants"][1]["hp"], 1)

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

    def test_long_rest_restores_health_and_second_wind_after_encounter(self):
        self._reach_forest()
        initiative = iter([1, 20])
        session.start_encounter(self.path, operation(), roller=lambda _: next(initiative))
        goblin_attack = iter([20, 2, 2])
        _, snapshot = session.attack(self.path, operation(), self.hero_id,
                                     roller=lambda _: next(goblin_attack))
        self.assertEqual(snapshot["character"]["resources"]["hp"]["current"], 6)
        session.advance_turn(self.path, operation())
        session.second_wind(self.path, operation(), roller=lambda _: 1)
        goblin_id = next(unit["combatant_id"] for unit in snapshot["combat"]["combatants"]
                         if unit["combatant_id"] != self.hero_id)
        hero_attack = iter([20, 8, 8])
        session.attack(self.path, operation(), goblin_id,
                       roller=lambda _: next(hero_attack))
        session.end_encounter(self.path, operation())
        completed, snapshot = session.long_rest(self.path, operation())
        self.assertEqual(completed["type"], "rest.long_completed")
        self.assertEqual(snapshot["character"]["resources"]["hp"]["current"], 12)
        self.assertEqual(snapshot["character"]["resources"]["second_wind"]["current"], 1)
        self.assertEqual(snapshot["world_time"], 480)
        self.assertEqual(snapshot["last_long_rest_start"], 0)

    def test_long_rest_restores_hit_die_once_and_replays(self):
        session.short_rest(self.path, operation(), spend_hit_die=True, roller=lambda _: 1)
        state.commit(self.path, operation(), "resource.changed",
                     {"resource_id": "temp_hp", "after": 5})
        before = state.load(self.path)[1]
        self.assertEqual(before["character"]["resources"]["hit_dice_d10"]["current"], 0)
        rest_op = operation()
        first, snapshot = session.long_rest(self.path, rest_op)
        self.assertEqual(snapshot["character"]["resources"]["hit_dice_d10"]["current"], 1)
        self.assertEqual(snapshot["character"]["resources"]["temp_hp"]["current"], 0)
        self.assertEqual(snapshot["world_time"], 540)
        self.assertEqual(snapshot["last_long_rest_start"], 60)
        repeated, _ = session.long_rest(self.path, rest_op)
        self.assertEqual(first["event_id"], repeated["event_id"])
        with self.assertRaises(session.SessionError):
            session.long_rest(self.path, operation())
        (self.path / "state.json").write_text(json.dumps(before), encoding="utf-8")
        _, recovered, _ = state.load(self.path)
        self.assertEqual(recovered["world_time"], 540)
        self.assertEqual(recovered["last_long_rest_start"], 60)
        self.assertEqual(recovered["character"]["resources"]["hit_dice_d10"]["current"], 1)
        self.assertEqual(recovered["character"]["resources"]["temp_hp"]["current"], 0)

    def test_long_rest_can_benefit_again_after_twenty_four_hours(self):
        session.long_rest(self.path, operation())
        for _ in range(16):
            session.short_rest(self.path, operation())
        self.assertEqual(state.load(self.path)[1]["world_time"], 1440)
        _, snapshot = session.long_rest(self.path, operation())
        self.assertEqual(snapshot["world_time"], 1920)
        self.assertEqual(snapshot["last_long_rest_start"], 1440)

    def test_long_rest_rejects_combat_and_zero_hp(self):
        self._reach_forest()
        initiative = iter([20, 1])
        session.start_encounter(self.path, operation(), roller=lambda _: next(initiative))
        with self.assertRaises(session.SessionError):
            session.long_rest(self.path, operation())
        # A separate campaign fixture exercises the zero-HP precondition.
        other = Path(self.temp.name) / "unconscious"
        state.create(other, "昏迷")
        state.confirm_character(other, operation(), hero())
        state.commit(other, operation(), "resource.changed",
                     {"resource_id": "hp", "after": 0})
        with self.assertRaises(session.SessionError):
            session.long_rest(other, operation())

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

    def _start_hero_first(self):
        self._reach_forest()
        values = iter([20, 1])
        _, snapshot = session.start_encounter(self.path, operation(), roller=lambda _: next(values))
        return next(unit["combatant_id"] for unit in snapshot["combat"]["combatants"]
                    if unit["combatant_id"] != self.hero_id)

    def test_movement_disengage_and_replay(self):
        goblin_id = self._start_hero_first()
        action, snapshot = session.combat_action(self.path, operation(), "disengage")
        self.assertEqual(action["payload"]["action"], "disengage")
        self.assertTrue(snapshot["combat"]["action_used"])
        move_op = operation()
        moved, snapshot = session.move_combat(self.path, move_op, [[-1, 0]])
        self.assertEqual(snapshot["combat"]["combatants"][0]["position"], [-1, 0])
        self.assertEqual(snapshot["combat"]["movement_used"], 5)
        self.assertIsNone(moved["payload"]["opportunity_attack"])
        self.assertFalse(next(u for u in snapshot["combat"]["combatants"]
                              if u["combatant_id"] == goblin_id)["reaction_used"])
        repeated, _ = session.move_combat(self.path, move_op, [[99, 99]],
                                          roller=lambda _: self.fail("rerolled"))
        self.assertEqual(repeated["event_id"], moved["event_id"])
        self.assertEqual(state.load(self.path)[1]["combat"]["combatants"][0]["position"], [-1, 0])

    def test_leaving_reach_triggers_one_reaction_attack(self):
        goblin_id = self._start_hero_first()
        rolls = iter([15, 3])
        event, snapshot = session.move_combat(self.path, operation(), [[-1, 0]],
                                               roller=lambda _: next(rolls))
        oa = event["payload"]["opportunity_attack"]
        self.assertEqual(oa["actor_combatant_id"], goblin_id)
        self.assertEqual(oa["damage"], 5)
        self.assertEqual(snapshot["character"]["resources"]["hp"]["current"], 7)
        self.assertTrue(next(u for u in snapshot["combat"]["combatants"]
                             if u["combatant_id"] == goblin_id)["reaction_used"])
        self.assertEqual(snapshot["combat"]["combatants"][0]["position"], [-1, 0])
        session.move_combat(self.path, operation(), [[0, 0], [-1, 0]],
                            roller=lambda _: self.fail("second reaction"))
        self.assertEqual(state.load(self.path)[1]["character"]["resources"]["hp"]["current"], 7)

    def test_dash_and_invalid_movement_do_not_mutate_state(self):
        self._start_hero_first()
        before = state.load(self.path)[1]["revision"]
        for path in ([[1, 0]], [[2, 0]], [[0, 0]], [[0, True]]):
            with self.subTest(path=path), self.assertRaises(session.SessionError):
                session.move_combat(self.path, operation(), path)
        self.assertEqual(state.load(self.path)[1]["revision"], before)
        session.combat_action(self.path, operation(), "dash")
        path = [[0, i] for i in range(1, 13)]
        moved, snapshot = session.move_combat(self.path, operation(), path)
        self.assertEqual(moved["payload"]["feet"], 60)
        self.assertEqual(snapshot["combat"]["movement_used"], 60)
        with self.assertRaises(session.SessionError):
            session.move_combat(self.path, operation(), [[0, 13]])

    def test_dodge_disadvantages_next_attack_until_own_turn(self):
        self._start_hero_first()
        session.combat_action(self.path, operation(), "dodge")
        session.advance_turn(self.path, operation())
        rolls = iter([18, 2])
        event, snapshot = session.attack(self.path, operation(), self.hero_id,
                                          roller=lambda _: next(rolls))
        self.assertFalse(event["payload"]["hit"])
        self.assertEqual(event["payload"]["dice"][0]["raw"], [18, 2])
        self.assertEqual(snapshot["character"]["resources"]["hp"]["current"], 12)
        session.advance_turn(self.path, operation())
        self.assertFalse(next(u for u in state.load(self.path)[1]["combat"]["combatants"]
                              if u["combatant_id"] == self.hero_id)["dodging"])

    def test_opportunity_attack_can_stop_movement_at_zero_hp(self):
        self._reach_forest()
        initiative = iter([1, 20])
        session.start_encounter(self.path, operation(), roller=lambda _: next(initiative))
        first_hit = iter([20, 3, 4])
        _, snapshot = session.attack(self.path, operation(), self.hero_id,
                                     roller=lambda _: next(first_hit))
        self.assertEqual(snapshot["character"]["resources"]["hp"]["current"], 3)
        session.advance_turn(self.path, operation())
        rolls = iter([15, 3])
        event, snapshot = session.move_combat(self.path, operation(), [[-1, 0]],
                                               roller=lambda _: next(rolls))
        self.assertEqual(event["payload"]["feet"], 0)
        actor = next(u for u in snapshot["combat"]["combatants"] if u["combatant_id"] == self.hero_id)
        self.assertEqual(actor["position"], [0, 0])
        self.assertEqual(snapshot["character"]["resources"]["hp"]["current"], 0)
        self.assertEqual(snapshot["combat"]["death_saves"]["failures"], 0)
        self.assertEqual(next(u for u in state.load(self.path)[1]["combat"]["combatants"]
                              if u["combatant_id"] == self.hero_id)["position"], [0, 0])

    def test_melee_hit_against_unconscious_hero_is_critical_and_two_failures(self):
        self._knock_hero_unconscious()
        session.death_save(self.path, operation(), roller=lambda _: 10)
        session.advance_turn(self.path, operation())
        rolls = iter([15, 2, 2, 3])
        event, snapshot = session.attack(self.path, operation(), self.hero_id,
                                          roller=lambda _: next(rolls))
        self.assertTrue(event["payload"]["critical"])
        self.assertEqual(event["payload"]["dice"][0]["raw"], [15, 2])
        self.assertEqual(event["payload"]["damage"], 7)
        self.assertEqual(snapshot["combat"]["death_saves"]["failures"], 2)
        self.assertEqual(snapshot["combat"]["death_saves"]["successes"], 1)
        self.assertEqual(snapshot["character"]["resources"]["hp"]["current"], 0)
        self.assertEqual(state.load(self.path)[1]["combat"]["death_saves"]["failures"], 2)

    def test_damage_at_zero_equal_to_maximum_causes_instant_death(self):
        self._knock_hero_unconscious()
        session.death_save(self.path, operation(), roller=lambda _: 10)
        session.advance_turn(self.path, operation())
        rolls = iter([15, 2, 6, 6])
        _, snapshot = session.attack(self.path, operation(), self.hero_id,
                                     roller=lambda _: next(rolls))
        self.assertTrue(snapshot["combat"]["death_saves"]["dead"])
        _, snapshot = session.end_encounter(self.path, operation())
        self.assertEqual(snapshot["character"]["life_state"], "dead")

    def test_stable_hero_recovers_after_audited_hours_and_can_rest(self):
        self._knock_hero_unconscious()
        for index in range(3):
            if index:
                session.advance_turn(self.path, operation())
                session.advance_turn(self.path, operation())
            session.death_save(self.path, operation(), roller=lambda _: 10)
        session.end_encounter(self.path, operation())
        recover_op = operation()
        recovered, snapshot = session.recover_stable(self.path, recover_op, roller=lambda _: 4)
        self.assertEqual(recovered["payload"]["dice"][0]["raw"], [4])
        self.assertEqual(snapshot["world_time"], 240)
        self.assertEqual(snapshot["character"]["resources"]["hp"]["current"], 1)
        self.assertEqual(snapshot["character"]["life_state"], "alive")
        repeated, _ = session.recover_stable(self.path, recover_op,
                                              roller=lambda _: self.fail("rerolled"))
        self.assertEqual(recovered["event_id"], repeated["event_id"])
        self.assertEqual(state.load(self.path)[1]["character"]["resources"]["hp"]["current"], 1)
        session.short_rest(self.path, operation(), spend_hit_die=True, roller=lambda _: 5)

    def test_stable_recovery_rejects_conscious_hero(self):
        with self.assertRaises(session.SessionError):
            session.recover_stable(self.path, operation(), roller=lambda _: 1)

    def test_goblin_movement_requires_player_opportunity_choice(self):
        self._reach_forest()
        initiative = iter([1, 20])
        _, snapshot = session.start_encounter(self.path, operation(),
                                               roller=lambda _: next(initiative))
        goblin = snapshot["combat"]["combatants"][0]
        before = snapshot["revision"]
        with self.assertRaises(session.SessionError):
            session.move_combat(self.path, operation(), [[2, 0]])
        self.assertEqual(state.load(self.path)[1]["revision"], before)
        event, snapshot = session.move_combat(self.path, operation(), [[2, 0]],
                                               use_reaction=False)
        self.assertIsNone(event["payload"]["opportunity_attack"])
        self.assertEqual(snapshot["combat"]["combatants"][0]["position"], [2, 0])
        self.assertFalse(next(u for u in snapshot["combat"]["combatants"]
                              if u["combatant_id"] == self.hero_id)["reaction_used"])
        self.assertEqual(goblin["combatant_id"], snapshot["combat"]["combatants"][0]["combatant_id"])

    def test_player_opportunity_attack_is_audited_with_goblin_movement(self):
        self._reach_forest()
        initiative = iter([1, 20])
        session.start_encounter(self.path, operation(), roller=lambda _: next(initiative))
        rolls = iter([14, 2])
        event, snapshot = session.move_combat(self.path, operation(), [[2, 0]],
                                               use_reaction=True, roller=lambda _: next(rolls))
        self.assertEqual(event["payload"]["opportunity_attack"]["damage"], 5)
        self.assertEqual(snapshot["combat"]["combatants"][0]["hp"], 2)
        self.assertEqual(snapshot["combat"]["combatants"][0]["position"], [2, 0])
        self.assertTrue(next(u for u in snapshot["combat"]["combatants"]
                             if u["combatant_id"] == self.hero_id)["reaction_used"])
        self.assertEqual(state.load(self.path)[1]["combat"]["combatants"][0]["hp"], 2)
        manifest, reloaded, _ = state.load(self.path)
        public = state.public_snapshot(reloaded, manifest)
        self.assertEqual(public["combat"]["combatants"][0]["position"], [2, 0])
        self.assertTrue(next(u for u in public["combat"]["combatants"]
                             if u["combatant_id"] == self.hero_id)["reaction_used"])

    def test_player_opportunity_kill_stops_goblin_before_departure(self):
        self._reach_forest()
        initiative = iter([1, 20])
        session.start_encounter(self.path, operation(), roller=lambda _: next(initiative))
        rolls = iter([20, 5, 5])
        event, snapshot = session.move_combat(self.path, operation(), [[2, 0]],
                                               use_reaction=True, roller=lambda _: next(rolls))
        self.assertEqual(event["payload"]["feet"], 0)
        self.assertEqual(snapshot["combat"]["combatants"][0]["hp"], 0)
        self.assertEqual(snapshot["combat"]["combatants"][0]["position"], [1, 0])
        session.end_encounter(self.path, operation())

    def test_goblin_disengage_avoids_player_reaction(self):
        self._reach_forest()
        initiative = iter([1, 20])
        session.start_encounter(self.path, operation(), roller=lambda _: next(initiative))
        session.combat_action(self.path, operation(), "disengage")
        event, snapshot = session.move_combat(self.path, operation(), [[2, 0]])
        self.assertIsNone(event["payload"]["opportunity_attack"])
        self.assertEqual(snapshot["combat"]["combatants"][0]["position"], [2, 0])

    def test_archer_close_shot_has_disadvantage_and_consumes_one_arrow_once(self):
        archer_path = Path(self.temp.name) / "archer"
        state.create(archer_path, "弓箭战士")
        choices = hero()
        choices.update(fighting_style="archery", armor="leather_armor", shield=False,
                       weapon="longbow")
        state.confirm_character(archer_path, operation(), choices)
        session.check(archer_path, operation(), "find_forest_path", roller=lambda _: 15)
        session.move_scene(archer_path, operation(), "forest_path")
        initiative = iter([20, 1])
        _, snapshot = session.start_encounter(archer_path, operation(),
                                              roller=lambda _: next(initiative))
        goblin_id = next(unit["combatant_id"] for unit in snapshot["combat"]["combatants"]
                         if unit["combatant_id"] != snapshot["character"]["id"])
        op = operation()
        dice = iter([18, 2])
        shot, snapshot = session.attack(archer_path, op, goblin_id,
                                        roller=lambda _: next(dice))
        self.assertFalse(shot["payload"]["hit"])
        self.assertEqual(shot["payload"]["dice"][0]["raw"], [18, 2])
        self.assertEqual(snapshot["character"]["resources"]["ammunition_arrow"]["current"], 19)
        retry, _ = session.attack(archer_path, op, goblin_id,
                                  roller=lambda _: self.fail("rerolled"))
        self.assertEqual(retry["event_id"], shot["event_id"])
        self.assertEqual(state.load(archer_path)[1]["character"]["resources"]["ammunition_arrow"]["current"], 19)

    def test_archer_can_recover_half_expended_arrows_after_victory(self):
        archer_path = Path(self.temp.name) / "archer_recovery"
        state.create(archer_path, "战场找箭")
        choices = hero()
        choices.update(fighting_style="archery", armor="leather_armor", shield=False,
                       weapon="longbow")
        state.confirm_character(archer_path, operation(), choices)
        session.check(archer_path, operation(), "find_forest_path", roller=lambda _: 15)
        session.move_scene(archer_path, operation(), "forest_path")
        initiative = iter([20, 1])
        _, snapshot = session.start_encounter(archer_path, operation(),
                                              roller=lambda _: next(initiative))
        goblin_id = next(unit["combatant_id"] for unit in snapshot["combat"]["combatants"]
                         if unit["combatant_id"] != snapshot["character"]["id"])
        miss = iter([1, 1])
        session.attack(archer_path, operation(), goblin_id, roller=lambda _: next(miss))
        session.advance_turn(archer_path, operation())
        session.advance_turn(archer_path, operation())
        critical = iter([20, 20, 3, 3])
        _, snapshot = session.attack(archer_path, operation(), goblin_id,
                                     roller=lambda _: next(critical))
        self.assertEqual(snapshot["combat"]["combatants"][1]["hp"], 0)
        session.end_encounter(archer_path, operation())
        before = state.load(archer_path)[1]
        self.assertEqual(before["character"]["resources"]["ammunition_arrow"]["current"], 18)
        self.assertEqual(before["character"]["resources"]["recoverable_arrow"]["current"], 1)
        recovered, snapshot = session.search_battlefield(archer_path, operation())
        self.assertEqual(recovered["payload"]["recovered"], 1)
        self.assertEqual(snapshot["character"]["resources"]["ammunition_arrow"]["current"], 19)
        self.assertEqual(snapshot["character"]["resources"]["recoverable_arrow"]["current"], 0)
        self.assertEqual(snapshot["world_time"], 1)
        self.assertEqual(state.load(archer_path)[1]["character"]["resources"]["ammunition_arrow"]["current"], 19)

    def test_archer_shoots_normally_after_disengaging_to_ten_feet(self):
        archer_path = Path(self.temp.name) / "archer_range"
        state.create(archer_path, "十英尺长弓")
        choices = hero()
        choices.update(fighting_style="archery", armor="leather_armor", shield=False,
                       weapon="longbow")
        state.confirm_character(archer_path, operation(), choices)
        session.check(archer_path, operation(), "find_forest_path", roller=lambda _: 15)
        session.move_scene(archer_path, operation(), "forest_path")
        initiative = iter([20, 1])
        _, snapshot = session.start_encounter(archer_path, operation(),
                                              roller=lambda _: next(initiative))
        goblin_id = next(unit["combatant_id"] for unit in snapshot["combat"]["combatants"]
                         if unit["combatant_id"] != snapshot["character"]["id"])
        session.combat_action(archer_path, operation(), "disengage")
        session.move_combat(archer_path, operation(), [[-1, 0]])
        session.advance_turn(archer_path, operation())
        session.advance_turn(archer_path, operation())
        dice = iter([14, 4])
        shot, snapshot = session.attack(archer_path, operation(), goblin_id,
                                        roller=lambda _: next(dice))
        self.assertEqual(shot["payload"]["dice"][0]["raw"], [14])
        self.assertTrue(shot["payload"]["hit"])
        self.assertEqual(shot["payload"]["damage"], 6)
        self.assertEqual(snapshot["combat"]["combatants"][1]["hp"], 1)

    def _barbarian_campaign(self, name):
        barbarian_path = Path(self.temp.name) / name
        state.create(barbarian_path, "野蛮人")
        choices = hero()
        choices.update(**{"class": "barbarian", "armor": "none", "shield": False,
                          "weapon": "greataxe"})
        del choices["fighting_style"]
        state.confirm_character(barbarian_path, operation(), choices)
        session.check(barbarian_path, operation(), "find_forest_path", roller=lambda _: 15)
        session.move_scene(barbarian_path, operation(), "forest_path")
        return barbarian_path

    def test_barbarian_rage_damage_resistance_and_persistence(self):
        path = self._barbarian_campaign("barbarian_rage")
        initiative = iter([20, 1])
        _, snapshot = session.start_encounter(path, operation(), roller=lambda _: next(initiative))
        goblin_id = next(unit["combatant_id"] for unit in snapshot["combat"]["combatants"]
                         if unit["combatant_id"] != snapshot["character"]["id"])
        rage, snapshot = session.rage(path, operation())
        self.assertEqual(rage["type"], "barbarian.rage_started")
        self.assertEqual(snapshot["character"]["resources"]["rage"]["current"], 1)
        self.assertTrue(snapshot["combat"]["rage_active"])
        attack_rolls = iter([10, 1])
        attack, snapshot = session.attack(path, operation(), goblin_id,
                                          roller=lambda _: next(attack_rolls))
        self.assertEqual(attack["payload"]["damage"], 6)
        session.advance_turn(path, operation())
        goblin_rolls = iter([15, 5])
        hit, snapshot = session.attack(path, operation(), snapshot["character"]["id"],
                                       roller=lambda _: next(goblin_rolls))
        self.assertEqual(hit["payload"]["rolled_damage"], 7)
        self.assertEqual(hit["payload"]["damage"], 3)
        self.assertEqual(snapshot["character"]["resources"]["hp"]["current"], 11)
        self.assertTrue(state.load(path)[1]["combat"]["rage_active"])

    def test_barbarian_rage_ends_after_idle_turn_but_use_is_spent(self):
        path = self._barbarian_campaign("barbarian_idle")
        initiative = iter([20, 1])
        session.start_encounter(path, operation(), roller=lambda _: next(initiative))
        session.rage(path, operation())
        _, snapshot = session.advance_turn(path, operation())
        self.assertFalse(snapshot["combat"]["rage_active"])
        self.assertEqual(snapshot["character"]["resources"]["rage"]["current"], 1)
        self.assertFalse(state.load(path)[1]["combat"]["rage_active"])

    def test_barbarian_rage_is_one_bonus_action_and_is_replayable(self):
        path = self._barbarian_campaign("barbarian_retry")
        initiative = iter([20, 1])
        session.start_encounter(path, operation(), roller=lambda _: next(initiative))
        rage_id = operation()
        first, snapshot = session.rage(path, rage_id)
        repeated, snapshot = session.rage(path, rage_id)
        self.assertEqual(first["event_id"], repeated["event_id"])
        self.assertEqual(snapshot["character"]["resources"]["rage"]["current"], 1)
        with self.assertRaises(session.SessionError):
            session.rage(path, operation())
        manifest, reloaded, events = state.load(path)
        self.assertEqual(reloaded["revision"], len(events))
        self.assertTrue(state.public_snapshot(reloaded, manifest)["combat"]["rage_active"])

    def test_barbarian_cannot_use_second_wind(self):
        path = self._barbarian_campaign("barbarian_no_wind")
        initiative = iter([20, 1])
        session.start_encounter(path, operation(), roller=lambda _: next(initiative))
        with self.assertRaises(session.SessionError):
            session.second_wind(path, operation(), roller=lambda _: 5)

    def test_barbarian_d12_hit_die_and_long_rest_restore_rage(self):
        path = self._barbarian_campaign("barbarian_rest")
        # A fixed scenario battle is needed to spend a rage use.
        initiative = iter([20, 1])
        _, snapshot = session.start_encounter(path, operation(), roller=lambda _: next(initiative))
        goblin_id = next(unit["combatant_id"] for unit in snapshot["combat"]["combatants"]
                         if unit["combatant_id"] != snapshot["character"]["id"])
        session.rage(path, operation())
        kill = iter([20, 6, 6])
        session.attack(path, operation(), goblin_id, roller=lambda _: next(kill))
        session.end_encounter(path, operation())
        _, snapshot = session.short_rest(path, operation(), spend_hit_die=True,
                                         roller=lambda _: 5)
        self.assertEqual(snapshot["character"]["resources"]["hit_dice_d12"]["current"], 0)
        self.assertEqual(snapshot["character"]["resources"]["rage"]["current"], 1)
        _, snapshot = session.long_rest(path, operation())
        self.assertEqual(snapshot["character"]["resources"]["hit_dice_d12"]["current"], 1)
        self.assertEqual(snapshot["character"]["resources"]["rage"]["current"], 2)


if __name__ == "__main__":
    unittest.main()
