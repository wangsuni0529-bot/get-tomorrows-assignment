"""Group normalized assignments into an agenda and print or return it.

Fetching lives in the Canvas client. Deciding which bucket an item belongs in
lives here.
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from typing import Any

from study_agent.client import get_assignments, get_canvas_config, get_courses
from study_agent.memory import is_assignment_muted, is_prep_muted, load_memory
from study_agent.normalize import is_active_status, normalize_assignment
from study_agent.prep import load_prep_bundle


def agenda_section(
    item: dict[str, Any],
    *,
    today: date,
    tomorrow: date,
    window_end: date,
    overdue_start: date,
    include_submitted: bool,
) -> str | None:
    """Return the agenda bucket for one normalized assignment, or None to skip it."""
    due = item["due"]
    if not due:
        return None

    due_date = due.date()
    status = item["status"]
    is_low_priority = item["priority"] == "low"
    active = is_active_status(status)
    overdue = overdue_start <= due_date < today

    if status == "missing" and overdue and is_low_priority:
        return "low_priority"
    if status == "missing" and overdue:
        return "overdue_missing"
    if include_submitted and not active and today <= due_date <= window_end:
        return "submitted"
    if active and is_low_priority and overdue_start <= due_date <= window_end:
        return "low_priority"
    if active and due_date == today:
        return "due_today"
    if active and due_date == tomorrow:
        return "due_tomorrow"
    if active and tomorrow < due_date <= window_end:
        return "next_days"
    return None


def build_study_agenda(
    courses: list[dict[str, Any]],
    assignments_by_course: dict[Any, list[dict[str, Any]]],
    days: int = 3,
    now: datetime | None = None,
    include_submitted: bool = True,
    overdue_days: int = 30,
    muted_assignment_ids: list[Any] | None = None,
    prep_work: list[dict[str, Any]] | None = None,
    prep_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Sort assignments into overdue, today, tomorrow, upcoming, low priority, and done."""
    current = now or datetime.now().astimezone()
    today = current.date()
    tomorrow = today + timedelta(days=1)
    window_end = today + timedelta(days=days)
    overdue_start = today - timedelta(days=overdue_days)

    agenda: dict[str, Any] = {
        "generated_at": current,
        "days": days,
        "overdue_missing": [],
        "due_today": [],
        "due_tomorrow": [],
        "next_days": [],
        "low_priority": [],
        "prep_work": prep_work or [],
        "prep_warnings": prep_warnings or [],
        "submitted": [],
    }
    memory = {"muted_assignment_ids": muted_assignment_ids or []}

    for course in courses:
        course_id = course["id"]

        for assignment in assignments_by_course.get(course_id, []):
            item = normalize_assignment(course, assignment, current)
            if is_assignment_muted(item["assignment_id"], memory):
                continue

            section = agenda_section(
                item,
                today=today,
                tomorrow=tomorrow,
                window_end=window_end,
                overdue_start=overdue_start,
                include_submitted=include_submitted,
            )
            if section:
                agenda[section].append(item)

    sortable = [
        "overdue_missing",
        "due_today",
        "due_tomorrow",
        "next_days",
        "low_priority",
        "submitted",
    ]
    for key in sortable:
        agenda[key].sort(key=lambda item: item["due"])

    return agenda


def get_study_agenda(
    days: int = 3,
    include_submitted: bool = True,
    overdue_days: int = 30,
    include_prep: bool = False,
) -> dict[str, Any]:
    """Read Canvas and return an agenda for the requested window."""
    base_url, token = get_canvas_config()
    headers = {"Authorization": f"Bearer {token}"}

    courses = get_courses(base_url, headers)
    assignments_by_course = {
        course["id"]: get_assignments(base_url, headers, course["id"])
        for course in courses
        if "id" in course
    }

    memory = load_memory()
    prep_work: list[dict[str, Any]] = []
    prep_warnings: list[str] = []

    if include_prep:
        prep_work, prep_warnings = load_prep_bundle(base_url, headers, courses, days)
        prep_work = [item for item in prep_work if not is_prep_muted(item.get("prep_key"), memory)]

    return build_study_agenda(
        courses,
        assignments_by_course,
        days,
        include_submitted=include_submitted,
        overdue_days=overdue_days,
        muted_assignment_ids=memory.get("muted_assignment_ids", []),
        prep_work=prep_work,
        prep_warnings=prep_warnings,
    )


