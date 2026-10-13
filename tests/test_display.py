import importlib.util
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/codex-5e-dm/scripts"
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("panel_server", ROOT / "skills/codex-5e-dm/display/server.py")
panel = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(panel)
import state


class DisplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.campaign = Path(self.temp.name) / "game"
        state.create(self.campaign, "面板测试")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), panel.handler_for(self.campaign))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def test_static_page_and_public_snapshot(self):
        with urllib.request.urlopen(self.base + "/") as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"Codex 5e DM", response.read())
        with urllib.request.urlopen(self.base + "/api/snapshot") as response:
            data = json.load(response)
            self.assertEqual(data["name"], "面板测试")
            self.assertNotIn("world", data)

    def test_mutation_and_raw_log_routes_closed(self):
        request = urllib.request.Request(self.base + "/api/snapshot", data=b"{}", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 405)
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.base + "/events.jsonl")
        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
