# Implementation Plan: Canvas Study Agent

## Overview

The current MVP proves that a local Python script can read Canvas assignments and print items due tomorrow. The next version should become a flexible study command center: it should show upcoming important work, include submission/status information, discover ungraded work from modules/pages/discussions/readings, and eventually use memory plus retrieval to personalize what matters.

## Product Goal

Help a student answer: "What should I do next, and where is the exact Canvas link or material I need?"

The agent should avoid false urgency. If an assignment is already submitted, it should say so. If a reading is ungraded but needed for tomorrow's class, it should still appear. If something is important but not due tomorrow, it should appear because the time window and workload justify it.

## Architecture Decisions

- Keep Canvas API access deterministic first. Do not use AI to guess graded assignment status when the API can provide structured fields.
- Separate data collection from ranking. Fetch raw Canvas data first, normalize it into local task records, then decide what is important.
- Treat ungraded readings and discussion instructions as retrieval problems. These may live in modules, pages, syllabus, discussion topics, files, or announcements rather than assignments.
- Add local storage before adding a cloud backend. A local SQLite database is enough for personal memory, caching, deduping, and progress tracking.
- Add LLM/RAG after the data model is stable. The model should summarize and classify content, but the source links and due dates should remain grounded in Canvas data.
- For public or friend use, move from personal tokens in `.env` to a proper OAuth flow. Do not ask friends to paste long-lived tokens into random files for a shared product.

## Phases

### Phase 1: Better Assignment View

Upgrade the script from "tomorrow only" to "upcoming work with status."

Core changes:
- Fetch assignments across a configurable window, such as next 1, 3, 7, or 14 days.
- Fetch each assignment's submission object for the current user.
- Display status: submitted, missing, late, graded, unsubmitted, no due date.
- Add simple importance ranking: due soon, not submitted, high points, requires online submission, has locked/unlocked dates.

Acceptance criteria:
- The user can run `python study_agenda.py --days 7`.
- Submitted assignments are clearly marked and not shown as urgent.
- Unsubmitted assignments due soon appear at the top.
- Every item includes course, title, due time, status, and Canvas link.

### Phase 2: Canvas Source Expansion

Expand beyond assignments into Canvas objects that often contain real work.

Sources to inspect:
- Modules: ordered weekly course content and external links.
- Pages: reading instructions, weekly overview pages, lecture prep notes.
- Discussion topics: graded and ungraded discussion posts.
- Announcements: instructor reminders and upcoming prep instructions.
- Syllabus or course front page: recurring reading expectations.
- Files: PDFs or uploaded readings linked from modules/pages.

Core changes:
- Add Canvas API functions for modules, module items, pages, discussion topics, announcements, and files.
- Store source URL, course, title, type, published date, and raw text/metadata where available.
- Print a separate "Possible prep work" section for ungraded readings/discussions.

Acceptance criteria:
- English discussion posts not listed as assignments can still appear if they are in modules or discussions.
- Reading pages/files linked from tomorrow's module or weekly page appear with direct links.
- The output distinguishes "graded assignment" from "prep / reading / discussion".

### Phase 3: Local Database and Memory

Add durable local memory so the system remembers what it has seen and what the user cares about.

Core changes:
- Add SQLite tables for courses, Canvas items, submissions, extracted materials, user notes, and user preferences.
- Cache Canvas API responses enough to avoid repeatedly scanning everything.
- Track dismissed/completed local tasks that Canvas does not know about.
- Store user preferences, such as "English readings matter before class" or "hide submitted assignments unless due today."

Acceptance criteria:
- Running the tool twice does not duplicate items.
- The user can mark a non-Canvas task as done locally.
- The agent remembers ranking preferences across runs.
- The user can inspect and delete local memory.

### Phase 4: RAG for Ungraded Work

Use retrieval to find and explain relevant course materials without hallucinating.

