import argparse
import sys

from study_memory import mute_assignment
from study_tools import format_agenda, get_study_agenda


OFF_TOPIC_KEYWORDS = {
    "eat",
    "food",
    "breakfast",
    "lunch",
    "dinner",
    "snack",
    "restaurant",
    "cook",
    "weather",
    "movie",
    "music",
}

STUDY_KEYWORDS = {
    "assignment",
    "assignments",
    "canvas",
    "class",
    "classes",
    "course",
    "courses",
    "deadline",
    "deadlines",
    "due",
    "homework",
    "late",
    "missing",
    "overdue",
    "school",
    "study",
    "task",
    "tasks",
    "work",
    "announcement",
    "announcements",
    "discussion",
    "discussions",
    "module",
    "modules",
    "prep",
    "prepare",
    "read",
    "reading",
    "readings",
    "syllabus",
}

TIME_KEYWORDS = {
    "today",
    "tomorrow",
    "tmrw",
    "week",
    "7",
    "3",
    "three",
}


def is_canvas_study_question(text):
    words = set(text.lower().replace("?", " ").split())

    if words & OFF_TOPIC_KEYWORDS and not words & STUDY_KEYWORDS:
        return False

    if words & STUDY_KEYWORDS:
        return True

    asks_what_to_do = "what should" in text.lower() and "do" in words
    has_time_context = bool(words & TIME_KEYWORDS)

    return asks_what_to_do and has_time_context


def unsupported_question_message():
    return (
        "I only know how to check Canvas study tasks right now.\n"
        "Try asking: What should I do tomorrow? / What is due this week? / "
        "Show overdue work."
    )


def choose_tool_call(user_message):
    text = user_message.lower()

    if not is_canvas_study_question(text):
        return None

    asks_general_agenda = "what should" in text and "do" in set(text.replace("?", " ").split())
    asks_hard_deadlines_only = any(word in text for word in ["deadline", "deadlines", "due"])
    include_prep = any(
        word in text
        for word in [
            "announcement",
            "discussion",
            "module",
            "prep",
            "prepare",
            "read",
            "reading",
            "syllabus",
            "everything",
            "forgetting",
        ]
    ) or (asks_general_agenda and not asks_hard_deadlines_only)

    if "week" in text or "7" in text:
        return {
            "tool": "get_study_agenda",
            "days": 7,
            "include_submitted": True,
            "include_prep": include_prep,
        }

    if "tomorrow" in text:
        return {
            "tool": "get_study_agenda",
            "days": 1,
            "include_submitted": True,
            "include_prep": include_prep,
        }

    if "overdue" in text or "missing" in text or "late" in text:
        return {
            "tool": "get_study_agenda",
            "days": 0,
            "include_submitted": False,
            "include_prep": include_prep,
        }

    if "3" in text or "three" in text:
        return {
            "tool": "get_study_agenda",
            "days": 3,
            "include_submitted": True,
            "include_prep": include_prep,
        }

    return {
        "tool": "get_study_agenda",
        "days": 3,
        "include_submitted": True,
        "include_prep": include_prep,
    }


def answer(user_message):
    tool_call = choose_tool_call(user_message)

    if tool_call is None:
        return unsupported_question_message()

    print()
    print(
        "Agent: I will check Canvas with "
        f"{tool_call['tool']}(days={tool_call['days']}, "
        f"include_submitted={tool_call['include_submitted']}, "
        f"include_prep={tool_call['include_prep']})."
    )

    agenda = get_study_agenda(
        days=tool_call["days"],
        include_submitted=tool_call["include_submitted"],
        include_prep=tool_call["include_prep"],
    )

    return format_agenda(agenda)


def run_once(message):
    print(answer(message))


def run_chat():
    print("Study Agent v0.1")
    print("Ask: What should I do tomorrow? / this week? / overdue?")
    print("Type q to quit.")

    while True:
        try:
            message = input("\nYou: ").strip()
        except EOFError:
            print()
            return

        if message.lower() in {"q", "quit", "exit"}:
            return

        if not message:
            continue

        try:
            tool_call = choose_tool_call(message)

            if tool_call is None:
                print(unsupported_question_message())
                continue

            print()
            print(
                "Agent: I will check Canvas with "
                f"{tool_call['tool']}(days={tool_call['days']}, "
                f"include_submitted={tool_call['include_submitted']}, "
                f"include_prep={tool_call['include_prep']})."
            )

            agenda = get_study_agenda(
                days=tool_call["days"],
                include_submitted=tool_call["include_submitted"],
                include_prep=tool_call["include_prep"],
            )
            print(format_agenda(agenda))
            prompt_to_mute_low_priority_items(agenda)
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)


def prompt_to_mute_low_priority_items(agenda):
    low_priority_items = agenda.get("low_priority", [])

    if not low_priority_items:
        return

    for item in low_priority_items:
        assignment_id = item.get("assignment_id")

        if assignment_id is None:
            continue

        response = input(
            "\nMute this low-priority item next time? "
            f"{item['course']} - {item['name']} [y/N]: "
        ).strip().lower()

        if response in {"y", "yes"}:
            mute_assignment(assignment_id)
            print("Muted. I will hide it next time.")


def main():
    parser = argparse.ArgumentParser(description="A small Canvas study agent.")
    parser.add_argument("message", nargs="*", help="Ask the agent a question.")
    args = parser.parse_args()

    if args.message:
        run_once(" ".join(args.message))
    else:
        run_chat()


if __name__ == "__main__":
    main()
