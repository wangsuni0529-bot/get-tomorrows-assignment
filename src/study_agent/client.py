"""Canvas API access. This module fetches data. It does not rank it."""

import os
import re
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from study_agent.normalize import html_to_text


class DiscussionInitialPostRequired(RuntimeError):
    """Canvas hid discussion replies because the user has not posted yet."""


def load_environment() -> None:
    """Load ``.env`` into the process environment without overriding existing variables."""
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


def get_canvas_config() -> tuple[str, str]:
    """Return the Canvas base URL and token from the environment."""
    load_environment()

    base_url = os.getenv("CANVAS_BASE_URL", "").rstrip("/")
    token = os.getenv("CANVAS_TOKEN", "")

    if not base_url or not token:
        raise RuntimeError("Missing Canvas config. Put CANVAS_BASE_URL and CANVAS_TOKEN in .env.")

    return base_url, token


def import_requests() -> Any:
    """Import requests, with an install hint when the dependency is missing."""
    try:
        import requests

        return requests
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: requests. Run `pip install -r requirements.txt` first."
        ) from exc


def same_origin(url: str, base_url: str) -> bool:
    """Return whether ``url`` is on the same host as the Canvas base URL."""
    return urlparse(url).netloc == urlparse(base_url).netloc


def headers_for_url(url: str, headers: dict[str, str], base_url: str) -> dict[str, str]:
    """Attach the Canvas token only to requests that stay on the Canvas host."""
    if same_origin(url, base_url):
        return headers
    return {}


def get_paginated_json(url: str, headers: dict[str, str], params: Any = None) -> list[Any]:
    """Follow Canvas ``Link`` headers and return every page as one list."""
    requests = import_requests()
    results: list[Any] = []
    current_url: str | None = url
    current_params = params or {}

    while current_url:
        response = requests.get(current_url, headers=headers, params=current_params)
        response.raise_for_status()
        results.extend(response.json())

        current_url = response.links.get("next", {}).get("url")
        current_params = None

    return results


def get_json(url: str, headers: dict[str, str], params: Any = None) -> Any:
    """GET one Canvas JSON resource."""
    requests = import_requests()
    response = requests.get(url, headers=headers, params=params or {})
    response.raise_for_status()
    return response.json()


def get_optional_json(fetcher: Any, *args: Any) -> Any:
    """Call a Canvas fetcher and return ``{"error": ...}`` instead of raising."""
    try:
        return fetcher(*args)
    except Exception as exc:
        return {"error": str(exc)}


def get_courses(base_url: str, headers: dict[str, str]) -> list[Any]:
    """Return the active courses for the token's user."""
    url = f"{base_url}/api/v1/courses"
    params = {
        "enrollment_state": "active",
        "per_page": 100,
    }
    return get_paginated_json(url, headers, params)


def get_course_details(base_url: str, headers: dict[str, str], course_id: Any) -> Any:
    """Return one course, including the syllabus body when Canvas provides it."""
    url = f"{base_url}/api/v1/courses/{course_id}"
    params = {"include[]": "syllabus_body"}
    return get_json(url, headers, params)


def get_page_details(
    base_url: str, headers: dict[str, str], course_id: Any, page_url: str
) -> Any:
    """Return one Canvas page."""
    url = f"{base_url}/api/v1/courses/{course_id}/pages/{page_url}"
    return get_json(url, headers)


def get_file_details(base_url: str, headers: dict[str, str], file_id: Any) -> Any:
    """Return metadata for one Canvas file."""
    url = f"{base_url}/api/v1/files/{file_id}"
    return get_json(url, headers)


def get_assignments(base_url: str, headers: dict[str, str], course_id: Any) -> list[Any]:
    """Return assignments for one course, including the current user's submission."""
    url = f"{base_url}/api/v1/courses/{course_id}/assignments"
    params = {
        "include[]": "submission",
        "per_page": 100,
    }
    return get_paginated_json(url, headers, params)


def get_modules(base_url: str, headers: dict[str, str], course_id: Any) -> list[Any]:
    """Return modules and their items for one course."""
    url = f"{base_url}/api/v1/courses/{course_id}/modules"
    params = {
        "include[]": ["items", "content_details"],
        "per_page": 100,
    }
    return get_paginated_json(url, headers, params)


def get_discussion_topics(base_url: str, headers: dict[str, str], course_id: Any) -> list[Any]:
    """Return discussion topics for one course."""
    url = f"{base_url}/api/v1/courses/{course_id}/discussion_topics"
    params = {"per_page": 100}
    return get_paginated_json(url, headers, params)


def get_current_user_id(base_url: str, headers: dict[str, str]) -> Any:
    """Return the Canvas user id for the token owner."""
    url = f"{base_url}/api/v1/users/self/profile"
    profile = get_json(url, headers)
    return profile.get("id")


def get_discussion_entries(
    base_url: str, headers: dict[str, str], course_id: Any, discussion_id: Any
) -> list[Any]:
    """Return discussion entries, or raise when Canvas requires an initial post."""
    requests = import_requests()
    url = f"{base_url}/api/v1/courses/{course_id}/discussion_topics/{discussion_id}/entries"
    params = {"per_page": 100}
    results: list[Any] = []
    current_url: str | None = url
    current_params: Any = params

    while current_url:
        response = requests.get(current_url, headers=headers, params=current_params)
        if response.status_code == 403 and "require_initial_post" in response.text:
            raise DiscussionInitialPostRequired()

        response.raise_for_status()
        results.extend(response.json())
        current_url = response.links.get("next", {}).get("url")
        current_params = None

    return results


def get_announcements(
    base_url: str, headers: dict[str, str], course_ids: list[Any], start_date: Any, end_date: Any
) -> list[Any]:
    """Return announcements for the given courses in a date window."""
    url = f"{base_url}/api/v1/announcements"
    params: list[tuple[str, Any]] = [
        ("per_page", 100),
        ("start_date", start_date.isoformat()),
        ("end_date", end_date.isoformat()),
    ]

    for course_id in course_ids:
        params.append(("context_codes[]", f"course_{course_id}"))

    return get_paginated_json(url, headers, params)


def extract_pdf_text(content: bytes) -> str:
    """Extract text from the first pages of a PDF."""
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


def download_canvas_text_resource(url: str, headers: dict[str, str], base_url: str) -> str:
    """Download a Canvas page or file and return its text.

    The Canvas token is sent only when ``url`` is on ``base_url``. Other hosts
    are fetched without those headers.
    """
    requests = import_requests()
    response = requests.get(url, headers=headers_for_url(url, headers, base_url), timeout=20)
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
