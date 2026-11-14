import os
import re
from io import BytesIO
from datetime import datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from study_memory import is_assignment_muted, is_prep_muted, load_memory


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


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self):
        return " ".join(self.parts)


def load_environment():
    try:
        from dotenv import load_dotenv

        load_dotenv()
        return
    except ImportError:
        pass

    env_path = Path(".env")
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_canvas_config():
    load_environment()

    base_url = os.getenv("CANVAS_BASE_URL", "").rstrip("/")
    token = os.getenv("CANVAS_TOKEN", "")

    if not base_url or not token:
        raise RuntimeError(
            "Missing Canvas config. Put CANVAS_BASE_URL and CANVAS_TOKEN in .env."
        )

    return base_url, token


def import_requests():
    try:
        import requests

        return requests
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: requests. Run `pip install -r requirements.txt` first."
        ) from exc


def parse_canvas_datetime(value):
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()


def get_paginated_json(url, headers, params=None):
    requests = import_requests()
    results = []
    current_url = url
    current_params = params or {}

    while current_url:
        response = requests.get(current_url, headers=headers, params=current_params)
        response.raise_for_status()
        results.extend(response.json())

        current_url = response.links.get("next", {}).get("url")
        current_params = None

    return results


def get_json(url, headers, params=None):
    requests = import_requests()
    response = requests.get(url, headers=headers, params=params or {})
    response.raise_for_status()
    return response.json()


def get_courses(base_url, headers):
    url = f"{base_url}/api/v1/courses"
    params = {
        "enrollment_state": "active",
        "per_page": 100,
    }

    return get_paginated_json(url, headers, params)


def get_course_details(base_url, headers, course_id):
    url = f"{base_url}/api/v1/courses/{course_id}"
    params = {
        "include[]": "syllabus_body",
    }

    return get_json(url, headers, params)


def get_page_details(base_url, headers, course_id, page_url):
    url = f"{base_url}/api/v1/courses/{course_id}/pages/{page_url}"
    return get_json(url, headers)


def get_file_details(base_url, headers, file_id):
    url = f"{base_url}/api/v1/files/{file_id}"
    return get_json(url, headers)


def get_assignments(base_url, headers, course_id):
    url = f"{base_url}/api/v1/courses/{course_id}/assignments"
    params = {
        "include[]": "submission",
        "per_page": 100,
    }

    return get_paginated_json(url, headers, params)


def get_modules(base_url, headers, course_id):
    url = f"{base_url}/api/v1/courses/{course_id}/modules"
    params = {
        "include[]": ["items", "content_details"],
        "per_page": 100,
    }

    return get_paginated_json(url, headers, params)


def get_discussion_topics(base_url, headers, course_id):
    url = f"{base_url}/api/v1/courses/{course_id}/discussion_topics"
    params = {
        "per_page": 100,
    }

    return get_paginated_json(url, headers, params)


def get_current_user_id(base_url, headers):
    url = f"{base_url}/api/v1/users/self/profile"
    profile = get_json(url, headers)
    return profile.get("id")


class DiscussionInitialPostRequired(RuntimeError):
    pass


def get_discussion_entries(base_url, headers, course_id, discussion_id):
    requests = import_requests()
    url = f"{base_url}/api/v1/courses/{course_id}/discussion_topics/{discussion_id}/entries"
    params = {"per_page": 100}
    results = []
    current_url = url
    current_params = params

    while current_url:
        response = requests.get(current_url, headers=headers, params=current_params)
        if response.status_code == 403 and "require_initial_post" in response.text:
            raise DiscussionInitialPostRequired()

        response.raise_for_status()
        results.extend(response.json())
        current_url = response.links.get("next", {}).get("url")
        current_params = None

    return results


def get_announcements(base_url, headers, course_ids, start_date, end_date):
    url = f"{base_url}/api/v1/announcements"
    params = [
        ("per_page", 100),
        ("start_date", start_date.isoformat()),
        ("end_date", end_date.isoformat()),
    ]

    for course_id in course_ids:
        params.append(("context_codes[]", f"course_{course_id}"))

    return get_paginated_json(url, headers, params)


def same_origin(url, base_url):
    return urlparse(url).netloc == urlparse(base_url).netloc


