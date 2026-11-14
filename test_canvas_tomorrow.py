import unittest
from datetime import date

from canvas_tomorrow import collect_assignments_due_on


class CanvasTomorrowTests(unittest.TestCase):
    def test_collects_only_assignments_due_on_target_date(self):
        courses = [
            {"id": 101, "name": "HPM 530"},
            {"id": 202, "name": "ENGL 105"},
        ]
        assignments_by_course = {
            101: [
                {
                    "name": "Team Reflection",
                    "due_at": "2026-09-02T23:59:00Z",
                    "html_url": "https://canvas.unc.edu/courses/101/assignments/1",
                },
                {
                    "name": "Later Paper",
                    "due_at": "2026-09-03T23:59:00Z",
                    "html_url": "https://canvas.unc.edu/courses/101/assignments/2",
                },
            ],
            202: [
                {
                    "name": "Micro Memoir Revision",
                    "due_at": "2026-09-02T20:00:00Z",
                    "html_url": "https://canvas.unc.edu/courses/202/assignments/3",
                },
                {
                    "name": "No Due Date Draft",
                    "due_at": None,
                    "html_url": "https://canvas.unc.edu/courses/202/assignments/4",
                },
            ],
        }

        found = collect_assignments_due_on(
            courses, assignments_by_course, date(2026, 9, 2)
        )

        self.assertEqual(
            [item["name"] for item in found],
            ["Micro Memoir Revision", "Team Reflection"],
        )

    def test_uses_fallback_names_for_missing_fields(self):
        courses = [{"id": 101}]
        assignments_by_course = {
            101: [
                {
                    "due_at": "2026-09-02T23:59:00Z",
                }
            ]
        }

        found = collect_assignments_due_on(
            courses, assignments_by_course, date(2026, 9, 2)
        )

        self.assertEqual(found[0]["course"], "Unknown Course")
        self.assertEqual(found[0]["name"], "Untitled Assignment")


if __name__ == "__main__":
    unittest.main()
