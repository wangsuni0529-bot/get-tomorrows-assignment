"""Local web server for the study agenda. It binds to localhost and serves the frontend."""

import json
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from study_agent.agenda import get_study_agenda
from study_agent.agent import choose_tool_call, unsupported_question_message
from study_agent.client import get_canvas_config
from study_agent.memory import load_memory, mute_assignment, mute_prep

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
MAX_DAYS = 14
VALID_MODES = {"focused", "balanced", "catch_all"}
VALID_SOURCE_TYPES = {"discussion", "module", "page", "file", "pdf", "announcement", "syllabus"}


def parse_bool(value: Any) -> bool:
    """Accept the usual true-ish query values."""
    return str(value or "").lower() in {"1", "true", "yes", "y", "on"}


def parse_days(value: Any, default: int = 1) -> int:
    """Parse a day window and reject values outside 0..14."""
    if value in {None, ""}:
        return default

    try:
        days = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("days must be a number") from exc

    if days < 0 or days > MAX_DAYS:
        raise ValueError(f"days must be between 0 and {MAX_DAYS}")

    return days


def parse_mode(value: Any) -> str:
    """Return focused, balanced, or catch_all."""
    mode = str(value or "balanced").strip().lower().replace("-", "_")

    if mode not in VALID_MODES:
        raise ValueError("mode must be focused, balanced, or catch_all")

    return mode


def mode_to_include_prep(mode: str) -> bool:
    """Focused mode is hard deadlines only. The other modes include possible prep."""
    return parse_mode(mode) != "focused"


def parse_source_types(value: Any) -> set[str]:
    """Parse a comma-separated source list, ignoring unknown names."""
    if value in {None, ""}:
        return set(VALID_SOURCE_TYPES)

    requested = {
        item.strip().lower().replace("-", "_")
        for item in str(value).split(",")
        if item.strip()
    }
    selected = requested & VALID_SOURCE_TYPES
    return selected or set(VALID_SOURCE_TYPES)


def filter_agenda_sources(agenda: dict[str, Any], source_types: set[str]) -> dict[str, Any]:
    """Drop prep items whose source type was turned off."""
    filtered = dict(agenda)
    filtered["prep_work"] = [
        item
        for item in agenda.get("prep_work", [])
        if item.get("source_type") in source_types
    ]
    return filtered


def date_label(value):
    if not value:
        return "No Canvas due date"

    return value.strftime("%a %b %d %Y, %I:%M %p")


def iso_datetime(value):
    if isinstance(value, datetime):
        return value.isoformat()

    return None


def serialize_assignment(item):
    return {
        "type": "assignment",
        "assignmentId": item.get("assignment_id"),
        "course": item.get("course", "Unknown Course"),
        "title": item.get("name", "Untitled Assignment"),
        "status": item.get("status", "unknown"),
        "due": iso_datetime(item.get("due")),
        "dueLabel": date_label(item.get("due")),
        "url": item.get("url", ""),
        "points": item.get("points"),
        "priority": item.get("priority", "normal"),
        "reason": item.get("priority_reason", ""),
    }


def serialize_prep(item):
    return {
        "type": "prep",
        "prepKey": item.get("prep_key"),
        "course": item.get("course", "Unknown Course"),
        "title": item.get("title", "Untitled prep item"),
        "status": item.get("status", "possible prep"),
        "due": None,
        "dueLabel": item.get("soft_deadline", "No Canvas due date found"),
        "url": item.get("url", ""),
        "sourceType": item.get("source_type", "course material"),
        "confidence": item.get("confidence", "unknown"),
        "reason": item.get("reason", ""),
        "evidence": item.get("evidence", ""),
        "completionStatus": item.get("completion_status"),
        "completionReason": item.get("completion_reason"),
    }


def serialize_agenda(agenda: dict[str, Any]) -> dict[str, Any]:
    """Convert an agenda into JSON-safe sections for the frontend."""
    sections = [
        ("overdue_missing", "Overdue / Missing", "assignment"),
        ("due_today", "Due Today", "assignment"),
        ("due_tomorrow", "Due Tomorrow", "assignment"),
        ("next_days", f"Next {agenda['days']} Days", "assignment"),
        ("prep_work", "Possible Prep Work", "prep"),
        ("low_priority", "Low Priority / Optional", "assignment"),
        ("submitted", "Submitted / Done", "assignment"),
    ]

    serialized_sections = []
    for key, label, item_type in sections:
        items = agenda.get(key, [])
        serializer = serialize_prep if item_type == "prep" else serialize_assignment
        serialized_sections.append(
            {
                "key": key,
                "label": label,
                "items": [serializer(item) for item in items],
            }
        )

    active_count = sum(
        len(agenda.get(key, []))
        for key in ["overdue_missing", "due_today", "due_tomorrow", "next_days"]
    )

    return {
        "generatedAt": iso_datetime(agenda.get("generated_at")),
        "generatedAtLabel": agenda["generated_at"].strftime("%Y-%m-%d %I:%M %p"),
        "days": agenda.get("days"),
        "sections": serialized_sections,
        "summary": {
            "active": active_count,
            "prep": len(agenda.get("prep_work", [])),
            "done": len(agenda.get("submitted", [])),
            "lowPriority": len(agenda.get("low_priority", [])),
        },
        "warnings": agenda.get("prep_warnings", []),
        "selected": {
            "mode": agenda.get("selected_mode", "balanced"),
            "sourceTypes": sorted(agenda.get("selected_source_types", VALID_SOURCE_TYPES)),
        },
    }


