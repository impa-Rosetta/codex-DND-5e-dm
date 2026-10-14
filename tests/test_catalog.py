import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "skills/codex-5e-dm/data/character-options.json"
SPEC = importlib.util.spec_from_file_location("catalog_character", ROOT / "skills/codex-5e-dm/scripts/character.py")
character = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(character)


class CatalogTests(unittest.TestCase):
    def test_catalog_has_stable_source_and_unique_ids(self):
        value = json.loads(DATA.read_text(encoding="utf-8"))
        self.assertEqual(value["ruleset"], "srd-5.1-2014")
        self.assertIn("SRD_CC_v5.1.pdf", value["source"])
        for group in ("races", "classes", "backgrounds"):
            ids = [item["id"] for item in value[group]]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertTrue(all(item["section"] for item in value[group]))
            self.assertTrue(all(item["status"] in ("indexed_only", "buildable") for item in value[group]))

    def test_catalog_does_not_call_unimplemented_options_buildable(self):
        value = character.options()
        self.assertEqual({item["id"] for item in value["races"] if item["status"] == "buildable"}, {"human"})
        self.assertEqual({item["id"] for item in value["classes"] if item["status"] == "buildable"},
                         {"fighter", "barbarian"})
        self.assertEqual({item["id"] for item in value["backgrounds"] if item["status"] == "buildable"}, {"acolyte"})


if __name__ == "__main__":
    unittest.main()