def extract_pdf_text(content):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: pypdf. Run `pip install -r requirements.txt` first."
        ) from exc

    reader = PdfReader(BytesIO(content))
    parts = []

    for page in reader.pages[:20]:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text.strip())

    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def download_canvas_text_resource(url, headers, base_url):
    requests = import_requests()
    request_headers = headers if same_origin(url, base_url) else {}
    response = requests.get(url, headers=request_headers, timeout=20)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()
    url_lower = url.lower()

    if "application/pdf" in content_type or url_lower.endswith(".pdf"):
        return extract_pdf_text(response.content)

    if "text/html" in content_type:
        return html_to_text(response.text)

    if "text/" in content_type:
        return re.sub(r"\s+", " ", response.text).strip()

    return ""


def is_submitted(assignment):
    submission = assignment.get("submission") or {}
    workflow_state = submission.get("workflow_state")

    return bool(
        workflow_state in {"submitted", "graded", "pending_review"}
        or submission.get("submitted_at")
    )


def get_assignment_status(assignment, now=None):
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


def get_low_priority_reason(assignment):
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


def normalize_assignment(course, assignment, now=None):
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


def is_active_status(status):
    return status in {"unsubmitted", "missing"}


def html_to_text(value):
    if not value:
        return ""

    parser = HTMLTextExtractor()
    parser.feed(value)
    return re.sub(r"\s+", " ", parser.text()).strip()


def has_action_signal(text):
    value = text.lower()
    return any(word in value for word in ACTION_WORDS)


def has_time_signal(text):
    value = text.lower()
    return any(word in value for word in TIME_WORDS)


def has_specific_task_action_signal(text):
    value = text.lower()
    return any(word in value for word in SPECIFIC_TASK_ACTION_WORDS)


def truncate_evidence(text, limit=180):
    cleaned = re.sub(r"\s+", " ", text).strip()

    if len(cleaned) <= limit:
        return cleaned

    return cleaned[: limit - 3].rstrip() + "..."


def extract_month_day_dates(text, year):
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


def is_relevant_to_window(text, today, window_end):
    explicit_dates = extract_month_day_dates(text, today.year)

    if not explicit_dates:
        return True

    return any(today <= explicit_date <= window_end for explicit_date in explicit_dates)


def is_noise_discussion(text):
    value = text.lower()
    return any(phrase in value for phrase in DISCUSSION_NOISE_PHRASES)


def is_noise_specific_task(text):
    value = text.lower()
    return any(phrase in value for phrase in SPECIFIC_TASK_NOISE_PHRASES)


def has_explicit_date_in_window(text, today, window_end):
    explicit_dates = extract_month_day_dates(text, today.year)
    return any(today <= explicit_date <= window_end for explicit_date in explicit_dates)


def course_lookup(courses):
    return {course["id"]: course for course in courses if "id" in course}


def current_term_code(now=None):
    current = now or datetime.now().astimezone()
    year = str(current.year)[-2:]

    for term, months in TERM_MONTHS.items():
        if current.month in months:
            return f"{term}{year}"

    return year


def course_matches_current_term(course, now=None):
    term_code = current_term_code(now)
    text = " ".join(
        str(course.get(key) or "")
        for key in ["name", "course_code", "sis_course_id"]
    ).upper()

    return term_code in text or f"FALL 20{term_code[-2:]}" in text


def filter_prep_courses(courses, now=None):
    current_courses = [
        course for course in courses if course.get("id") and course_matches_current_term(course, now)
    ]

    return current_courses or [course for course in courses if course.get("id")]


def make_prep_item(course, title, source_type, url, evidence, confidence, reason):
    prep_key = make_prep_key(course["id"], source_type, title, url)
    return {
        "prep_key": prep_key,
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


def make_prep_key(course_id, source_type, title, url):
    raw = "|".join(
        [
            str(course_id or ""),
            str(source_type or ""),
            normalize_title(title),
            str(url or "").strip().lower(),
        ]
    )
    return raw


def add_prep_metadata(item, **metadata):
    enriched = dict(item)
    enriched.update({key: value for key, value in metadata.items() if value is not None})
    return enriched


def split_sentences(text):
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []

    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned)
        if sentence.strip()
    ]


def sentence_is_optional(sentence):
    return "optional" in sentence.lower() or "extra credit" in sentence.lower()


