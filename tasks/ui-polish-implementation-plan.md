# UI Polish Implementation Plan: Local Study Agent Dashboard

## Goal

Polish the local Study Agent web UI so the user can open a local URL, ask study questions, switch views, refresh Canvas results, and understand the agent's answer without returning to VS Code or Terminal.

This plan is only for the local version. It does not include public deployment, account management, multi-user login, database work, or friend beta infrastructure.

## Revised Product Direction

The main panel is the agent workspace. It should contain the core interaction:

- Ask box
- Suggested questions
- Time window buttons
- Mode selector
- Source controls
- Refresh / last checked state
- Structured task cards

The left panel is not the control center for this local MVP. It is a lightweight app shell that can eventually support account/workspace/history features, but today it should not hide essential controls.

## Core Principle

Do not make users hunt in a collapsible sidebar for the controls they need every day.

The user should be able to answer these questions from the main panel within 10 seconds:

- What did the agent check?
- What time window am I looking at?
- Is this strict or broad scanning?
- When was Canvas last refreshed?
- Which task card should I act on first?
- What should I click next?

## Current State

Already exists:

- Local web server: `web_server.py`
- Static frontend: `frontend/index.html`, `frontend/style.css`, `frontend/app.js`
- Quick buttons: Tomorrow, Overdue, Next 3 Days, This Week, Prep / Readings
- Chatbox
- Summary counts
- Structured task cards
- Canvas links

Main gaps:

- Left panel currently looks like a workflow sidebar, but those steps are not real user actions.
- Main panel does not yet include all primary controls.
- No visible mode selector.
- No source toggles.
- No suggested question chips.
- Freshness is present but not prominent enough.
- Task cards need clearer information hierarchy and action entry points.
- No web-based mute / not relevant feedback.

## Page Element Plan

### 1. Left Panel: Local App Shell

**Description:** Keep the left panel light. It should identify the product and show local-only status, but it should not contain the main controls.

**What it should contain now:**

- Study Agent name
- Local Canvas status
- Short local privacy note
- Optional compact status:
  - Local mode
  - Token stored in `.env`
  - Muted items count if available

**What it should not contain now:**

- Time window buttons
- Mode selector
- Source toggles
- Account management
- Billing
- Friend invite
- Full chat history

**Future placeholders allowed:**

- Account: disabled / "future public version"
- History: disabled / "not needed for local MVP yet"
- Settings: optional, only if it points to real local preferences

**Why this matters:** The left panel can be hidden, so essential controls should not live there. Since the current product is local-only, account management would feel fake and distract from the actual agent experience.

**Standard of done:**

- The left panel is useful but non-essential.
- The app still works if the left panel is hidden on smaller screens.
- No public/multi-user promise appears in the local UI.

**Tests:**

- Manual: hide/narrow the sidebar and confirm the user can still ask, switch time window, refresh, and read results.
- Manual: verify the sidebar does not show fake account or history functionality.

### 2. Main Panel: Primary Agent Controls

**Description:** The main panel should be the place where the user asks questions and controls how the agent checks Canvas.

**Controls to include:**

- Chatbox
- Suggested question chips
- Time window buttons:
  - Today
  - Tomorrow
  - Next 3 Days
  - This Week
  - Overdue
- Mode selector:
  - Focused
  - Balanced
  - Catch-all
- Source controls:
  - Assignments
  - Discussions
  - Modules / Pages
  - Announcements
  - Syllabus
- Refresh button
- Last checked timestamp

**Why this matters:** These are not secondary settings. They directly shape the agent answer and belong near the question/answer flow.

**Standard of done:**

- A user can run the agent with one click.
- A user can type a natural-language question.
- A user can change time window and mode without using the sidebar.
- Current selections remain visible after results load.

**Tests:**

- Manual: click each time window and verify the result updates.
- Manual: switch Focused/Balanced/Catch-all and verify the agent explanation changes.
- Manual: refresh reruns the current selected view.

### 3. Suggested Questions

**Description:** Suggested questions should teach users what the agent can do.

**Prompts to include:**

- What should I do tomorrow?
- What is due this week?
- What readings or prep do I have?
- Am I missing anything?
- Only show hard deadlines.
- Show everything I might need for class.

