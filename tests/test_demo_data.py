"""The public demo has to keep telling a recognizable, fictional story."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO_PATH = ROOT / "frontend" / "demo-data.json"


class DemoDataTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(DEMO_PATH.read_text())

    def test_sample_covers_deadlines_prep_and_low_priority(self):
        assignments = self.data["assignments"]
        offsets = [item["offsetDays"] for item in assignments]

        self.assertTrue(any(offset < 0 for offset in offsets))
        self.assertTrue(any(item["priority"] == "low" for item in assignments))
        self.assertGreaterEqual(len({item["course"] for item in assignments}), 3)
        self.assertIn("Demo", assignments[0]["course"])

        sources = {item["sourceType"] for item in self.data["prep"]}
        self.assertTrue({"discussion", "page", "syllabus"} <= sources)

    def test_sample_does_not_pretend_to_be_a_real_account(self):
        blob = json.dumps(self.data)
        self.assertIn("fictional", self.data["notice"].lower())
        self.assertNotIn("CANVAS_TOKEN", blob)
