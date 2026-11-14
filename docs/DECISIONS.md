# Decision log

Short notes on choices that shape the product. Each one records the context, the decision, the alternatives, why, and the trade-off.

## 1. Deterministic Canvas data before any language model

**Context.** Due dates, points, and submission state already exist as structured Canvas fields. A model that "reads" the course and invents a deadline would be hard to trust.

**Decision.** Assignment status, due time, and links come from the Canvas API. A model is not on the path that builds the agenda.

**Alternatives.** Send course pages to an LLM and ask it to list the work. Use retrieval first and let the model decide what is due.

**Why.** The API is the source of truth for graded work. The chat box only chooses which deterministic tool to call.

**Trade-off.** The agent cannot paraphrase a messy week in natural language. It also cannot hallucinate a due date. Wording quality is limited to the templates and the evidence snippets.

## 2. Separate collection from ranking

**Context.** The first script fetched assignments and printed whatever was due tomorrow. Later questions needed a window, submission status, and a distinction between urgent and optional.

**Decision.** The Canvas client returns raw payloads. Normalization turns an assignment into a local record. Agenda code then places that record in a bucket. Prep extraction is a separate step that returns its own records.

**Alternatives.** Rank inside the HTTP functions. One module that fetches, filters, and prints.

**Why.** The ranking rules can be tested without the network. Fetch errors can be reported without changing how an item is sorted.

**Trade-off.** There are more modules, and a reader has to follow a record across them. That is cheaper than a single file that does every job.

## 3. Label ungraded material as possible prep

**Context.** Readings and discussions often live in modules, pages, announcements, and the syllabus. They matter before class and they are not assignments.

**Decision.** Those items are a separate section, always labeled possible prep, with a source, a confidence, and the text that matched.

**Alternatives.** Hide anything without a due date. Promote a strong text match into the same list as graded work.

**Why.** A missing reading and a missing problem set are different promises. The student should see the guess and the evidence, then open Canvas and check.

**Trade-off.** The prep scan still produces false positives. Keyword rules are blunt. The label and the evidence are how the product stays honest about that.

## 4. Do not send the Canvas token to non-Canvas sites

**Context.** Module items sometimes link to a publisher, a Google Doc, or a public PDF. The token is a bearer credential for every course the student can see.

**Decision.** `headers_for_url` attaches the Authorization header only when the URL host matches `CANVAS_BASE_URL`. Other downloads, if they happen at all, go out without it. The local server binds to `127.0.0.1`.

**Alternatives.** Fetch every link with the token. Refuse to open anything outside Canvas. Proxy external links through a hosted backend.

**Why.** A useful prep scan can look at Canvas pages and files. It should not present the token to some other host.

**Trade-off.** Readings that live only on another site are invisible unless the student clicks through. That is the right miss.

## 5. Local storage before a cloud backend

**Context.** The first users are one student on one computer. The memory we need is a mute list and, later, preferences.

**Decision.** Muted ids live in `.study_agent_memory.json` on the machine that runs the tool. There is no account and no hosted database.

**Alternatives.** SQLite immediately. A multi-user database now, with accounts "for later."

**Why.** A mute list does not need a server. A cloud account would require storing a Canvas token somewhere else.

**Trade-off.** The mute list does not follow the student to another computer. The file is a shallow JSON document, not a full history. SQLite is still a reasonable next step if the local memory grows past a mute list.

## 6. OAuth before any multi-user version

**Context.** A friend should not paste a long-lived Canvas token into someone else's project.

**Decision.** The shareable product, if it is built, uses Canvas OAuth, encrypted token storage, and per-user isolation. Until then, the shared experience is the fictional demo, and the real experience is local.

**Alternatives.** Ask classmates to copy `.env`. Store pasted tokens on a small server.

**Why.** A pasted token is a password. The demo already lets a recruiter or a classmate use the interface.

**Trade-off.** Nobody else can connect a real Canvas account from the public site today. That is intentional.

## 7. Demo mode uses fictional data

**Context.** A portfolio link has to work for someone with no UNC login and no token. The real UI is the thing worth showing.

**Decision.** `frontend/demo-data.json` holds made-up courses, including overdue work, a low-priority item, and possible prep. The page uses it when the API is unreachable or the token is missing. A "Demo data" badge stays visible. Dates are offsets from today.