**Behavior decision:** Suggested question chips should run immediately when clicked. This is faster and makes them feel like real commands, not passive examples.

**Why this matters:** New users do not know the agent's boundaries. Suggested questions are lightweight onboarding.

**Standard of done:**

- Chips are visible near the chatbox.
- Clicking a chip submits that prompt.
- Off-topic prompts still get a boundary response instead of calling Canvas.

**Tests:**

- Manual: click every suggested prompt and confirm the response type.
- Unit: existing router tests continue to pass.

### 4. Time Window Buttons

**Description:** Keep time windows in the main panel, because they are part of the immediate question.

**Options:**

- Today
- Tomorrow
- Next 3 Days
- This Week
- Overdue

**Default:** Tomorrow.

**Why this matters:** Students think in time windows: "today," "tomorrow," "this week." This is the fastest path to value.

**Standard of done:**

- Selected time window is visibly active.
- Switching time window refreshes results.
- Overdue mode does not mix in future assignments.

**Tests:**

- Unit: `days=0` remains valid for overdue.
- Unit: `days > 14` is rejected.
- Manual: each button updates task sections and counts.

### 5. Mode Selector

**Description:** Add a sensitivity control that changes how broad the agent should be.

**Modes:**

- Focused: hard-deadline assignments only.
- Balanced: hard-deadline assignments plus likely prep/readings/discussions.
- Catch-all: include broader possible prep, including lower-confidence syllabus/announcement/module signals.

**Default:** Balanced.

**Why this matters:** This gives users emotional control. Some days they want no noise; other days they want the agent to surface anything that might matter.

**Standard of done:**

- Mode is visible in the main panel.
- Current mode remains visible near the task results.
- Focused hides Possible Prep Work.
- Balanced and Catch-all include prep but label confidence clearly.

**Tests:**

- Unit: Focused maps to `include_prep=False`.
- Unit: Balanced maps to `include_prep=True`.
- Manual: switching mode changes result scope.

### 6. Source Controls

**Description:** Let users choose which Canvas source categories are included.

**Sources:**

- Assignments
- Discussions
- Modules / Pages
- Announcements
- Syllabus

**MVP behavior:**

- Assignments stays on by default and can be visually treated as the core source.
- Other sources can be toggled on/off.
- If backend source-specific fetching is not split yet, filter returned prep items by source after collection.

**Why this matters:** Syllabus and announcements may create noise. Source toggles let the user debug and tune the agent.

**Standard of done:**

- Toggling Syllabus off hides syllabus prep cards.
- Toggling Discussions off hides discussion prep cards.
- The UI answer says which source categories were checked or shown.

**Tests:**

- Backend: source filter removes excluded prep source types.
- Manual: turn off Syllabus and verify syllabus cards disappear.

### 7. Freshness / Refresh

**Description:** Make data freshness explicit in the main panel and answer state.

**Display:**

- Last checked timestamp
- Current view label, e.g. `Tomorrow / Balanced`
- Refresh button
- Loading state while Canvas is being checked

**Why this matters:** Homework data is time-sensitive. Users need to trust that this is a fresh Canvas read.

**Standard of done:**

- Every successful response updates last checked.
- Refresh uses the current selected time window, mode, and sources.
- Errors are plain language and never expose token details.

**Tests:**

- Existing backend serialization test covers `generatedAtLabel`.
- Manual: refresh updates loading state and timestamp.

### 8. Output Task Sections

**Description:** After the agent checks Canvas, show structured task sections. The output should be card-first, not paragraph-first.

**Sections:**

- Overdue / Missing
- Due Today
- Due Tomorrow
- Upcoming
- Possible Prep Work
- Low Priority / Optional
- Submitted / Done

**Why this matters:** This is the actionable part. Users should not have to parse a paragraph to decide what to do.

**Standard of done:**

- Important sections appear before low-confidence sections.
- Empty sections are hidden.
- If no tasks are found, show a helpful empty state.

**Tests:**

- Manual: query Tomorrow and This Week.
- Manual: query Focused and confirm Possible Prep Work is hidden.
- Manual: empty state is readable if no tasks exist.

### 9. Output Task Cards

