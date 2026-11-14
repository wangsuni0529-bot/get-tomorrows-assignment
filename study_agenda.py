import argparse
import sys

from study_tools import format_agenda, get_study_agenda


def main():
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
