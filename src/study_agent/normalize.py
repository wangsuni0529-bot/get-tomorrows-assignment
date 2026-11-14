"""Turn raw Canvas assignments into comparable local records."""

import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any


class HTMLTextExtractor(HTMLParser):
    """Collect visible text nodes from an HTML snippet."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        return " ".join(self.parts)


def parse_canvas_datetime(value: str | None) -> datetime | None:
    """Parse a Canvas ISO timestamp into a timezone-aware local datetime."""
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()


def html_to_text(value: str | None) -> str:
    """Strip HTML tags and collapse whitespace."""
    if not value:
        return ""

    parser = HTMLTextExtractor()
    parser.feed(value)
    return re.sub(r"\s+", " ", parser.text()).strip()


def is_submitted(assignment: dict[str, Any]) -> bool:
    """Return whether the current user has a submission on record."""
    submission = assignment.get("submission") or {}
    workflow_state = submission.get("workflow_state")

    submitted_states = {"submitted", "graded", "pending_review"}
    return bool(workflow_state in submitted_states or submission.get("submitted_at"))


def get_assignment_status(assignment: dict[str, Any], now: datetime | None = None) -> str:
    """Return a short status: graded, submitted, submitted late, missing, or unsubmitted."""
    current = now or datetime.now().astimezone()
    due = parse_canvas_datetime(assignment.get("due_at"))
    submission = assignment.get("submission") or {}
    workflow_state = submission.get("workflow_state")

    if workflow_state == "graded":
        return "graded"

    if is_submitted(assignment):
        if submission.get("late"):
            return "submitted late"
        return "submitted"

    if due and due < current:
        return "missing"

    return "unsubmitted"


def get_low_priority_reason(assignment: dict[str, Any]) -> str | None:
    """Return why an assignment is optional or low stakes, or None when it is normal work."""
    title = (assignment.get("name") or "").lower()
    assignment_group = (assignment.get("assignment_group_name") or "").lower()
    points = assignment.get("points_possible")

    if "optional" in title or "optional" in assignment_group:
        return "Title or assignment group says optional"

    if "extra credit" in title or "extra credit" in assignment_group:
        return "Looks like extra credit"

    if points == 0:
        return "Worth 0 points"

    if assignment.get("omit_from_final_grade") is True:
        return "Omitted from final grade"

    return None


def normalize_assignment(
    course: dict[str, Any], assignment: dict[str, Any], now: datetime | None = None
) -> dict[str, Any]:
    """Map one Canvas assignment into the record the agenda sorts."""
    due = parse_canvas_datetime(assignment.get("due_at"))
    submission = assignment.get("submission") or {}
    low_priority_reason = get_low_priority_reason(assignment)

    return {
        "assignment_id": assignment.get("id"),
        "course": course.get("name") or course.get("course_code") or "Unknown Course",
        "course_id": course["id"],
        "name": assignment.get("name") or "Untitled Assignment",
        "due": due,
        "url": assignment.get("html_url") or "",
        "points": assignment.get("points_possible"),
        "status": get_assignment_status(assignment, now),
        "priority": "low" if low_priority_reason else "normal",
        "priority_reason": low_priority_reason or "Canvas hard-deadline assignment",
        "workflow_state": submission.get("workflow_state") or "unknown",
        "submitted_at": parse_canvas_datetime(submission.get("submitted_at")),
    }


def is_active_status(status: str) -> bool:
    """Return whether the student still needs to act on this status."""
    return status in {"unsubmitted", "missing"}
