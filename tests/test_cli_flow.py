import json
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from test_character import hero

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/codex-5e-dm/scripts"


class CliFlowTests(unittest.TestCase):
    def test_create_preview_confirm_reload_from_other_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            campaign = root / "game"
            choices = root / "choices.json"
            choices.write_text(json.dumps(hero()), encoding="utf-8")

            def run(script, *args):
                result = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                                        cwd=root, text=True, capture_output=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)

            run("state.py", "create", campaign, "--name", "旧磨坊")
            option_list = run("character.py", "options")
            self.assertEqual(option_list["ruleset"], "srd-5.1-2014")
            preview = run("character.py", "build", "--input", choices)
            self.assertEqual(preview["derived"]["max_hp"], 12)
            self.assertEqual(run("state.py", "load", campaign)["character"], None)
            operation = str(uuid.uuid4())
            confirmed = run("state.py", "confirm-character", campaign, "--operation-id", operation,
                            "--input", choices)
            again = run("state.py", "confirm-character", campaign, "--operation-id", operation,
                        "--input", choices)
            self.assertEqual(confirmed["event"]["event_id"], again["event"]["event_id"])
            self.assertEqual(run("state.py", "load", campaign)["character"]["id"],
                             confirmed["state"]["character"]["id"])
            rest_operation = str(uuid.uuid4())
            rested = run("session.py", campaign, "long-rest", "--operation-id", rest_operation)
            repeated = run("session.py", campaign, "long-rest", "--operation-id", rest_operation)
            self.assertEqual(rested["event"]["event_id"], repeated["event"]["event_id"])
            self.assertEqual(run("state.py", "load", campaign)["world_time"], 480)


if __name__ == "__main__":
    unittest.main()