**Description:** Each task card should explain what it is, why it appeared, and what to do next.

**Assignment card fields:**

- Course
- Title
- Status
- Due time
- Points if available
- Priority
- Why this appears
- Open Canvas

**Prep card fields:**

- Course
- Title
- Source
- Confidence
- Completion status for discussion posts
- No Canvas due date label
- Evidence
- Open Canvas

**Why this matters:** Prep work is ambiguous by nature. Source, confidence, and evidence make the agent trustworthy.

**Standard of done:**

- Every card clearly shows submission/completion status.
- Every card has a visible Canvas entry point when a link exists.
- Assignment cards show course, title, status, due time, points if available, priority, and why it appeared.
- Prep cards show course, title, source, confidence, evidence, completion status if available, and why it appeared.
- No card is just a title and link.

**Tests:**

- Manual: inspect one assignment card and one prep card.
- Manual: click Canvas link and confirm it opens.

### 10. Feedback Actions: Mute / Not Relevant

**Description:** Add a lightweight feedback loop after results appear.

**MVP scope:**

- Add `Mute` for low-priority assignments using existing local memory.
- Add `Not relevant` as either a disabled placeholder or a local-only action if stable prep keys are added.

**Why this matters:** This is the beginning of agent memory. It makes repeated noisy reminders less annoying.

**Standard of done for first build:**

- Low-priority assignment cards can be muted from the web UI.
- Muted assignments disappear after refresh.
- Prep mute is either implemented with stable IDs or clearly left out.

**Tests:**

- Backend: mute endpoint stores assignment ID.
- Manual: click mute, refresh, item stays hidden.

## Backend/API Plan

### Existing endpoints

- `GET /api/agenda?days=1&includePrep=true`
- `POST /api/chat`

### Planned additions

- Add `mode` query param:
  - `focused`
  - `balanced`
  - `catch_all`
- Add `sourceTypes` query param:
  - comma-separated source filters, e.g. `discussion,module,page,announcement,syllabus`
- Add stable card fields where missing:
  - assignment ID
  - source type
  - completion status
  - evidence
  - Canvas URL
- Add local memory endpoint:
  - `POST /api/mute`

## Implementation Tasks

### Task 1: Define Main Panel State Contract

**Description:** Add helper functions that map time window, mode, and source choices into API behavior.

**Acceptance criteria:**

- [ ] Focused maps to hard-deadline-only behavior.
- [ ] Balanced maps to prep-enabled behavior.
- [ ] Source filters can hide selected prep source types.

**Verification:**

- [ ] Unit tests pass with `venv/bin/python -m unittest`.

**Files likely touched:**

- `web_server.py`
- `test_web_server.py`

**Estimated scope:** Small.

### Task 2: Restructure Left Panel Into Local App Shell

**Description:** Remove fake workflow navigation and keep the left panel as lightweight local status/future shell.

**Acceptance criteria:**

- [ ] Left panel does not contain primary controls.
- [ ] Left panel does not show fake account/history features.
- [ ] Main panel remains fully usable without the left panel.

**Verification:**

- [ ] Manual browser check at `http://127.0.0.1:8000`.

**Files likely touched:**

- `frontend/index.html`
- `frontend/style.css`

**Estimated scope:** Small.

### Task 3: Move Primary Controls Into Main Panel

**Description:** Put time window buttons, mode selector, source controls, refresh, and chatbox together in the main agent workspace.

**Acceptance criteria:**

- [ ] Time window controls are in the main panel.
- [ ] Mode selector is in the main panel.
- [ ] Source toggles are in the main panel.
- [ ] Refresh uses the current selections.

**Verification:**

- [ ] Manual browser check.
- [ ] Existing tests still pass.

**Files likely touched:**

- `frontend/index.html`
- `frontend/app.js`
- `frontend/style.css`

**Estimated scope:** Medium.

### Task 4: Add Suggested Question Chips

**Description:** Add clickable suggested prompts near the chatbox.

**Acceptance criteria:**

- [ ] Suggested questions are visible.
- [ ] Clicking a prompt runs it immediately.
- [ ] Off-topic questions still do not call Canvas.

**Verification:**

- [ ] Manual browser check.
- [ ] Existing router tests still pass.

