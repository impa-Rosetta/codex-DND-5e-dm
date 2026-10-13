import importlib.util
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from test_character import hero


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("campaign_state", ROOT / "skills/codex-5e-dm/scripts/state.py")
state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(state)


class CampaignStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "campaign"
        state.create(self.path, "Test")

    def test_create_and_reload(self):
        manifest, snapshot, events = state.load(self.path)
        self.assertEqual(manifest["ruleset"], "srd-5.1-2014")
        self.assertEqual(snapshot["revision"], 0)
        self.assertEqual(events, [])

    def test_retry_does_not_duplicate_event(self):
        operation = str(uuid.uuid4())
        payload = {"public_view": {"summary": "Hello"}}
        first, _ = state.commit(self.path, operation, "scene.narrated", payload)
        second, snapshot = state.commit(self.path, operation, "scene.narrated", payload)
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(snapshot["revision"], 1)
        self.assertEqual(len(state.load(self.path)[2]), 1)

    def test_replay_unapplied_event_once(self):
        old_snapshot = state.load(self.path)[1]
        event, _ = state.commit(self.path, str(uuid.uuid4()), "location.discovered",
                                {"location_id": "forest", "public_view": {"summary": "Forest"}})
        (self.path / "state.json").write_text(json.dumps(old_snapshot), encoding="utf-8")
        _, repaired, _ = state.load(self.path)
        self.assertEqual(repaired["revision"], 1)
        self.assertEqual(repaired["last_applied_event_id"], event["event_id"])
        self.assertEqual(repaired["scene"]["discovered_locations"].count("forest"), 1)

    def test_truncated_log_is_rejected_without_mutation(self):
        log = self.path / "events.jsonl"
        log.write_bytes(b'{"partial":true}')
        snapshot = (self.path / "state.json").read_bytes()
        with self.assertRaises(state.StateError):
            state.load(self.path)
        self.assertEqual((self.path / "state.json").read_bytes(), snapshot)

    def test_public_projection_excludes_world_secret(self):
        manifest, snapshot, _ = state.load(self.path)
        snapshot["scene"]["secret_npc_plan"] = "ambush"
        snapshot["combat"] = {"round": 1, "turn_index": 0,
                              "combatants": [{"combatant_id": "goblin", "name": "Goblin", "hp": 7,
                                              "ac": 15, "secret_tactic": "retreat"}]}
        value = state.public_snapshot(snapshot, manifest)
        self.assertNotIn("world", value)
        self.assertNotIn("secret_npc_plan", value["scene"])
        self.assertNotIn("secret_tactic", value["combat"]["combatants"][0])
        self.assertEqual(value["scene"]["discovered_locations"], ["old_mill"])

    def test_confirm_character_is_idempotent_and_reloaded(self):
        operation = str(uuid.uuid4())
        event, snapshot = state.confirm_character(self.path, operation, hero())
        repeated, _ = state.confirm_character(self.path, operation, hero())
        self.assertEqual(event["event_id"], repeated["event_id"])
        self.assertEqual(snapshot["character"]["derived"]["ac"], 19)
        self.assertEqual(state.load(self.path)[1]["character"]["id"], snapshot["character"]["id"])

    def test_invalid_character_does_not_write_event(self):
        candidate = hero(); candidate["class"] = "wizard"
        with self.assertRaises(ValueError):
            state.confirm_character(self.path, str(uuid.uuid4()), candidate)
        self.assertEqual(state.load(self.path)[1]["revision"], 0)

    def test_roll_scores_are_audited_and_idempotent(self):
        operation = str(uuid.uuid4())
        draws = iter([6, 1, 4, 5] * 6)
        event, _ = state.roll_ability_scores(self.path, operation, roller=lambda _: next(draws))
        repeated, snapshot = state.roll_ability_scores(self.path, operation,
                                                       roller=lambda _: self.fail("retry rolled again"))
        self.assertEqual(event["event_id"], repeated["event_id"])
        self.assertEqual(snapshot["revision"], 1)
        self.assertEqual(event["payload"]["groups"][0],
                         {"raw": [6, 1, 4, 5], "dropped_index": 1,
                          "kept": [6, 4, 5], "total": 15})

    def test_rolled_character_requires_campaign_event(self):
        candidate = hero()
        candidate["ability_method"] = "rolled"
        candidate.pop("base_abilities")
        candidate["rolled_assignment"] = dict(zip(("str", "dex", "con", "int", "wis", "cha"), range(6)))
        candidate["roll_event_id"] = str(uuid.uuid4())
        with self.assertRaises(state.StateError):
            state.preview_character(self.path, candidate)
        event, _ = state.roll_ability_scores(self.path, str(uuid.uuid4()), roller=lambda _: 4)
        candidate["roll_event_id"] = event["event_id"]
        card = state.preview_character(self.path, candidate)
        self.assertEqual(card["derived"]["abilities"]["str"], 13)
        self.assertEqual(state.load(self.path)[1]["character"], None)
        committed, snapshot = state.confirm_character(self.path, str(uuid.uuid4()), candidate)
        self.assertEqual(committed["type"], "character.created")
        self.assertEqual(snapshot["character"]["source_choices"]["roll_event_id"], event["event_id"])


if __name__ == "__main__":
    unittest.main()
