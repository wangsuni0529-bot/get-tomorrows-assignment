"""Pure rules for spotting possible prep work in course text.

These functions do not call Canvas. They only decide whether a piece of text
looks like work a student might need to do.
"""

import re
from datetime import date, datetime, timedelta
from typing import Any

ACTION_WORDS = {
    "complete",
    "discuss",
    "prepare",
    "read",
    "reading",
    "reply",
    "respond",
    "review",
    "post",
    "watch",
}

SPECIFIC_TASK_ACTION_WORDS = {
    "complete",
    "prepare",
    "read",
    "reading",
    "reply",
    "respond",
    "review",
    "post",
    "watch",
    "attempt",
}

TIME_WORDS = {
    "before",
    "by",
    "class",
    "due",
    "friday",
    "monday",
    "saturday",
    "sunday",
    "this week",
    "thursday",
    "today",
    "tomorrow",
    "tuesday",
    "wednesday",
    "weekly",
}

DISCUSSION_NOISE_PHRASES = {
    "ask a question",
    "course question board",
    "course introduction",
    "demo discussion",
    "discussion title",
    "drop your song",
    "final presentation discussion board",
    "include your discussion prompt here",
    "playlist recs",
    "playlist requests",
}

SPECIFIC_TASK_NOISE_PHRASES = {
    "after successful completion",
    "lesson objective",
    "lesson objectives",
    "objective 1",
    "objective 2",
    "objective 3",
    "objective 4",
    "today we will",
    "you will be able to",
}

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

TERM_MONTHS = {
    "SP": {1, 2, 3, 4, 5},
    "SU": {6, 7, 8},
    "FA": {9, 10, 11, 12},
}


def has_action_signal(text: str) -> bool:
    """Return whether the text contains a prep action word."""
    value = text.lower()
    return any(word in value for word in ACTION_WORDS)


def has_time_signal(text: str) -> bool:
    """Return whether the text contains a day or timing word."""
    value = text.lower()
    return any(word in value for word in TIME_WORDS)


def has_specific_task_action_signal(text: str) -> bool:
    """Return whether a sentence looks like a concrete task, not a vague mention."""
    value = text.lower()
    return any(word in value for word in SPECIFIC_TASK_ACTION_WORDS)


def truncate_evidence(text: str, limit: int = 180) -> str:
    """Shorten evidence text so a card can show it."""
    cleaned = re.sub(r"\s+", " ", text).strip()

    if len(cleaned) <= limit:
        return cleaned

    return cleaned[: limit - 3].rstrip() + "..."


def extract_month_day_dates(text: str, year: int) -> list[date]:
    """Find month-and-day mentions, using ``year`` because the text usually omits it."""
    dates = []
    pattern = r"\b(" + "|".join(MONTHS.keys()) + r")\.?\s+(\d{1,2})\b"

    for match in re.finditer(pattern, text.lower()):
        month = MONTHS[match.group(1)]
        day = int(match.group(2))
        try:
            dates.append(datetime(year, month, day).date())
        except ValueError:
            continue

    return dates


def is_relevant_to_window(text: str, today: date, window_end: date) -> bool:
    """Keep text that has no explicit date, or an explicit date inside the window."""
    explicit_dates = extract_month_day_dates(text, today.year)

    if not explicit_dates:
        return True

    return any(today <= explicit_date <= window_end for explicit_date in explicit_dates)


def is_noise_discussion(text: str) -> bool:
    """Return whether a discussion title looks like a standing question board."""
    value = text.lower()
    return any(phrase in value for phrase in DISCUSSION_NOISE_PHRASES)


def is_noise_specific_task(text: str) -> bool:
    """Return whether a sentence is a learning objective rather than a task."""
    value = text.lower()
    return any(phrase in value for phrase in SPECIFIC_TASK_NOISE_PHRASES)


def has_explicit_date_in_window(text: str, today: date, window_end: date) -> bool:
    """Return whether the text names a date inside the window."""
    explicit_dates = extract_month_day_dates(text, today.year)
    return any(today <= explicit_date <= window_end for explicit_date in explicit_dates)


def current_term_code(now: datetime | None = None) -> str:
    """Return a code like ``FA26`` for the term that contains ``now``."""
    current = now or datetime.now().astimezone()
    year = str(current.year)[-2:]

    for term, months in TERM_MONTHS.items():
        if current.month in months:
            return f"{term}{year}"

    return year


