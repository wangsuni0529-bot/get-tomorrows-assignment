# Canvas Study Agent Todo

## Now

- [ ] Rotate the Canvas token that appeared in terminal output.
- [x] Confirm the new token works with `python canvas_tomorrow.py`.
- [ ] Decide whether submitted assignments should be hidden or shown as completed.

## Phase 1: Better Assignment View

- [x] Split Canvas API calls from agenda logic.
- [x] Add flexible date windows: next 3 and 7 days.
- [x] Add assignment submission status.
- [x] Rank missing and unsubmitted due-soon work above submitted work.

## Phase 2: Beyond Assignments

- [x] Read Canvas modules.
- [x] Read Canvas discussion topics.
- [x] Read Canvas announcements.
- [x] Read Canvas syllabus text.
- [x] Surface reading/prep links separately from graded assignments.
- [x] Add deeper page/PDF extraction for module-linked readings.
- [ ] Add local mute/done support for possible prep work.
- [ ] Add RAG/LLM extraction to reduce false positives in Page/PDF prep tasks.

## Phase 3: Memory

- [ ] Add local SQLite database.
- [ ] Cache Canvas items across runs.
- [ ] Let user mark local prep items done.
- [ ] Store user preferences for ranking and display.

## Phase 4: RAG and Agent

- [ ] Extract text from pages, discussions, announcements, and allowed PDFs.
- [ ] Add local retrieval over extracted course materials.
- [ ] Add source-cited answers for natural-language questions.
- [ ] Wrap the deterministic tools in an agent loop.

## Phase 5: Sharing With Others

- [ ] Design OAuth login instead of pasted tokens.
- [ ] Design encrypted token storage.
- [ ] Add reconnect flow for expired/revoked access.
- [ ] Add per-user data isolation.
- [ ] Add account data export/delete.