def canvas_is_configured() -> bool:
    """Return whether a Canvas base URL and token are available. The token is not returned."""
    try:
        get_canvas_config()
    except Exception:
        return False

    return True


def build_agenda_response(
    days: int,
    mode: str = "balanced",
    source_types: set[str] | None = None,
    include_submitted: bool = True,
) -> dict[str, Any]:
    """Build the JSON agenda for one window, mode, and source filter."""
    selected_mode = parse_mode(mode)
    selected_sources = source_types or set(VALID_SOURCE_TYPES)
    agenda = get_study_agenda(
        days=days,
        include_submitted=include_submitted,
        include_prep=mode_to_include_prep(selected_mode),
    )
    agenda = filter_agenda_sources(agenda, selected_sources)
    agenda["selected_mode"] = selected_mode
    agenda["selected_source_types"] = selected_sources
    return serialize_agenda(agenda)


class StudyAgentHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status, code, message):
        self.send_json(status, {"error": {"code": code, "message": message}})

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self.send_json(200, {"ok": True, "canvasConfigured": canvas_is_configured()})
            return

        if parsed.path == "/api/agenda":
            params = parse_qs(parsed.query)
            try:
                days = parse_days((params.get("days") or [None])[0], default=1)
                mode = parse_mode((params.get("mode") or ["balanced"])[0])
                source_types = parse_source_types((params.get("sourceTypes") or [None])[0])
                include_submitted = not parse_bool((params.get("hideSubmitted") or ["false"])[0])
            except ValueError as exc:
                self.send_error_json(400, "INVALID_QUERY", str(exc))
                return

            try:
                payload = build_agenda_response(days, mode, source_types, include_submitted)
            except Exception as exc:
                self.send_error_json(500, "CANVAS_ERROR", str(exc))
                return

            self.send_json(200, payload)
            return

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/chat":
            if parsed.path == "/api/mute":
                self.handle_mute()
                return

            self.send_error_json(404, "NOT_FOUND", "Endpoint not found")
            return

        self.handle_chat()

    def read_json_body(self, max_length=4000):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("Invalid content length")

        if length > max_length:
            raise OverflowError("Request body is too long")

        try:
            body = self.rfile.read(length).decode("utf-8")
            return json.loads(body or "{}")
        except json.JSONDecodeError:
            raise ValueError("Request body must be JSON")

    def handle_chat(self):
        try:
            payload = self.read_json_body()
        except OverflowError as exc:
            self.send_error_json(413, "BODY_TOO_LARGE", str(exc))
            return
        except ValueError:
            self.send_error_json(400, "INVALID_JSON", "Request body must be JSON")
            return

        message = str(payload.get("message") or "").strip()
        if not message:
            self.send_error_json(400, "EMPTY_MESSAGE", "Message is required")
            return

        tool_call = choose_tool_call(message)
        if tool_call is None:
            self.send_json(
                200,
                {
                    "message": unsupported_question_message(),
                    "toolCall": None,
                    "agenda": None,
                },
            )
            return

        mode = parse_mode(payload.get("mode") or "balanced")
        source_types = parse_source_types(payload.get("sourceTypes"))
        request_mode = mode if tool_call["include_prep"] else "focused"
        if tool_call["include_prep"] and mode == "focused":
            request_mode = "balanced"

        try:
            agenda = build_agenda_response(
                tool_call["days"],
                request_mode,
                source_types,
                tool_call["include_submitted"],
            )
        except Exception as exc:
            self.send_error_json(500, "CANVAS_ERROR", str(exc))
            return

        self.send_json(
            200,
            {
                "message": "I checked Canvas and organized what matters next.",
                "toolCall": tool_call,
                "agenda": agenda,
            },
        )

    def handle_mute(self):
        try:
            payload = self.read_json_body()
        except OverflowError as exc:
            self.send_error_json(413, "BODY_TOO_LARGE", str(exc))
            return
        except ValueError as exc:
            self.send_error_json(400, "INVALID_JSON", str(exc))
            return

        item_type = str(payload.get("type") or "assignment")

        if item_type == "prep":
            prep_key = payload.get("prepKey")
            if prep_key in {None, ""}:
                self.send_error_json(400, "MISSING_PREP_KEY", "prepKey is required")
                return

            mute_prep(prep_key)
            memory = load_memory()
            self.send_json(
                200,
                {
                    "ok": True,
                    "mutedPrepKeys": memory.get("muted_prep_keys", []),
                },
            )
            return

        assignment_id = payload.get("assignmentId")
        if assignment_id in {None, ""}:
            self.send_error_json(400, "MISSING_ASSIGNMENT_ID", "assignmentId is required")
            return

        mute_assignment(assignment_id)
        memory = load_memory()
        self.send_json(
            200,
            {
                "ok": True,
                "mutedAssignmentIds": memory.get("muted_assignment_ids", []),
            },
        )


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve the app on localhost. The Canvas token stays in this process."""
    server = ThreadingHTTPServer((host, port), StudyAgentHandler)
    print(f"Study Agent web demo running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    run()