**Files likely touched:**

- `frontend/index.html`
- `frontend/app.js`
- `frontend/style.css`

**Estimated scope:** Small.

### Task 5: Refine Output Sections and Task Cards

**Description:** Make the answer state card-first, with highly scannable assignment and prep cards.

**Acceptance criteria:**

- [ ] Sections appear in priority order.
- [ ] Assignment cards show due/status/priority/reason/link.
- [ ] Prep cards show source/confidence/evidence/completion/link.
- [ ] Status and Canvas link are visually easy to find.

**Verification:**

- [ ] Manual browser check.
- [ ] Existing tests still pass.

**Files likely touched:**

- `frontend/app.js`
- `frontend/style.css`
- optional: `web_server.py`

**Estimated scope:** Medium.

### Task 6: Add Compact Result Header

**Description:** Add a compact header above task sections for counts, selected time window, selected mode, selected sources, and last refresh time. This is not a natural-language answer card.

**Acceptance criteria:**

- [ ] Header shows active/prep/done counts.
- [ ] Header shows selected time window and mode.
- [ ] Header shows last refreshed timestamp.
- [ ] Header stays visually secondary to task cards.

**Verification:**

- [ ] Manual browser check.
- [ ] Existing tests still pass.

**Files likely touched:**

- `frontend/index.html`
- `frontend/app.js`
- `frontend/style.css`
- optional: `web_server.py`

**Estimated scope:** Medium.

### Task 7: Add Web Mute For Low-Priority Assignments

**Description:** Add web-based mute for low-priority assignment reminders.

**Acceptance criteria:**

- [ ] Low-priority assignment cards show Mute.
- [ ] Clicking Mute hides the item after refresh.
- [ ] Prep mute is deferred unless stable prep IDs are added.

**Verification:**

- [ ] Backend test for `POST /api/mute`.
- [ ] Manual browser check.

**Files likely touched:**

- `web_server.py`
- `study_memory.py`
- `frontend/app.js`
- `frontend/style.css`
- `test_web_server.py`

**Estimated scope:** Medium.

## Checkpoints

### Checkpoint A: Main Controls Work

After Tasks 1-4:

- [ ] User can ask, click suggested prompts, change time window, change mode, toggle sources, and refresh from the main panel.
- [ ] Left panel contains no essential controls.
- [ ] Tests pass.

### Checkpoint B: Answer State Is Card-First

After Tasks 5-6:

- [ ] The result is driven by clear task cards, not a paragraph answer.
- [ ] Each task card provides status, evidence, and next action.
- [ ] Empty/loading/error states are understandable.

### Checkpoint C: Feedback Loop Exists

After Task 7:

- [ ] User can mute at least low-priority assignment reminders.
- [ ] Muted items persist locally.
- [ ] No multi-user/database assumptions were introduced.

## Testing Strategy

Automated:

- `venv/bin/python -m unittest`
- Unit tests for mode parsing and API params.
- Unit tests for source filtering.
- Unit tests for mute endpoint if implemented.

Manual browser checks:

- Open `http://127.0.0.1:8000`.
- Confirm default view is Tomorrow + Balanced.
- Switch to Focused and confirm prep disappears.
- Switch to Balanced and confirm prep can appear.
- Toggle Syllabus off and confirm syllabus prep disappears.
- Ask `what should I do tomorrow`.
- Ask `what is due tomorrow`.
- Ask an off-topic question and confirm Canvas is not called.
- Click Canvas links.
- Refresh current view.

Safety checks:

- Do not expose `CANVAS_TOKEN` in frontend JavaScript, HTML, logs, or API responses.
- Keep server bound to `127.0.0.1` for local-only use.
- Do not add account management until moving to a real multi-user architecture.

## Not Doing Today

- Public deployment.
- Friend beta.
- Database.
- OAuth.
- Account management.
- Full chat history.
- Notifications.
- Calendar integration.
- Full RAG memory.

## Open Questions For Confirmation

- Should Syllabus be on by default in Balanced, or only in Catch-all?
- Should source toggles live directly under the mode selector, or inside a small "Sources checked" disclosure?
- Should `Not relevant` be postponed until prep items have stable local IDs?
