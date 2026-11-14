"""Collect possible prep work from Canvas modules, discussions, announcements, and pages.

Graded assignments are handled elsewhere. Everything returned here is labeled
as possible prep, because the source is ungraded or loosely worded.
"""

from datetime import datetime, timedelta
from typing import Any

from study_agent.client import (
    DiscussionInitialPostRequired,
    download_canvas_text_resource,
    get_announcements,
    get_course_details,
    get_current_user_id,
    get_discussion_entries,
    get_discussion_topics,
    get_file_details,
    get_modules,
    get_optional_json,
    get_page_details,
)
from study_agent.normalize import html_to_text
from study_agent.prep_text import (
    add_prep_metadata,
    discussion_status_from_entries,
    extract_specific_prep_tasks,
    filter_prep_courses,
    has_action_signal,
    has_explicit_date_in_window,
    has_time_signal,
    is_noise_discussion,
    is_relevant_to_window,
    make_prep_item,
    normalize_title,
)


def course_lookup(courses: list[dict[str, Any]]) -> dict[Any, dict[str, Any]]:
    """Index courses by id."""
    return {course["id"]: course for course in courses if "id" in course}


def get_discussion_completion_status(
    base_url: str,
    headers: dict[str, str],
    course_id: Any,
    discussion_id: Any,
    current_user_id: Any,
) -> dict[str, str]:
    """Read discussion entries and report whether the current user posted."""
    try:
        entries = get_discussion_entries(base_url, headers, course_id, discussion_id)
    except DiscussionInitialPostRequired:
        return {
            "completion_status": "not posted",
            "completion_reason": "Canvas says an initial post is required before viewing replies",
        }
    except Exception as exc:
        return {
            "completion_status": "unknown",
            "completion_reason": f"Could not read discussion entries: {exc}",
        }

    return discussion_status_from_entries(entries, current_user_id)


def add_discussion_completion_statuses(
    base_url: str,
    headers: dict[str, str],
    prep_work: list[dict[str, Any]],
    current_user_id: Any,
) -> list[dict[str, Any]]:
    """Attach posted / not posted status to discussion prep items."""
    enriched = []
    cache = {}

    for item in prep_work:
        if item.get("source_type") != "discussion" or not item.get("discussion_id"):
            enriched.append(item)
            continue

        key = (item["course_id"], item["discussion_id"])
        if key not in cache:
            cache[key] = get_discussion_completion_status(
                base_url,
                headers,
                item["course_id"],
                item["discussion_id"],
                current_user_id,
            )

        enriched.append(add_prep_metadata(item, **cache[key]))

    return enriched