def extract_specific_prep_tasks(course, source, days=3, now=None):
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


def flattened_discussion_entries(entries):
    flattened = []

    def visit(entry):
        flattened.append(entry)
        for key in ["recent_replies", "replies"]:
            for reply in entry.get(key) or []:
                visit(reply)

    for entry in entries or []:
        visit(entry)

    return flattened


def discussion_status_from_entries(entries, current_user_id):
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


def get_discussion_completion_status(base_url, headers, course_id, discussion_id, current_user_id):
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


def add_discussion_completion_statuses(base_url, headers, prep_work, current_user_id):
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


def hide_module_reminders_with_specific_sources(prep_work):
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
            and (item.get("course_id"), normalize_title(item.get("title"))) in specific_source_titles
        )
    ]


def normalize_title(title):
    return re.sub(r"\s+", " ", str(title or "").strip().lower())


def should_fetch_module_item_text(module, item, today, window_end):
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
    base_url,
    headers,
    course,
    module,
    item,
    page_fetcher=get_page_details,
    file_fetcher=get_file_details,
    text_fetcher=download_canvas_text_resource,
):
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
        file_details = file_fetcher(base_url, headers, item["content_id"])
        file_url = file_details.get("url") or item.get("url")
        text = text_fetcher(file_url, headers, base_url) if file_url else ""
        content_type = file_details.get("content-type") or ""
        source_type = "pdf" if "pdf" in content_type.lower() or str(file_url).lower().endswith(".pdf") else "file"
        return {
            "course_id": course["id"],
            "source_type": source_type,
            "title": file_details.get("display_name") or file_details.get("filename") or title,
            "url": file_details.get("url") or item.get("html_url") or item.get("url"),
            "text": text,
            "module_name": module.get("name") or "",
            "source_item_id": item.get("id"),
        }

    return None


def collect_detailed_module_prep_work(
    base_url,
    headers,
    courses,
    modules_by_course,
    days=3,
    now=None,
):
    prep_work = []
    warnings = []
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
                if item.get("type") not in {"Page", "File"}:
                    continue

                if not should_fetch_module_item_text(module, item, today, window_end):
                    continue

                try:
                    source = fetch_module_item_text(base_url, headers, course, module, item)
                except Exception as exc:
                    warnings.append(
                        f"Could not extract {course.get('name')} - {item.get('title')}: {exc}"
                    )
                    continue

                if not source or not source.get("text"):
                    continue

                prep_work.extend(extract_specific_prep_tasks(course, source, days, now))

    return prep_work, warnings


def dedupe_and_rank_prep_work(prep_work, limit=12):
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
    source_order = {"page": 0, "pdf": 1, "module": 2, "discussion": 3, "announcement": 4, "syllabus": 5}
    deduped.sort(
        key=lambda item: (
            confidence_order.get(item["confidence"], 9),
            source_order.get(item["source_type"], 9),
            item["course"],
            item["title"],
        )
    )

    return deduped[:limit]


def collect_module_prep_work(courses, modules_by_course, today, window_end):
    prep_work = []
    lookup = course_lookup(courses)

    for course_id, modules in modules_by_course.items():
        course = lookup.get(course_id)
        if not course:
            continue

        for module in modules:
            module_name = module.get("name") or "Canvas module"

            for item in module.get("items") or []:
                item_type = item.get("type")

                if item_type in {"Assignment", "Quiz", "SubHeader"}:
                    continue

                title = item.get("title") or item.get("page_url") or "Module item"
                requirement = item.get("completion_requirement") or {}
                text = f"{module_name} {title} {requirement.get('type', '')}"

                if not is_relevant_to_window(text, today, window_end):
                    continue

                if requirement or (has_action_signal(text) and has_time_signal(text)):
                    confidence = "high" if requirement else "medium"
                    reason = (
                        f"Canvas module requires {requirement.get('type')}"
                        if requirement
                        else "Module title looks like prep work"
                    )
                    prep_work.append(
                        make_prep_item(
                            course,
                            title,
                            "module",
                            item.get("html_url") or item.get("url") or item.get("external_url"),
                            text,
                            confidence,
                            reason,
                        )
                    )

    return prep_work


