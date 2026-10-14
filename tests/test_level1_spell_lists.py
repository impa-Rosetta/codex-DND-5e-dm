"""Guard the transcribed SRD 5.1 first-level spell-list index."""

import json
import unittest
from pathlib import Path


PATH = Path(__file__).resolve().parents[1] / "skills/codex-5e-dm/data/level1-spell-lists.json"
EXPECTED_COUNTS = {
    "bard": (9, 20),
    "cleric": (7, 15),
    "druid": (7, 16),
    "sorcerer": (14, 17),
    "warlock": (7, 7),
    "wizard": (14, 27),
}


class LevelOneSpellListTests(unittest.TestCase):
    def test_srd_list_entries_are_unique_and_not_buildable(self):
        data = json.loads(PATH.read_text(encoding="utf-8"))
        self.assertEqual(data["ruleset"], "srd-5.1-2014")
        self.assertEqual(data["status"], "indexed_only")
        self.assertEqual(set(data["class_lists"]), set(EXPECTED_COUNTS))
        for class_id, (cantrip_count, spell_count) in EXPECTED_COUNTS.items():
            entry = data["class_lists"][class_id]
            with self.subTest(class_id=class_id):
                self.assertIn("Spell Lists >", entry["section"])
                self.assertEqual(len(entry["cantrips"]), cantrip_count)
                self.assertEqual(len(entry["level1"]), spell_count)
                self.assertEqual(len(set(entry["cantrips"])), cantrip_count)
                self.assertEqual(len(set(entry["level1"])), spell_count)
                self.assertTrue(all(item == item.lower() and " " not in item
                                    for item in entry["cantrips"] + entry["level1"]))
        self.assertIn("eldritch_blast", data["class_lists"]["warlock"]["cantrips"])
        self.assertIn("find_familiar", data["class_lists"]["wizard"]["level1"])
        self.assertNotIn("eldritch_blast", data["class_lists"]["wizard"]["cantrips"])


if __name__ == "__main__":
    unittest.main()
