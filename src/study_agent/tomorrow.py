"""Print assignments due tomorrow.

This is the original narrow command. The agenda command is the one to use
when you want status, priority, and prep.
"""

import sys
from datetime import date, datetime, timedelta
from typing import Any

from study_agent.client import get_assignments, get_canvas_config, get_courses
from study_agent.normalize import parse_canvas_datetime


def get_tomorrow(now: datetime | None = None) -> date:
    """Return tomorrow's calendar date in the local timezone."""
    current = now or datetime.now().astimezone()
    return current.date() + timedelta(days=1)


def collect_assignments_due_on(
    courses: list[dict[str, Any]],
    assignments_by_course: dict[Any, list[dict[str, Any]]],
    target_date: date,
) -> list[dict[str, Any]]:
    """Return assignments whose due date falls on ``target_date``, earliest first."""
    found = []

    for course in courses:
        course_id = course["id"]
        course_name = course.get("name") or "Unknown Course"

        for assignment in assignments_by_course.get(course_id, []):
            due_datetime = parse_canvas_datetime(assignment.get("due_at"))

            if not due_datetime or due_datetime.date() != target_date:
                continue

            found.append(
                {
                    "course": course_name,
                    "name": assignment.get("name") or "Untitled Assignment",
                    "due": due_datetime,
                    "url": assignment.get("html_url") or "",
                }
            )

    return sorted(found, key=lambda item: item["due"])


def print_assignments(found: list[dict[str, Any]], target_date: date) -> None:
    """Print the tomorrow list."""
    print()
    print(f"Assignments due tomorrow: {target_date}")
    print("=" * 60)

    if not found:
        print("Nothing due tomorrow.")
        return

    for item in found:
        print()
        print(f"Course: {item['course']}")
        print(f"Assignment: {item['name']}")
        print(f"Due: {item['due'].strftime('%I:%M %p')}")
        print(f"Link: {item['url']}")

    print()
    print("=" * 60)
    print(f"Total: {len(found)} assignment(s)")


def main() -> None:
    """Fetch Canvas and print assignments due tomorrow."""
    try:
        base_url, token = get_canvas_config()
        headers = {"Authorization": f"Bearer {token}"}
        target_date = get_tomorrow()

        courses = get_courses(base_url, headers)
        assignments_by_course = {
            course["id"]: get_assignments(base_url, headers, course["id"])
            for course in courses
            if "id" in course
        }

        found = collect_assignments_due_on(courses, assignments_by_course, target_date)
        print_assignments(found, target_date)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