**Alternatives.** Screenshot-only README. A public server that stores real tokens. Disable the buttons in the static build.

**Why.** The interaction is the product: change the window, switch to focused, mute something. Sample data keeps that working as a static site.

**Trade-off.** The demo router is a JavaScript copy of the Python router. The two can drift. The sample week is curated, so it will not show the messy false positives of a real prep scan.

## 8. Deploy the demo as a static site

**Context.** The Python server is local on purpose. The thing to publish is the frontend plus the sample file.

**Decision.** GitHub Actions uploads `frontend/` and deploys it with `actions/deploy-pages`. Asset URLs are relative, so they work under `https://wangsuni0529-bot.github.io/get-tomorrows-assignment/`.

**Alternatives.** Host the Python app. Use a relative-path hack only in development and absolute `/style.css` in production.

**Why.** A static deploy has no token to leak and no server to keep up. Project Pages serves the site from a subpath, so root-absolute asset paths would 404.

**Trade-off.** The published site cannot read a visitor's Canvas. That is the demo's job. Real Canvas stays on localhost.

## 9. Split the Canvas module by responsibility

**Context.** `study_tools.py` was 1,327 lines. It fetched HTTP, normalized assignments, guessed prep from prose, ranked both, and formatted the terminal. `canvas_tomorrow.py` repeated the HTTP and env code.

**Decision.** Split the package into a Canvas client, assignment normalization, prep text rules, prep collection, and agenda ranking. The tomorrow command and the web server call those pieces. Public functions have type hints and a one-line docstring.

**Alternatives.** Leave the file and add comments. Split every helper into its own module.

**Why.** A change to ranking should not require reading the HTTP pagination loop. Tests already covered the pure functions, so the move could be checked.

**Trade-off.** `prep.py` is still the largest file, at 656 lines, because it walks several Canvas object types. The keyword lists are data, and they live with the rules that use them.

## 10. CI runs tests and Ruff

**Context.** The original checks were `python -m unittest` on a laptop. Nothing stopped a broken import or an unused variable from landing on `main`.

**Decision.** `requirements.txt` pins the runtime libraries, pytest, and Ruff. GitHub Actions installs them and runs `ruff check src tests` and `pytest`. Ruff is configured for pycodestyle errors, pyflakes, isort, and pyupgrade, at 100 columns, targeting Python 3.12.

**Alternatives.** A formatter-only pass. A long list of optional lint rules on day one.

**Why.** The useful bar is "the tests pass and the imports are real." A huge rule set would have turned the split into a style project.

**Trade-off.** Ruff does not require docstrings or type hints. Those are a review habit, not a gate. The line length of 100 is wider than the default 88 so the existing test strings stayed readable.

## Before and after

Measured on the original `main` tree and on this branch. Lint uses the Ruff config in `pyproject.toml` (E, F, I, UP, line length 100, target Python 3.12). "Largest file" is source lines.

| | Before | After |
| --- | ---: | ---: |
| `canvas_tomorrow.py` | 169 | — |
| `study_agenda.py` | 47 | — |
| `study_agent.py` | 259 | — |
| `study_memory.py` | 68 | — |
| `study_tools.py` | 1,327 | — |
| `web_server.py` | 366 | — |
| `client.py` | — | 259 |
| `normalize.py` | — | 120 |
| `prep_text.py` | — | 371 |
| `prep.py` | — | 656 |
| `agenda.py` | — | 310 |
| `agent.py` | — | 264 |
| `memory.py` | — | 76 |
| `tomorrow.py` | — | 95 |
| `web.py` | — | 393 |
| Largest file | 1,327 lines (`study_tools.py`, 39,540 bytes) | 656 lines (`prep.py`, 20,499 bytes) |
| Tests | 37 | 44 |
| Lint findings | 33 | 0 |
| CI | none | GitHub Actions, pytest and Ruff |
| Deploy | none | https://wangsuni0529-bot.github.io/get-tomorrows-assignment/ |

The original 37 tests are still in the suite. The extra tests cover an undated assignment, the token header rule, missing and present Canvas config, and the shape of the fictional demo file.