def hide_module_reminders_with_specific_sources(
    prep_work: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop a module card when a page or file already extracted the same title."""
    specific_source_titles = {
        (item.get("course_id"), normalize_title(item.get("title")))
        for item in prep_work
        if item.get("source_type") in {"page", "pdf", "file"}
    }

    if not specific_source_titles:
        return prep_work

    return [
        item
        for item in prep_work
        if not (
            item.get("source_type") == "module"
            and (item.get("course_id"), normalize_title(item.get("title")))
            in specific_source_titles
        )
    ]


def should_fetch_module_item_text(
    module: dict[str, Any], item: dict[str, Any], today: Any, window_end: Any
) -> bool:
    """Open a linked page or file only when its title names a date in the window."""
    title_context = " ".join(
        str(value or "")
        for value in [
            module.get("name"),
            item.get("title"),
            item.get("page_url"),
        ]
    )

    return has_explicit_date_in_window(title_context, today, window_end)


def fetch_module_item_text(
    base_url: str,
    headers: dict[str, str],
    course: dict[str, Any],
    module: dict[str, Any],
    item: dict[str, Any],
    page_fetcher: Any = get_page_details,
    file_fetcher: Any = get_file_details,
    text_fetcher: Any = download_canvas_text_resource,
) -> dict[str, Any] | None:
    """Read a module Page or File into text the prep extractor can scan."""
    item_type = item.get("type")
    title = item.get("title") or item.get("page_url") or "Module item"

    if item_type == "Page" and item.get("page_url"):
        page = page_fetcher(base_url, headers, course["id"], item["page_url"])
        return {
            "course_id": course["id"],
            "source_type": "page",
            "title": page.get("title") or title,
            "url": page.get("html_url") or item.get("html_url") or item.get("url"),
            "text": html_to_text(page.get("body")),
            "module_name": module.get("name") or "",
            "source_item_id": item.get("id"),
        }

    if item_type == "File" and item.get("content_id"):
        return _file_source(
            base_url, headers, course, module, item, title, file_fetcher, text_fetcher
        )

    return None


def _file_source(
    base_url: str,
    headers: dict[str, str],
    course: dict[str, Any],
    module: dict[str, Any],
    item: dict[str, Any],
    title: str,
    file_fetcher: Any,
    text_fetcher: Any,
) -> dict[str, Any]:
    file_details = file_fetcher(base_url, headers, item["content_id"])
    file_url = file_details.get("url") or item.get("url")
    text = text_fetcher(file_url, headers, base_url) if file_url else ""
    content_type = file_details.get("content-type") or ""
    source_type = (
        "pdf" if "pdf" in content_type.lower() or str(file_url).lower().endswith(".pdf") else "file"
    )
    return {
        "course_id": course["id"],
        "source_type": source_type,
        "title": file_details.get("display_name") or file_details.get("filename") or title,
        "url": file_details.get("url") or item.get("html_url") or item.get("url"),
        "text": text,
        "module_name": module.get("name") or "",
        "source_item_id": item.get("id"),
    }


def collect_detailed_module_prep_work(
    base_url: str,
    headers: dict[str, str],
    courses: list[dict[str, Any]],
    modules_by_course: dict[Any, Any],
    days: int = 3,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Open dated module pages and files and extract specific prep tasks."""
    prep_work: list[dict[str, Any]] = []
    warnings: list[str] = []
    lookup = course_lookup(courses)
    current = now or datetime.now().astimezone()
    today = current.date()
    window_end = today + timedelta(days=max(days, 1))

    for course_id, modules in modules_by_course.items():
        course = lookup.get(course_id)
        if not course:
            continue

        for module in modules:
            for item in module.get("items") or []:
                prepared = _prep_from_module_item(
                    base_url, headers, course, module, item, today, window_end, days, now
                )
                if prepared is None:
                    continue
                tasks, warning = prepared
                if warning:
                    warnings.append(warning)
                prep_work.extend(tasks)

    return prep_work, warnings


def _prep_from_module_item(
    base_url: str,
    headers: dict[str, str],
    course: dict[str, Any],
    module: dict[str, Any],
    item: dict[str, Any],
    today: Any,
    window_end: Any,
    days: int,
    now: datetime | None,
) -> tuple[list[dict[str, Any]], str | None] | None:
    if item.get("type") not in {"Page", "File"}:
        return None

    if not should_fetch_module_item_text(module, item, today, window_end):
        return None

    try:
        source = fetch_module_item_text(base_url, headers, course, module, item)
    except Exception as exc:
        warning = f"Could not extract {course.get('name')} - {item.get('title')}: {exc}"
        return [], warning

    if not source or not source.get("text"):
        return [], None

    return extract_specific_prep_tasks(course, source, days, now), None


def dedupe_and_rank_prep_work(
    prep_work: list[dict[str, Any]], limit: int = 12
) -> list[dict[str, Any]]:
    """Remove duplicate prep cards and keep the highest-confidence ones."""
    prep_work = hide_module_reminders_with_specific_sources(prep_work)
    seen = set()
    deduped = []

    for item in prep_work:
        key = (item["course_id"], item["source_type"], item["title"], item["evidence"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    confidence_order = {"high": 0, "medium": 1, "low": 2}
    source_order = {
        "page": 0,
        "pdf": 1,
        "module": 2,
        "discussion": 3,
        "announcement": 4,
        "syllabus": 5,
    }
    deduped.sort(
        key=lambda item: (
            confidence_order.get(item["confidence"], 9),
            source_order.get(item["source_type"], 9),
            item["course"],
            item["title"],
        )
    )

    return deduped[:limit]


def collect_module_prep_work(
    courses: list[dict[str, Any]],
    modules_by_course: dict[Any, Any],
    today: Any,
    window_end: Any,
) -> list[dict[str, Any]]:
    """Turn module items with a requirement or an action/time title into prep cards."""
    prep_work = []
    lookup = course_lookup(courses)

    for course_id, modules in modules_by_course.items():
        course = lookup.get(course_id)
        if not course:
            continue

        for module in modules:
            module_name = module.get("name") or "Canvas module"

            for item in module.get("items") or []:
                card = _module_item_card(course, module_name, item, today, window_end)
                if card:
                    prep_work.append(card)

    return prep_work


def _module_item_card(
    course: dict[str, Any],
    module_name: str,
    item: dict[str, Any],
    today: Any,
    window_end: Any,
) -> dict[str, Any] | None:
    item_type = item.get("type")

    if item_type in {"Assignment", "Quiz", "SubHeader"}:
        return None

    title = item.get("title") or item.get("page_url") or "Module item"
    requirement = item.get("completion_requirement") or {}
    text = f"{module_name} {title} {requirement.get('type', '')}"

    if not is_relevant_to_window(text, today, window_end):
        return None

    if not requirement and not (has_action_signal(text) and has_time_signal(text)):
        return None

    confidence = "high" if requirement else "medium"
    reason = (
        f"Canvas module requires {requirement.get('type')}"
        if requirement
        else "Module title looks like prep work"
    )
    return make_prep_item(
        course,
        title,
        "module",
        item.get("html_url") or item.get("url") or item.get("external_url"),
        text,
        confidence,
        reason,
    )


def collect_discussion_prep_work(
    courses: list[dict[str, Any]],
    discussions_by_course: dict[Any, Any],
    today: Any,
    window_end: Any,
) -> list[dict[str, Any]]:
    """Turn ungraded discussions that ask for something into prep cards."""
    prep_work = []
    lookup = course_lookup(courses)

    for course_id, discussions in discussions_by_course.items():
        course = lookup.get(course_id)
        if not course:
            continue

        for discussion in discussions:
            card = _discussion_card(course, discussion, today, window_end)
            if card:
                prep_work.append(card)

    return prep_work


def _discussion_card(
    course: dict[str, Any],
    discussion: dict[str, Any],
    today: Any,
    window_end: Any,
) -> dict[str, Any] | None:
    if discussion.get("assignment_id"):
        return None

    title = discussion.get("title") or "Discussion topic"
    message = html_to_text(discussion.get("message"))
    combined = f"{title} {message}"

    if is_noise_discussion(combined):
        return None

    if not (
        has_action_signal(combined)
        and has_time_signal(combined)
        and is_relevant_to_window(combined, today, window_end)
    ):
        return None

    return add_prep_metadata(
        make_prep_item(
            course,
            title,
            "discussion",
            discussion.get("html_url"),
            combined,
            "medium",
            "Ungraded Canvas discussion topic",
        ),
        discussion_id=discussion.get("id"),
        completion_status="unknown",
        completion_reason="Discussion entries not checked yet",
    )


def collect_announcement_prep_work(
    courses: list[dict[str, Any]],
    announcements: list[dict[str, Any]],
    today: Any,
    window_end: Any,
) -> list[dict[str, Any]]:
    """Turn announcements with an action and a time into prep cards."""
    prep_work = []
    lookup = course_lookup(courses)

    for announcement in announcements:
        card = _announcement_card(lookup, announcement, today, window_end)
        if card:
            prep_work.append(card)

    return prep_work


def _announcement_card(
    lookup: dict[Any, dict[str, Any]],
    announcement: dict[str, Any],
    today: Any,
    window_end: Any,
) -> dict[str, Any] | None:
    context_code = announcement.get("context_code") or ""
    if not context_code.startswith("course_"):
        return None

    try:
        course_id = int(context_code.replace("course_", "", 1))
    except ValueError:
        return None

    course = lookup.get(course_id)
    if not course:
        return None

    title = announcement.get("title") or "Announcement"
    message = html_to_text(announcement.get("message"))
    combined = f"{title} {message}"

    if not (
        has_action_signal(combined)
        and has_time_signal(combined)
        and is_relevant_to_window(combined, today, window_end)
    ):
        return None

    return make_prep_item(
        course,
        title,
        "announcement",
        announcement.get("html_url") or announcement.get("url"),
        combined,
        "medium",
        "Announcement contains an action and time signal",
    )


def collect_syllabus_prep_work(
    courses: list[dict[str, Any]], syllabus_by_course: dict[Any, str]
) -> list[dict[str, Any]]:
    """Turn a syllabus that mentions an action and a time into one low-confidence card."""
    prep_work = []
    lookup = course_lookup(courses)

    for course_id, syllabus_body in syllabus_by_course.items():
        course = lookup.get(course_id)
        if not course:
            continue

        text = html_to_text(syllabus_body)

        if has_action_signal(text) and has_time_signal(text):
            syllabus_url = course.get("html_url") or (
                f"https://uncch.instructure.com/courses/{course_id}/assignments/syllabus"
            )
            prep_work.append(
                make_prep_item(
                    course,
                    "Syllabus reading or participation expectation",
                    "syllabus",
                    syllabus_url,
                    text,
                    "low",
                    "Syllabus contains a recurring action/time expectation",
                )
            )

    return prep_work


def collect_prep_work(
    courses: list[dict[str, Any]],
    modules_by_course: dict[Any, Any],
    discussions_by_course: dict[Any, Any],
    announcements: list[dict[str, Any]],
    syllabus_by_course: dict[Any, str],
    days: int = 3,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Merge prep found in modules, discussions, announcements, and syllabi."""
    current = now or datetime.now().astimezone()
    today = current.date()
    window_end = today + timedelta(days=max(days, 1))
    prep_work: list[dict[str, Any]] = []
    prep_work.extend(collect_module_prep_work(courses, modules_by_course, today, window_end))
    prep_work.extend(
        collect_discussion_prep_work(courses, discussions_by_course, today, window_end)
    )
    prep_work.extend(collect_announcement_prep_work(courses, announcements, today, window_end))
    prep_work.extend(collect_syllabus_prep_work(courses, syllabus_by_course))

    seen = set()
    deduped = []
    for item in prep_work:
        key = (item["course_id"], item["source_type"], item["title"], item["url"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    confidence_order = {"high": 0, "medium": 1, "low": 2}
    deduped.sort(
        key=lambda item: (
            confidence_order.get(item["confidence"], 9),
            item["course"],
            item["title"],
        )
    )
    return dedupe_and_rank_prep_work(deduped)


def load_prep_bundle(
    base_url: str,
    headers: dict[str, str],
    courses: list[dict[str, Any]],
    days: int,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch current-term prep sources and return ranked items plus warnings."""
    prep_courses = filter_prep_courses(courses, now)
    course_ids = [course["id"] for course in prep_courses if "id" in course]
    current = now or datetime.now().astimezone()
    today = current.date()
    end_date = today + timedelta(days=max(days, 1))
    modules_by_course: dict[Any, Any] = {}
    discussions_by_course: dict[Any, Any] = {}
    syllabus_by_course: dict[Any, str] = {}
    warnings: list[str] = []

    for course in prep_courses:
        if "id" not in course:
            continue
        _read_course_prep_sources(
            base_url,
            headers,
            course,
            modules_by_course,
            discussions_by_course,
            syllabus_by_course,
            warnings,
        )

    announcements = get_optional_json(
        get_announcements, base_url, headers, course_ids, today, end_date
    )
    if isinstance(announcements, dict) and "error" in announcements:
        warnings.append(f"Could not read announcements: {announcements['error']}")
        announcements = []

    current_user_id = get_optional_json(get_current_user_id, base_url, headers)
    if isinstance(current_user_id, dict) and "error" in current_user_id:
        warnings.append(f"Could not identify current Canvas user: {current_user_id['error']}")
        current_user_id = None

    prep_work = collect_prep_work(
        prep_courses,
        modules_by_course=modules_by_course,
        discussions_by_course=discussions_by_course,
        announcements=announcements,
        syllabus_by_course=syllabus_by_course,
        days=days,
        now=current,
    )
    detailed_prep_work, detailed_warnings = collect_detailed_module_prep_work(
        base_url,
        headers,
        prep_courses,
        modules_by_course,
        days=days,
        now=current,
    )
    prep_work.extend(detailed_prep_work)
    prep_work = add_discussion_completion_statuses(base_url, headers, prep_work, current_user_id)
    prep_work = dedupe_and_rank_prep_work(prep_work)
    warnings.extend(detailed_warnings)
    return prep_work, warnings


def _read_course_prep_sources(
    base_url: str,
    headers: dict[str, str],
    course: dict[str, Any],
    modules_by_course: dict[Any, Any],
    discussions_by_course: dict[Any, Any],
    syllabus_by_course: dict[Any, str],
    warnings: list[str],
) -> None:
    course_id = course["id"]
    course_name = course.get("name")

    modules = get_optional_json(get_modules, base_url, headers, course_id)
    if isinstance(modules, dict) and "error" in modules:
        warnings.append(f"Could not read modules for {course_name}: {modules['error']}")
    else:
        modules_by_course[course_id] = modules

    discussions = get_optional_json(get_discussion_topics, base_url, headers, course_id)
    if isinstance(discussions, dict) and "error" in discussions:
        warnings.append(f"Could not read discussions for {course_name}: {discussions['error']}")
    else:
        discussions_by_course[course_id] = discussions

    details = get_optional_json(get_course_details, base_url, headers, course_id)
    if isinstance(details, dict) and "error" in details:
        warnings.append(f"Could not read syllabus for {course_name}: {details['error']}")
    else:
        syllabus_by_course[course_id] = details.get("syllabus_body") or ""
