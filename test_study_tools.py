import unittest
from datetime import date, datetime, timezone

import tempfile

from study_agent import choose_tool_call
from study_memory import (
    is_assignment_muted,
    is_prep_muted,
    load_memory,
    mute_assignment,
    mute_prep,
)
from study_tools import (
    build_study_agenda,
    collect_prep_work,
    dedupe_and_rank_prep_work,
    discussion_status_from_entries,
    extract_specific_prep_tasks,
    fetch_module_item_text,
    filter_prep_courses,
    get_assignment_status,
    get_low_priority_reason,
)


NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


class StudyToolsTests(unittest.TestCase):
    def test_status_marks_submitted_assignment_as_submitted(self):
        assignment = {
            "due_at": "2026-09-03T23:59:00Z",
            "submission": {
                "workflow_state": "submitted",
                "submitted_at": "2026-09-02T10:00:00Z",
                "late": False,
            },
        }

        self.assertEqual(get_assignment_status(assignment, NOW), "submitted")

    def test_status_marks_past_unsubmitted_assignment_as_missing(self):
        assignment = {
            "due_at": "2026-09-01T23:59:00Z",
            "submission": {
                "workflow_state": "unsubmitted",
            },
        }

        self.assertEqual(get_assignment_status(assignment, NOW), "missing")

    def test_build_agenda_groups_by_urgency_and_status(self):
        courses = [{"id": 101, "name": "HPM 540"}]
        assignments_by_course = {
            101: [
                {
                    "name": "Old Missing Work",
                    "due_at": "2026-09-01T23:59:00Z",
                    "html_url": "https://canvas.example/old",
                    "submission": {"workflow_state": "unsubmitted"},
                },
                {
                    "name": "Today Work",
                    "due_at": "2026-09-02T23:59:00Z",
                    "html_url": "https://canvas.example/today",
                    "submission": {"workflow_state": "unsubmitted"},
                },
                {
                    "name": "Tomorrow Work",
                    "due_at": "2026-09-03T23:59:00Z",
                    "html_url": "https://canvas.example/tomorrow",
                    "submission": {"workflow_state": "unsubmitted"},
                },
                {
                    "name": "Submitted Work",
                    "due_at": "2026-09-03T20:00:00Z",
                    "html_url": "https://canvas.example/submitted",
                    "submission": {
                        "workflow_state": "submitted",
                        "submitted_at": "2026-09-02T10:00:00Z",
                    },
                },
            ]
        }

        agenda = build_study_agenda(courses, assignments_by_course, days=3, now=NOW)

        self.assertEqual(
            [item["name"] for item in agenda["overdue_missing"]],
            ["Old Missing Work"],
        )
        self.assertEqual([item["name"] for item in agenda["due_today"]], ["Today Work"])
        self.assertEqual(
            [item["name"] for item in agenda["due_tomorrow"]],
            ["Tomorrow Work"],
        )
        self.assertEqual(
            [item["name"] for item in agenda["submitted"]],
            ["Submitted Work"],
        )

    def test_old_missing_assignments_are_not_shown_by_default(self):
        courses = [{"id": 101, "name": "Old Course"}]
        assignments_by_course = {
            101: [
                {
                    "name": "Very Old Missing Work",
                    "due_at": "2026-04-01T23:59:00Z",
                    "submission": {"workflow_state": "unsubmitted"},
                }
            ]
        }

        agenda = build_study_agenda(courses, assignments_by_course, days=3, now=NOW)

        self.assertEqual(agenda["overdue_missing"], [])

    def test_week_question_chooses_seven_day_agenda_tool(self):
        tool_call = choose_tool_call("What should I do this week?")

        self.assertEqual(
            tool_call,
            {
                "tool": "get_study_agenda",
                "days": 7,
                "include_submitted": True,
                "include_prep": True,
            },
        )

    def test_tomorrow_question_chooses_one_day_agenda_tool(self):
        tool_call = choose_tool_call("What should I do tomorrow?")

        self.assertEqual(
            tool_call,
            {
                "tool": "get_study_agenda",
                "days": 1,
                "include_submitted": True,
                "include_prep": True,
            },
        )

    def test_due_question_keeps_prep_sources_off(self):
        tool_call = choose_tool_call("What is due tomorrow?")

        self.assertEqual(
            tool_call,
            {
                "tool": "get_study_agenda",
                "days": 1,
                "include_submitted": True,
                "include_prep": False,
            },
        )

    def test_food_question_does_not_choose_canvas_tool(self):
        tool_call = choose_tool_call("what should i eat tmrw")

        self.assertIsNone(tool_call)

    def test_reading_question_includes_prep_sources(self):
        tool_call = choose_tool_call("What readings do I have this week?")

        self.assertTrue(tool_call["include_prep"])
        self.assertEqual(tool_call["days"], 7)

    def test_optional_missing_assignment_goes_to_low_priority(self):
        courses = [{"id": 101, "name": "HPM 530"}]
        assignments_by_course = {
            101: [
                {
                    "id": 982708,
                    "name": "Optional Team Role Play due Sept 1 Psych Safety",
                    "due_at": "2026-09-01T15:30:00Z",
                    "points_possible": 100.0,
                    "submission": {"workflow_state": "unsubmitted"},
                }
            ]
        }

        agenda = build_study_agenda(courses, assignments_by_course, days=3, now=NOW)

        self.assertEqual(agenda["overdue_missing"], [])
        self.assertEqual(
            [item["name"] for item in agenda["low_priority"]],
            ["Optional Team Role Play due Sept 1 Psych Safety"],
        )

    def test_muted_assignment_is_hidden_from_agenda(self):
        courses = [{"id": 101, "name": "HPM 530"}]
        assignments_by_course = {
            101: [
                {
                    "id": 982708,
                    "name": "Optional Team Role Play due Sept 1 Psych Safety",
                    "due_at": "2026-09-01T15:30:00Z",
                    "submission": {"workflow_state": "unsubmitted"},
                }
            ]
        }

        agenda = build_study_agenda(
            courses,
            assignments_by_course,
            days=3,
            now=NOW,
            muted_assignment_ids=["982708"],
        )

        self.assertEqual(agenda["overdue_missing"], [])
        self.assertEqual(agenda["low_priority"], [])

    def test_old_low_priority_assignments_are_hidden_by_default(self):
        courses = [{"id": 101, "name": "Old Course"}]
        assignments_by_course = {
            101: [
                {
                    "id": 123,
                    "name": "Old 0 Point Survey",
                    "due_at": "2026-04-01T23:59:00Z",
                    "points_possible": 0,
                    "submission": {"workflow_state": "unsubmitted"},
                }
            ]
        }

        agenda = build_study_agenda(courses, assignments_by_course, days=3, now=NOW)

        self.assertEqual(agenda["low_priority"], [])

    def test_zero_point_assignment_is_low_priority(self):
        assignment = {
            "name": "Degree assessment",
            "points_possible": 0,
        }

        self.assertEqual(get_low_priority_reason(assignment), "Worth 0 points")

    def test_memory_can_mute_assignment(self):
        with tempfile.TemporaryDirectory() as directory:
            memory_path = f"{directory}/memory.json"

            mute_assignment(982708, path=memory_path)
            memory = load_memory(memory_path)

            self.assertTrue(is_assignment_muted(982708, memory))

    def test_memory_can_mute_prep_item(self):
        with tempfile.TemporaryDirectory() as directory:
            memory_path = f"{directory}/memory.json"

            mute_prep("101:discussion:opening-prompt", path=memory_path)
            memory = load_memory(memory_path)

            self.assertTrue(is_prep_muted("101:discussion:opening-prompt", memory))

    def test_module_item_with_completion_requirement_becomes_prep_work(self):
        courses = [{"id": 101, "name": "ENGL 105"}]
        modules_by_course = {
            101: [
                {
                    "name": "Week 3",
                    "items": [
                        {
                            "id": 301,
                            "title": "Read Baldwin before class",
                            "type": "Page",
                            "html_url": "https://canvas.example/pages/baldwin",
                            "completion_requirement": {"type": "must_view"},
                        }
                    ],
                }
            ]
        }

        prep_work = collect_prep_work(
            courses,
            modules_by_course=modules_by_course,
            discussions_by_course={},
            announcements=[],
            syllabus_by_course={},
            days=3,
            now=NOW,
        )

        self.assertEqual(prep_work[0]["course"], "ENGL 105")
        self.assertEqual(prep_work[0]["source_type"], "module")
        self.assertEqual(prep_work[0]["confidence"], "high")

    def test_ungraded_discussion_becomes_prep_work(self):
        courses = [{"id": 101, "name": "ENGL 105"}]
        discussions_by_course = {
            101: [
                {
                    "id": 401,
                    "title": "Week 3 discussion post",
                    "message": "<p>Post one response before Friday class.</p>",
                    "html_url": "https://canvas.example/discussions/401",
                    "assignment_id": None,
                }
            ]
        }

        prep_work = collect_prep_work(
            courses,
            modules_by_course={},
            discussions_by_course=discussions_by_course,
            announcements=[],
            syllabus_by_course={},
            days=3,
            now=NOW,
        )

        self.assertEqual(prep_work[0]["source_type"], "discussion")
        self.assertIn("discussion post", prep_work[0]["title"].lower())

    def test_generic_question_board_is_not_prep_work(self):
        courses = [{"id": 101, "name": "HPM 540"}]
        discussions_by_course = {
            101: [
                {
                    "id": 401,
                    "title": "Ask A Question",
                    "message": "<p>This is an ungraded discussion area that you can use to post general class questions.</p>",
                    "html_url": "https://canvas.example/discussions/401",
                    "assignment_id": None,
                }
            ]
        }

        prep_work = collect_prep_work(
            courses,
            modules_by_course={},
            discussions_by_course=discussions_by_course,
            announcements=[],
            syllabus_by_course={},
            days=3,
            now=NOW,
        )

        self.assertEqual(prep_work, [])

    def test_syllabus_text_with_action_and_time_signal_becomes_low_confidence_prep_work(self):
        courses = [{"id": 101, "name": "ENGL 105", "html_url": "https://canvas.example/courses/101"}]
        syllabus_by_course = {
            101: "<p>Each week, complete the reading before class and come prepared to discuss.</p>"
        }

        prep_work = collect_prep_work(
            courses,
            modules_by_course={},
            discussions_by_course={},
            announcements=[],
            syllabus_by_course=syllabus_by_course,
            days=3,
            now=NOW,
        )

        self.assertEqual(prep_work[0]["source_type"], "syllabus")
        self.assertEqual(prep_work[0]["confidence"], "low")

    def test_old_dated_discussion_is_not_prep_work_for_current_window(self):
        courses = [{"id": 101, "name": "ENGL 105"}]
        discussions_by_course = {
            101: [
                {
                    "id": 401,
                    "title": "Post for Tuesday, August 25",
                    "message": "<p>Post your response before class.</p>",
                    "html_url": "https://canvas.example/discussions/401",
                    "assignment_id": None,
                }
            ]
        }

        prep_work = collect_prep_work(
            courses,
            modules_by_course={},
            discussions_by_course=discussions_by_course,
            announcements=[],
            syllabus_by_course={},
            days=3,
            now=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(prep_work, [])

    def test_future_dated_module_is_prep_work_for_current_window(self):
        courses = [{"id": 101, "name": "HPM510.001.FA26"}]
        modules_by_course = {
            101: [
                {
                    "name": "Week 4: Emergency Preparedness (Sept. 8/10)",
                    "items": [
                        {
                            "id": 301,
                            "title": "Session 7 | Overview and Before Class",
                            "type": "Page",
                            "html_url": "https://canvas.example/modules/items/301",
                        }
                    ],
                }
            ]
        }

        prep_work = collect_prep_work(
            courses,
            modules_by_course=modules_by_course,
            discussions_by_course={},
            announcements=[],
            syllabus_by_course={},
            days=7,
            now=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(len(prep_work), 1)

    def test_prep_course_filter_keeps_current_fall_courses(self):
        courses = [
            {"id": 101, "name": "ENGL283.002.FA26"},
            {"id": 202, "name": "HBEH510.001.FA23"},
            {"id": 303, "name": "BSPH Program in HPM"},
        ]
        now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)

        filtered = filter_prep_courses(courses, now)

        self.assertEqual([course["id"] for course in filtered], [101])

    def test_extract_specific_prep_tasks_from_page_text(self):
        course = {"id": 101, "name": "ENGL283.002.FA26"}
        source = {
            "source_type": "page",
            "title": "Week 4 Before Class",
            "url": "https://canvas.example/pages/week-4",
            "text": "Before Tuesday class, read The Summer Day and post a short response. Optional: browse the extra links.",
        }

        tasks = extract_specific_prep_tasks(
            course,
            source,
            days=7,
            now=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["source_type"], "page")
        self.assertEqual(tasks[0]["confidence"], "high")
        self.assertIn("read The Summer Day", tasks[0]["evidence"])

    def test_fetch_module_item_text_reads_canvas_page_body(self):
        calls = []

        def fake_get_page_details(base_url, headers, course_id, page_url):
            calls.append((base_url, course_id, page_url))
            return {
                "title": "Week 4 Before Class",
                "body": "<p>Before Tuesday class, read Chapter 2.</p>",
                "html_url": "https://canvas.example/pages/week-4",
            }

        course = {"id": 101, "name": "ENGL283.002.FA26"}
        module = {"name": "Week 4"}
        item = {
            "title": "Week 4 Before Class",
            "type": "Page",
            "page_url": "week-4-before-class",
        }

        source = fetch_module_item_text(
            "https://canvas.example",
            {},
            course,
            module,
            item,
            page_fetcher=fake_get_page_details,
        )

        self.assertEqual(calls, [("https://canvas.example", 101, "week-4-before-class")])
        self.assertEqual(source["source_type"], "page")
        self.assertIn("read Chapter 2", source["text"])

    def test_specific_page_prep_hides_matching_module_reminder(self):
        prep_work = [
            {
                "course": "HPM510.001.FA26",
                "course_id": 101,
                "title": "Session 8 | Overview and Before Class",
                "source_type": "module",
                "status": "possible prep",
                "soft_deadline": "No Canvas due date found",
                "url": "https://canvas.example/modules/items/1",
                "confidence": "medium",
                "reason": "Module title looks like prep work",
                "evidence": "Week 4 Session 8 | Overview and Before Class",
            },
            {
                "course": "HPM510.001.FA26",
                "course_id": 101,
                "title": "Session 8 | Overview and Before Class",
                "source_type": "page",
                "status": "possible prep",
                "soft_deadline": "No Canvas due date found",
                "url": "https://canvas.example/pages/session-8",
                "confidence": "high",
                "reason": "Specific action found in linked course material",
                "evidence": "Before Thursday class, read the final rule.",
            },
        ]

        deduped = dedupe_and_rank_prep_work(prep_work)

        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["source_type"], "page")

    def test_discussion_status_marks_user_entry_as_posted(self):
        entries = [
            {"id": 1, "user_id": 10, "message": "Other student"},
            {"id": 2, "user_id": 42, "message": "My opening response"},
        ]

        status = discussion_status_from_entries(entries, current_user_id=42)

        self.assertEqual(status["completion_status"], "posted")

    def test_discussion_status_marks_absent_user_as_not_posted(self):
        entries = [{"id": 1, "user_id": 10, "message": "Other student"}]

        status = discussion_status_from_entries(entries, current_user_id=42)

        self.assertEqual(status["completion_status"], "not posted")


if __name__ == "__main__":
    unittest.main()