Core changes:
- Extract text from Canvas pages, discussion prompts, announcements, linked HTML, and PDFs when allowed.
- Chunk extracted text and store embeddings locally.
- Retrieve course materials relevant to a date, course, or question.
- Use an LLM to summarize only retrieved materials, with citations back to Canvas links.

Acceptance criteria:
- Asking "what do I need to read for English tomorrow?" returns specific reading items and links.
- The answer includes source links for every claim.
- If the system cannot find evidence, it says so instead of guessing.

### Phase 5: Agent Interface

Wrap the deterministic tools in an actual assistant workflow.

Initial commands:
- `agenda`: show upcoming important work.
- `tomorrow`: show tomorrow's work and prep.
- `course ENGL`: show one course's upcoming work.
- `done <item>`: mark a local task done.
- `why <item>`: explain why this item is ranked as important.

Later interfaces:
- CLI first.
- Optional local web dashboard.
- Optional daily notification or calendar integration.
- Optional ChatGPT/Codex tool wrapper after the local functions are reliable.

Acceptance criteria:
- The user can ask a natural-language question and get a grounded answer.
- The agent can call local tools instead of relying on memory alone.
- The user can always see the exact source link.

### Phase 6: Multi-User / Friends / Public Version

This is a different security category from a personal local script.

Core changes:
- Replace pasted personal tokens with Canvas OAuth.
- Store tokens encrypted, ideally in an OS keychain or managed secrets store.
- Use refresh tokens where Canvas configuration permits it.
- Add clear permission screens explaining what data is read.
- Add data minimization: store only the fields needed for agenda and retrieval.
- Add delete/export account data features.
- Add per-user isolation at the database level.

Acceptance criteria:
- A friend can connect Canvas without sharing a token with you.
- The app can detect expired/revoked access and guide reconnection.
- User A can never see User B's courses, submissions, files, or notes.
- The privacy model is documented in plain language.

## Task List

### Task 1: Split Current Script Into Canvas Client and Agenda Logic

Description: Refactor the current single script into a small Canvas API client and pure agenda functions.

Acceptance criteria:
- Existing tomorrow output still works.
- API calls are isolated from filtering/ranking logic.
- Tests cover date filtering and sorting.

Verification:
- `venv/bin/python -m unittest`
- Manual run with the existing token.

Dependencies: None

Estimated scope: Small

### Task 2: Add Flexible Date Window

Description: Add `--days`, `--from`, and `--to` options so the user can inspect upcoming work beyond tomorrow.

Acceptance criteria:
- `--days 7` shows assignments due in the next week.
- `--days 1` matches the current tomorrow behavior when requested.
- Output is sorted by urgency and due time.

Verification:
- Unit tests for date range inclusion/exclusion.
- Manual run for `--days 7`.

Dependencies: Task 1

Estimated scope: Small

### Task 3: Add Submission Status

Description: Fetch the current user's submission for each assignment and display status.

Acceptance criteria:
- Submitted assignments show submitted status.
- Missing/unsubmitted work is visually prioritized.
- The output does not imply a submitted assignment still needs action unless resubmission is relevant.

Verification:
- Unit tests using sample submission payloads.
- Manual run confirms `Problem Set 1` status.

Dependencies: Task 1

Estimated scope: Medium

### Task 4: Add Canvas Modules and Discussions Discovery

Description: Read modules and discussions to find non-assignment tasks such as readings and discussion posts.

Acceptance criteria:
- Module items appear with course, title, type, and link.
- Discussion topics appear even when not represented as assignments.
- The tool clearly labels them as prep/non-graded unless Canvas says otherwise.

Verification:
- Unit tests with sample module/discussion payloads.
- Manual check against English course.

Dependencies: Task 1

Estimated scope: Medium

### Task 5: Add Local SQLite Storage

Description: Store normalized Canvas items and local user state.

Acceptance criteria:
- Items are deduped across runs.
- User can mark local prep items done.
- Cache can be cleared.