def course_matches_current_term(course: dict[str, Any], now: datetime | None = None) -> bool:
    """Return whether a course name or code looks like the current term."""
    term_code = current_term_code(now)
    text = " ".join(
        str(course.get(key) or "") for key in ["name", "course_code", "sis_course_id"]
    ).upper()

    return term_code in text or f"FALL 20{term_code[-2:]}" in text


def filter_prep_courses(
    courses: list[dict[str, Any]], now: datetime | None = None
) -> list[dict[str, Any]]:
    """Prefer current-term courses, and fall back to every course that has an id."""
    current_courses = [
        course
        for course in courses
        if course.get("id") and course_matches_current_term(course, now)
    ]

    return current_courses or [course for course in courses if course.get("id")]


def normalize_title(title: Any) -> str:
    """Normalize a title for comparison."""
    return re.sub(r"\s+", " ", str(title or "").strip().lower())


def make_prep_key(course_id: Any, source_type: str, title: str, url: str | None) -> str:
    """Build a stable id for muting one prep item."""
    return "|".join(
        [
            str(course_id or ""),
            str(source_type or ""),
            normalize_title(title),
            str(url or "").strip().lower(),
        ]
    )


def make_prep_item(
    course: dict[str, Any],
    title: str,
    source_type: str,
    url: str | None,
    evidence: str,
    confidence: str,
    reason: str,
) -> dict[str, Any]:
    """Build one possible-prep record. The status is always ``possible prep``."""
    return {
        "prep_key": make_prep_key(course["id"], source_type, title, url),
        "course": course.get("name") or course.get("course_code") or "Unknown Course",
        "course_id": course["id"],
        "title": title or "Untitled prep item",
        "source_type": source_type,
        "status": "possible prep",
        "soft_deadline": "No Canvas due date found",
        "url": url or course.get("html_url") or "",
        "confidence": confidence,
        "reason": reason,
        "evidence": truncate_evidence(evidence),
    }


def add_prep_metadata(item: dict[str, Any], **metadata: Any) -> dict[str, Any]:
    """Copy a prep item and set any metadata values that are not None."""
    enriched = dict(item)
    enriched.update({key: value for key, value in metadata.items() if value is not None})
    return enriched


def split_sentences(text: str) -> list[str]:
    """Split text into sentences on periods, question marks, and exclamation marks."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []

    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned)
        if sentence.strip()
    ]


def sentence_is_optional(sentence: str) -> bool:
    """Return whether a sentence labels itself optional or extra credit."""
    lowered = sentence.lower()
    return "optional" in lowered or "extra credit" in lowered


def extract_specific_prep_tasks(
    course: dict[str, Any],
    source: dict[str, Any],
    days: int = 3,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Pull high-confidence tasks out of linked page or file text."""
    current = now or datetime.now().astimezone()
    today = current.date()
    window_end = today + timedelta(days=max(days, 1))
    tasks = []

    for sentence in split_sentences(source.get("text") or ""):
        if sentence_is_optional(sentence):
            continue

        if is_noise_specific_task(sentence):
            continue

        if not has_specific_task_action_signal(sentence) or not has_time_signal(sentence):
            continue

        if not is_relevant_to_window(sentence, today, window_end):
            continue

        tasks.append(
            add_prep_metadata(
                make_prep_item(
                    course,
                    source.get("title") or "Prep from course material",
                    source.get("source_type") or "course_material",
                    source.get("url"),
                    sentence,
                    "high",
                    "Specific action found in linked course material",
                ),
                source_item_id=source.get("source_item_id"),
                module_name=source.get("module_name"),
            )
        )

    return tasks


def flattened_discussion_entries(entries: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Walk a discussion thread, including replies, in one list."""
    flattened: list[dict[str, Any]] = []

    def visit(entry: dict[str, Any]) -> None:
        flattened.append(entry)
        for key in ["recent_replies", "replies"]:
            for reply in entry.get(key) or []:
                visit(reply)

    for entry in entries or []:
        visit(entry)

    return flattened


def discussion_status_from_entries(
    entries: list[dict[str, Any]] | None, current_user_id: Any
) -> dict[str, str]:
    """Return whether the current user has posted in a discussion thread."""
    if current_user_id is None:
        return {
            "completion_status": "unknown",
            "completion_reason": "Could not identify current Canvas user",
        }

    current_user_id = str(current_user_id)

    for entry in flattened_discussion_entries(entries):
        if str(entry.get("user_id")) == current_user_id:
            return {
                "completion_status": "posted",
                "completion_reason": "Found your Canvas user id in discussion entries",
            }

    return {
        "completion_status": "not posted",
        "completion_reason": "No entry found from your Canvas user id",
    }
