import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


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


def parse_canvas_datetime(value):
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()


def get_tomorrow(now=None):
    current = now or datetime.now().astimezone()
    return current.date() + timedelta(days=1)


def collect_assignments_due_on(courses, assignments_by_course, target_date):
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


def import_requests():
    try:
        import requests

        return requests
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: requests. Run `pip install -r requirements.txt` first."
        ) from exc


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


def get_courses(base_url, headers):
    url = f"{base_url}/api/v1/courses"
    params = {
        "enrollment_state": "active",
        "per_page": 100,
    }

    return get_paginated_json(url, headers, params)


def get_assignments(base_url, headers, course_id):
    url = f"{base_url}/api/v1/courses/{course_id}/assignments"
    params = {
        "per_page": 100,
    }

    return get_paginated_json(url, headers, params)


def print_assignments(found, target_date):
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


def main():
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
