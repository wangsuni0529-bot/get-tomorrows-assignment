import json
import os
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from study_agent.web import (
    canvas_is_configured,
    filter_agenda_sources,
    mode_to_include_prep,
    parse_bool,
    parse_days,
    parse_source_types,
    serialize_agenda,
)


class WebServerTests(unittest.TestCase):
    def test_parse_days_accepts_small_window(self):
        self.assertEqual(parse_days("7"), 7)

    def test_parse_days_rejects_large_window(self):
        with self.assertRaises(ValueError):
            parse_days("90")

    def test_parse_bool_accepts_common_true_values(self):
        self.assertTrue(parse_bool("true"))
        self.assertTrue(parse_bool("1"))
        self.assertTrue(parse_bool("yes"))

    def test_mode_to_include_prep(self):
        self.assertFalse(mode_to_include_prep("focused"))
        self.assertTrue(mode_to_include_prep("balanced"))
        self.assertTrue(mode_to_include_prep("catch_all"))

    def test_parse_source_types_filters_unknown_values(self):
        self.assertEqual(
            parse_source_types("discussion,syllabus,banana"),
            {"discussion", "syllabus"},
        )

    def test_filter_agenda_sources_hides_excluded_prep_items(self):
        agenda = {
            "prep_work": [
                {"source_type": "discussion", "title": "Opening Prompt"},
                {"source_type": "syllabus", "title": "Reading expectation"},
            ]
        }

        filtered = filter_agenda_sources(agenda, {"discussion"})

        self.assertEqual(
            [item["title"] for item in filtered["prep_work"]],
            ["Opening Prompt"],
        )

    def test_serialize_agenda_returns_json_safe_dates(self):
        agenda = {
            "generated_at": datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
            "days": 1,
            "overdue_missing": [],
            "due_today": [
                {
                    "course": "HPM 540",
                    "assignment_id": 123,
                    "name": "Problem Set",
                    "status": "unsubmitted",
                    "due": datetime(2026, 9, 13, 23, 59, tzinfo=UTC),
                    "url": "https://canvas.example/assignments/1",
                    "points": 10,
                    "priority": "normal",
                    "priority_reason": "Canvas hard-deadline assignment",
                }
            ],
            "due_tomorrow": [],
            "next_days": [],
            "low_priority": [],
            "prep_work": [],
            "prep_warnings": [],
            "submitted": [],
        }

        payload = serialize_agenda(agenda)

        json.dumps(payload)
        self.assertEqual(
            payload["sections"][1]["items"][0]["dueLabel"],
            "Sun Sep 13 2026, 11:59 PM",
        )
        self.assertEqual(payload["sections"][1]["items"][0]["assignmentId"], 123)

    def test_serialize_agenda_returns_prep_key(self):
        agenda = {
            "generated_at": datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
            "days": 1,
            "overdue_missing": [],
            "due_today": [],
            "due_tomorrow": [],
            "next_days": [],
            "low_priority": [],
            "prep_work": [
                {
                    "prep_key": "101|discussion|opening prompt|https://canvas.example/d/1",
                    "course": "ENGL 283",
                    "title": "Opening Prompt",
                    "status": "possible prep",
                    "soft_deadline": "No Canvas due date found",
                    "url": "https://canvas.example/d/1",
                    "source_type": "discussion",
                    "confidence": "medium",
                    "reason": "Ungraded Canvas discussion topic",
                    "evidence": "Respond before class.",
                }
            ],
            "prep_warnings": [],
            "submitted": [],
        }

        payload = serialize_agenda(agenda)

        self.assertEqual(
            payload["sections"][4]["items"][0]["prepKey"],
            "101|discussion|opening prompt|https://canvas.example/d/1",
        )

    def test_canvas_is_not_configured_when_the_token_is_missing(self):
        with patch.dict(os.environ, {"CANVAS_BASE_URL": "", "CANVAS_TOKEN": ""}, clear=False):
            self.assertFalse(canvas_is_configured())

    def test_canvas_is_configured_when_url_and_token_are_set(self):
        env = {
            "CANVAS_BASE_URL": "https://canvas.example",
            "CANVAS_TOKEN": "not-a-real-token",
        }
        with patch.dict(os.environ, env, clear=False):
            self.assertTrue(canvas_is_configured())


if __name__ == "__main__":
    unittest.main()