def collect_discussion_prep_work(courses, discussions_by_course, today, window_end):
    prep_work = []
    lookup = course_lookup(courses)

    for course_id, discussions in discussions_by_course.items():
        course = lookup.get(course_id)
        if not course:
            continue

        for discussion in discussions:
            if discussion.get("assignment_id"):
                continue

            title = discussion.get("title") or "Discussion topic"
            message = html_to_text(discussion.get("message"))
            combined = f"{title} {message}"

            if is_noise_discussion(combined):
                continue

            if (
                has_action_signal(combined)
                and has_time_signal(combined)
                and is_relevant_to_window(combined, today, window_end)
            ):
                prep_work.append(
                    add_prep_metadata(
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
                )

    return prep_work


def collect_announcement_prep_work(courses, announcements, today, window_end):
    prep_work = []
    lookup = course_lookup(courses)

    for announcement in announcements:
        context_code = announcement.get("context_code") or ""
        if not context_code.startswith("course_"):
            continue

        try:
            course_id = int(context_code.replace("course_", "", 1))
        except ValueError:
            continue

        course = lookup.get(course_id)
        if not course:
            continue

        title = announcement.get("title") or "Announcement"
        message = html_to_text(announcement.get("message"))
        combined = f"{title} {message}"

        if (
            has_action_signal(combined)
            and has_time_signal(combined)
            and is_relevant_to_window(combined, today, window_end)
        ):
            prep_work.append(
                make_prep_item(
                    course,
                    title,
                    "announcement",
                    announcement.get("html_url") or announcement.get("url"),
                    combined,
                    "medium",
                    "Announcement contains an action and time signal",
                )
            )

    return prep_work


def collect_syllabus_prep_work(courses, syllabus_by_course):
    prep_work = []
    lookup = course_lookup(courses)

    for course_id, syllabus_body in syllabus_by_course.items():
        course = lookup.get(course_id)
        if not course:
            continue

        text = html_to_text(syllabus_body)

        if has_action_signal(text) and has_time_signal(text):
            prep_work.append(
                make_prep_item(
                    course,
                    "Syllabus reading or participation expectation",
                    "syllabus",
                    course.get("html_url") or f"https://uncch.instructure.com/courses/{course_id}/assignments/syllabus",
                    text,
                    "low",
                    "Syllabus contains a recurring action/time expectation",
                )
            )

    return prep_work


def collect_prep_work(
    courses,
    modules_by_course,
    discussions_by_course,
    announcements,
    syllabus_by_course,
    days=3,
    now=None,
):
    current = now or datetime.now().astimezone()
    today = current.date()
    window_end = today + timedelta(days=max(days, 1))
    prep_work = []
    prep_work.extend(collect_module_prep_work(courses, modules_by_course, today, window_end))
    prep_work.extend(collect_discussion_prep_work(courses, discussions_by_course, today, window_end))
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
    deduped.sort(key=lambda item: (confidence_order.get(item["confidence"], 9), item["course"], item["title"]))
    return dedupe_and_rank_prep_work(deduped)


def build_study_agenda(
    courses,
    assignments_by_course,
    days=3,
    now=None,
    include_submitted=True,
    overdue_days=30,
    muted_assignment_ids=None,
    prep_work=None,
    prep_warnings=None,
):
    current = now or datetime.now().astimezone()
    today = current.date()
    tomorrow = today + timedelta(days=1)
    window_end = today + timedelta(days=days)
    overdue_start = today - timedelta(days=overdue_days)

    agenda = {
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
            due = item["due"]

            if not due:
                continue

            if is_assignment_muted(item["assignment_id"], memory):
                continue

            due_date = due.date()
            status = item["status"]
            is_low_priority = item["priority"] == "low"

            if status == "missing" and overdue_start <= due_date < today and is_low_priority:
                agenda["low_priority"].append(item)
            elif status == "missing" and overdue_start <= due_date < today:
                agenda["overdue_missing"].append(item)
            elif include_submitted and not is_active_status(status) and today <= due_date <= window_end:
                agenda["submitted"].append(item)
            elif is_active_status(status) and is_low_priority and overdue_start <= due_date <= window_end:
                agenda["low_priority"].append(item)
            elif is_active_status(status) and due_date == today:
                agenda["due_today"].append(item)
            elif is_active_status(status) and due_date == tomorrow:
                agenda["due_tomorrow"].append(item)
            elif is_active_status(status) and tomorrow < due_date <= window_end:
                agenda["next_days"].append(item)

    for key in ["overdue_missing", "due_today", "due_tomorrow", "next_days", "low_priority", "submitted"]:
        agenda[key].sort(key=lambda item: item["due"])

    return agenda


def get_optional_json(fetcher, *args):
    try:
        return fetcher(*args)
    except Exception as exc:
        return {"error": str(exc)}


def get_study_agenda(days=3, include_submitted=True, overdue_days=30, include_prep=False):
    base_url, token = get_canvas_config()
    headers = {"Authorization": f"Bearer {token}"}

    courses = get_courses(base_url, headers)
    assignments_by_course = {
        course["id"]: get_assignments(base_url, headers, course["id"])
        for course in courses
        if "id" in course
    }

    memory = load_memory()
    prep_work = []
    prep_warnings = []

    if include_prep:
        prep_courses = filter_prep_courses(courses)
        course_ids = [course["id"] for course in prep_courses if "id" in course]
        today = datetime.now().astimezone().date()
        end_date = today + timedelta(days=max(days, 1))
        modules_by_course = {}
        discussions_by_course = {}
        syllabus_by_course = {}

        for course in prep_courses:
            if "id" not in course:
                continue

            course_id = course["id"]

            modules = get_optional_json(get_modules, base_url, headers, course_id)
            if isinstance(modules, dict) and "error" in modules:
                prep_warnings.append(f"Could not read modules for {course.get('name')}: {modules['error']}")
            else:
                modules_by_course[course_id] = modules

            discussions = get_optional_json(get_discussion_topics, base_url, headers, course_id)
            if isinstance(discussions, dict) and "error" in discussions:
                prep_warnings.append(f"Could not read discussions for {course.get('name')}: {discussions['error']}")
            else:
                discussions_by_course[course_id] = discussions

            details = get_optional_json(get_course_details, base_url, headers, course_id)
            if isinstance(details, dict) and "error" in details:
                prep_warnings.append(f"Could not read syllabus for {course.get('name')}: {details['error']}")
            else:
                syllabus_by_course[course_id] = details.get("syllabus_body") or ""

        announcements = get_optional_json(get_announcements, base_url, headers, course_ids, today, end_date)
        if isinstance(announcements, dict) and "error" in announcements:
            prep_warnings.append(f"Could not read announcements: {announcements['error']}")
            announcements = []

        current_user_id = get_optional_json(get_current_user_id, base_url, headers)
        if isinstance(current_user_id, dict) and "error" in current_user_id:
            prep_warnings.append(f"Could not identify current Canvas user: {current_user_id['error']}")
            current_user_id = None

        prep_work = collect_prep_work(
            prep_courses,
            modules_by_course=modules_by_course,
            discussions_by_course=discussions_by_course,
            announcements=announcements,
            syllabus_by_course=syllabus_by_course,
            days=days,
            now=datetime.now().astimezone(),
        )
        detailed_prep_work, detailed_warnings = collect_detailed_module_prep_work(
            base_url,
            headers,
            prep_courses,
            modules_by_course,
            days=days,
            now=datetime.now().astimezone(),
        )
        prep_work.extend(detailed_prep_work)
        prep_work = add_discussion_completion_statuses(
            base_url,
            headers,
            prep_work,
            current_user_id,
        )
        prep_work = dedupe_and_rank_prep_work(prep_work)
        prep_work = [
            item
            for item in prep_work
            if not is_prep_muted(item.get("prep_key"), memory)
        ]
        prep_warnings.extend(detailed_warnings)

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


def format_item(item):
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


def format_prep_item(item):
    lines = [
        f"{item['course']}",
        f"  {item['title']}",
        f"  Status: {item['status']} | Source: {item['source_type']} | Confidence: {item['confidence']}",
    ]

    if item.get("completion_status"):
        lines.append(
            f"  Completion: {item['completion_status']} | Check: {item.get('completion_reason')}"
        )

    lines.extend(
        [
            f"  When: {item['soft_deadline']}",
            f"  Why: {item['reason']}",
            f"  Evidence: {item['evidence']}",
            f"  Link: {item['url']}",
        ]
    )

    return "\n".join(lines)


def format_agenda(agenda):
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