def format_item(item: dict[str, Any]) -> str:
    """Format one assignment for the terminal."""
    due = item["due"].strftime("%a %b %d %Y, %I:%M %p") if item["due"] else "No due date"
    points = ""
    if item["points"] is not None:
        points = f" | {item['points']} pts"

    return "\n".join(
        [
            f"{item['course']}",
            f"  {item['name']}",
            f"  Status: {item['status']} | Due: {due}{points}",
            f"  Priority: {item['priority']} | Why: {item['priority_reason']}",
            f"  Link: {item['url']}",
        ]
    )


def format_prep_item(item: dict[str, Any]) -> str:
    """Format one possible-prep item for the terminal."""
    lines = [
        f"{item['course']}",
        f"  {item['title']}",
        (
            f"  Status: {item['status']} | Source: {item['source_type']} | "
            f"Confidence: {item['confidence']}"
        ),
    ]

    if item.get("completion_status"):
        completion = item["completion_status"]
        lines.append(f"  Completion: {completion} | Check: {item.get('completion_reason')}")

    lines.extend(
        [
            f"  When: {item['soft_deadline']}",
            f"  Why: {item['reason']}",
            f"  Evidence: {item['evidence']}",
            f"  Link: {item['url']}",
        ]
    )

    return "\n".join(lines)


def format_agenda(agenda: dict[str, Any]) -> str:
    """Render an agenda as plain text."""
    sections = [
        ("Overdue / Missing", agenda["overdue_missing"]),
        ("Due Today", agenda["due_today"]),
        ("Due Tomorrow", agenda["due_tomorrow"]),
        (f"Next {agenda['days']} Days", agenda["next_days"]),
        ("Low Priority / Optional", agenda["low_priority"]),
        ("Submitted / Done", agenda["submitted"]),
    ]

    lines = [
        "",
        f"Study agenda generated {agenda['generated_at'].strftime('%Y-%m-%d %I:%M %p')}",
        "=" * 72,
    ]

    total_active = 0

    for title, items in sections:
        if not items:
            continue

        lines.append("")
        lines.append(title)
        lines.append("-" * len(title))

        for item in items:
            lines.append(format_item(item))
            lines.append("")

        if title not in {"Submitted / Done", "Low Priority / Optional"}:
            total_active += len(items)

    if agenda["prep_work"]:
        title = "Possible Prep Work"
        lines.append("")
        lines.append(title)
        lines.append("-" * len(title))

        for item in agenda["prep_work"]:
            lines.append(format_prep_item(item))
            lines.append("")

    if total_active == 0 and not agenda["submitted"]:
        lines.append("")
        lines.append("No hard-deadline Canvas assignments found in this window.")

    lines.append("=" * 72)
    lines.append(f"Active item(s): {total_active}")

    if agenda["submitted"]:
        lines.append(f"Submitted/done shown: {len(agenda['submitted'])}")

    if agenda["low_priority"]:
        lines.append(f"Low-priority item(s): {len(agenda['low_priority'])}")

    if agenda["prep_work"]:
        lines.append(f"Possible prep item(s): {len(agenda['prep_work'])}")

    if agenda["prep_warnings"]:
        lines.append("Prep source warning(s):")
        lines.extend(f"- {warning}" for warning in agenda["prep_warnings"][:5])

    return "\n".join(lines)


def main() -> None:
    """Print an agenda from the command line."""
    parser = argparse.ArgumentParser(description="Show upcoming Canvas assignment agenda.")
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="How many days ahead to include. Default: 3.",
    )
    parser.add_argument(
        "--hide-submitted",
        action="store_true",
        help="Hide submitted or graded assignments from the Done section.",
    )
    parser.add_argument(
        "--overdue-days",
        type=int,
        default=30,
        help="How far back to look for missing work. Default: 30.",
    )
    parser.add_argument(
        "--include-prep",
        action="store_true",
        help="Also scan modules, discussions, announcements, and syllabus for possible prep work.",
    )
    args = parser.parse_args()

    try:
        agenda = get_study_agenda(
            days=args.days,
            include_submitted=not args.hide_submitted,
            overdue_days=args.overdue_days,
            include_prep=args.include_prep,
        )
        print(format_agenda(agenda))
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
