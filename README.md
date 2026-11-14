# Canvas Study Agent

This local project has two working modes:

- `study_agent.py`: a tiny chat-style agent that chooses a Canvas agenda tool.
- `study_agenda.py`: a direct command for upcoming hard-deadline Canvas assignments.

It currently reads structured Canvas assignments, due dates, links, and submission status. It can also run a conservative prep-work scan across current-term Canvas modules, ungraded discussions, announcements, and syllabus text.

Prep-work results are intentionally labeled as `Possible Prep Work` because they may come from ungraded or loosely worded course material rather than Canvas assignments with hard due dates.

When prep scanning is enabled, the agent also opens linked Canvas Pages and Canvas Files/PDFs from relevant current-week module items and extracts text to find more specific prep tasks. External module URLs are not fetched automatically because Canvas tokens must not be sent to non-Canvas websites.

Low-priority items, such as optional assignments or 0-point items, are separated from urgent work. In chat mode, the agent can ask whether to mute a low-priority item so it will be hidden next time.

## Setup

```bash
cd canvas-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env`:

```text
CANVAS_BASE_URL=https://uncch.instructure.com
CANVAS_TOKEN=your_token_here
```

Do not share your `.env` file or token.

## Run the Agent

```bash
python study_agent.py
```

Then ask:

```text
What should I do tomorrow?
What should I do this week?
Show overdue work.
What readings or prep do I have this week?
```

You can also ask once from Terminal:

```bash
python study_agent.py "What should I do tomorrow?"
```

## Run the Local Web Demo

Start the local web app:

```bash
python web_server.py
```

Then open:

```text
http://127.0.0.1:8000
```

The web demo uses the same local `.env` file as the terminal agent. It runs only on your computer by default.

## Run the Agenda Directly

Default view: overdue plus the next 3 days.

```bash
python study_agenda.py
```

Next 7 days:

```bash
python study_agenda.py --days 7
```

Next 7 days plus possible prep work from modules, discussions, announcements, and syllabus:

```bash
python study_agenda.py --days 7 --include-prep
```

Hide submitted assignments:

```bash
python study_agenda.py --hide-submitted
```

## Mute Low-Priority Items

Run chat mode:

```bash
python study_agent.py
```

Ask a study question. If the agenda includes optional or low-priority items, the agent may ask:

```text
Mute this low-priority item next time? [y/N]
```

Answer `y` to hide that item in future runs. Muted items are stored locally in `.study_agent_memory.json`.

## Current Limits

The prep-work scan is conservative but not perfect. It uses Canvas source links, Canvas Page/File/PDF text extraction, and simple rules, not full AI/RAG yet. Treat `Possible Prep Work` as a useful lead, then click the source link to verify.

## Old Tomorrow Script

```bash
python canvas_tomorrow.py
```

If your shell uses `python3`:

```bash
python3 canvas_tomorrow.py
```

## Test

```bash
python -m unittest
```