Verification:
- Unit tests against a temporary SQLite database.
- Manual run twice confirms no duplicates.

Dependencies: Tasks 2-4

Estimated scope: Medium

### Task 6: Add Basic Importance Ranking

Description: Rank items by due date, status, estimated effort, points, course meeting date, and user preferences.

Acceptance criteria:
- Unsubmitted due-soon assignments rank above submitted assignments.
- Ungraded prep work can rank high when it appears before an upcoming class.
- The output explains the ranking reason in one short phrase.

Verification:
- Unit tests for ranking scenarios.
- Manual review of a 7-day agenda.

Dependencies: Tasks 3-5

Estimated scope: Medium

### Task 7: Add RAG Extraction Prototype

Description: Extract text from Canvas pages/discussions/PDFs and retrieve relevant chunks for questions.

Acceptance criteria:
- The system can answer a course-specific reading question using retrieved text.
- Answers include links to source Canvas materials.
- Unknown answers are handled honestly.

Verification:
- Test with stored sample course materials.
- Manual question: "What do I need to read for English tomorrow?"

Dependencies: Tasks 4-5

Estimated scope: Medium

### Task 8: Add Natural-Language Agent Wrapper

Description: Let the user ask questions while the agent calls deterministic local tools.

Acceptance criteria:
- User can ask "What should I do this week?"
- The answer is based on tool output and retrieved sources.
- The agent does not expose tokens or raw private data unnecessarily.

Verification:
- Manual conversation tests.
- Privacy review of prompts and logs.

Dependencies: Tasks 5-7

Estimated scope: Medium

### Task 9: Design Multi-User Security Model

Description: Create a separate design before allowing friends or public users.

Acceptance criteria:
- OAuth connection flow is specified.
- Token storage and refresh behavior are specified.
- User data isolation and deletion are specified.
- Plain-language privacy explanation exists.

Verification:
- Design review before implementation.

Dependencies: Personal version working reliably

Estimated scope: Medium

## Checkpoints

### Checkpoint A: Personal Agenda v2

After Tasks 1-3:
- Upcoming assignments work for configurable windows.
- Submission status is visible.
- The CLI no longer over-warns about submitted work.

### Checkpoint B: Study Prep v1

After Tasks 4-6:
- Modules, discussions, readings, and announcements are included.
- The output separates graded work from prep work.
- Ranking starts to feel useful rather than just chronological.

### Checkpoint C: Real Agent Prototype

After Tasks 7-8:
- The system can answer natural-language questions using local tools and retrieved Canvas sources.
- It cites links.
- It can remember local preferences and done/dismissed state.

### Checkpoint D: Shareable Product Readiness

After Task 9:
- Security model is clear enough to invite another user safely.
- No one is asked to send or expose personal tokens.
- Expiration/reconnection behavior is designed.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Canvas API does not expose all course materials cleanly | High | Start with modules/pages/discussions, then add extraction only where links are available. |
| Ungraded readings are ambiguous | High | Use retrieval plus source links; never invent work without evidence. |
| Submission status varies by assignment type | Medium | Normalize status from Canvas submission fields and show raw fallback labels when uncertain. |
| Token leakage | High | Keep `.env` local, rotate exposed tokens, avoid logging token values, move to OAuth for multi-user. |
| Public use creates privacy/compliance burden | High | Keep personal local version first; design OAuth and data deletion before sharing. |
| Token expiration or revocation breaks trust | Medium | Detect 401/403, show reconnect instructions, later use OAuth refresh where available. |

## Open Questions

- Which courses matter most for the next prototype: English, HPM540, or all active courses?
- Do you want submitted assignments hidden by default or shown in a completed section?
- Should the first flexible view be `next 7 days`, `this week`, or `before next class`?
- Do your Canvas modules/pages contain the reading links, or are readings mostly in syllabus/files/announcements?
- Do you want this to stay CLI-first for now, or become a small local web dashboard soon?
