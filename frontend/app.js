const agendaEl = document.querySelector("#agenda");
const agentMessageEl = document.querySelector("#agent-message");
const activeCountEl = document.querySelector("#active-count");
const prepCountEl = document.querySelector("#prep-count");
const doneCountEl = document.querySelector("#done-count");
const updatedAtEl = document.querySelector("#updated-at");
const currentScopeEl = document.querySelector("#current-scope");
const chatForm = document.querySelector("#chat-form");
const messageInput = document.querySelector("#message");
const refreshButton = document.querySelector("#refresh-button");
const timeButtons = [...document.querySelectorAll("#time-controls button")];
const modeButtons = [...document.querySelectorAll("#mode-controls button")];
const sourceCheckboxes = [...document.querySelectorAll(".source-controls input:not([disabled])")];
const suggestedPromptButtons = [...document.querySelectorAll(".suggested-prompts button")];
const dataBadge = document.querySelector("#data-badge");
const demoNote = document.querySelector("#demo-note");
const connectionLabel = document.querySelector("#connection-label");
const connectionPill = document.querySelector("#connection-pill");
const privacyCopy = document.querySelector("#privacy-copy");

const MUTED_ASSIGNMENTS = "gta-demo-muted-assignments";
const MUTED_PREP = "gta-demo-muted-prep";
const ALL_SOURCES = ["discussion", "module", "page", "file", "pdf", "announcement", "syllabus"];

const OFF_TOPIC_KEYWORDS = new Set([
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
]);

const STUDY_KEYWORDS = new Set([
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
]);

const TIME_KEYWORDS = new Set(["today", "tomorrow", "tmrw", "week", "7", "3", "three"]);

const state = {
  days: "1",
  timeLabel: "Tomorrow",
  mode: "balanced",
  isLoading: false,
  demo: true,
  demoData: null,
};

function appBase() {
  const url = new URL(window.location.href);
  if (url.pathname.endsWith(".html")) {
    url.pathname = url.pathname.slice(0, url.pathname.lastIndexOf("/") + 1);
  } else if (!url.pathname.endsWith("/")) {
    url.pathname += "/";
  }
  return url;
}

function appUrl(path) {
  return new URL(path, appBase()).toString();
}

function selectedSources() {
  return sourceCheckboxes.filter((input) => input.checked).map((input) => input.value);
}

function apiSourceTypes() {
  const selected = new Set(selectedSources());
  const values = [];

  if (selected.has("discussion")) values.push("discussion");
  if (selected.has("module")) values.push("module", "page", "file", "pdf");
  if (selected.has("announcement")) values.push("announcement");
  if (selected.has("syllabus")) values.push("syllabus");

  return values.join(",");
}

function selectedSourceSet() {
  const values = apiSourceTypes().split(",").filter(Boolean);
  return new Set(values.length ? values : ALL_SOURCES);
}

function modeLabel(mode) {
  if (mode === "focused") return "Focused";
  if (mode === "catch_all") return "Catch-all";
  return "Balanced";
}

function updateSelectedButtons() {
  timeButtons.forEach((button) => {
    button.classList.toggle("is-selected", button.dataset.days === state.days);
  });

  modeButtons.forEach((button) => {
    button.classList.toggle("is-selected", button.dataset.mode === state.mode);
  });

  currentScopeEl.textContent = `${state.timeLabel} / ${modeLabel(state.mode)}`;
}

function updateChrome() {
  dataBadge.hidden = false;
  if (state.demo) {
    dataBadge.textContent = "Demo data";
    dataBadge.classList.remove("is-live");
    demoNote.hidden = false;
    connectionLabel.textContent = "Demo data";
    connectionPill.classList.add("is-demo");
    privacyCopy.textContent =
      "This preview uses fictional courses. No Canvas token is sent anywhere.";
    return;
  }

  dataBadge.textContent = "Your Canvas";
  dataBadge.classList.add("is-live");
  demoNote.hidden = true;
  connectionLabel.textContent = "Local Canvas";
  connectionPill.classList.remove("is-demo");
  privacyCopy.textContent =
    "Your Canvas token stays in this computer's .env file and is only sent to Canvas.";
}

function setLoading(message) {
  state.isLoading = true;
  refreshButton.disabled = true;
  agentMessageEl.textContent = message;
  agendaEl.replaceChildren();
  activeCountEl.textContent = "-";
  prepCountEl.textContent = "-";
  doneCountEl.textContent = "-";
  updatedAtEl.textContent = state.demo ? "Loading demo" : "Checking Canvas";
}

function setReady() {
  state.isLoading = false;
  refreshButton.disabled = false;
}

function setError(message) {
  setReady();
  agentMessageEl.textContent = message;
  const empty = document.createElement("div");
  empty.className = "empty-state";
  empty.textContent = state.demo
    ? "The sample agenda could not be loaded."
    : "Check that the local server is running and your Canvas .env settings are correct.";
  agendaEl.replaceChildren(empty);
  updatedAtEl.textContent = "Error";
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.error?.message || "Something went wrong");
  }

  return payload;
}

function badgeTone(value) {
  const text = String(value || "").toLowerCase();

  if (text.includes("missing") || text.includes("not posted") || text.includes("overdue")) {
    return "danger";
  }

  if (text.includes("possible") || text.includes("unsubmitted") || text.includes("low") || text.includes("medium")) {
    return "warning";
  }

  if (text.includes("submitted") || text.includes("graded") || text === "posted" || text.includes("high")) {
    return "done";
  }

  return "";
}

function makeBadge(label, value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }

  const badge = document.createElement("span");
  badge.className = `badge ${badgeTone(value)}`.trim();
  badge.textContent = label ? `${label}: ${value}` : value;
  return badge;
}

function makeDetail(label, value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }

  const row = document.createElement("div");
  row.className = "detail-row";

  const term = document.createElement("dt");
  term.textContent = label;

  const desc = document.createElement("dd");
  desc.textContent = value;

  row.append(term, desc);
  return row;
}

function renderTaskCard(item, sectionKey) {
  const card = document.createElement("article");
  card.className = `task-card ${item.type === "prep" ? "prep-card" : "assignment-card"}`;

  const top = document.createElement("div");
  top.className = "task-topline";

  const course = document.createElement("span");
  course.className = "course";
  course.textContent = item.course;

  const due = makeBadge("", item.dueLabel);
  top.append(course);
  if (due) top.append(due);

  const title = document.createElement("p");
  title.className = "title";
  title.textContent = item.title;

  const meta = document.createElement("div");
  meta.className = "meta";

  [
    makeBadge("Status", item.status),
    makeBadge("Priority", item.priority),
    makeBadge("Source", item.sourceType),
    makeBadge("Confidence", item.confidence),
    makeBadge("Completion", item.completionStatus),
  ]
    .filter(Boolean)
    .forEach((badge) => meta.append(badge));

  const disclosure = document.createElement("details");
  disclosure.className = "card-disclosure";

  const summary = document.createElement("summary");
  summary.textContent = "Details";

  const details = document.createElement("dl");
  details.className = "card-details";

  [
    makeDetail("Due", item.dueLabel),
    makeDetail("Points", item.points === undefined || item.points === null ? null : `${item.points}`),
    makeDetail("Why", item.reason),
    makeDetail("Evidence", item.evidence),
    makeDetail("Completion check", item.completionReason),
  ]
    .filter(Boolean)
    .forEach((row) => details.append(row));
  disclosure.append(summary, details);

  const actions = document.createElement("div");
  actions.className = "card-actions";

  if (item.url) {
    const link = document.createElement("a");
    link.className = "canvas-link";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = "Open Canvas";
    actions.append(link);
  }

  if (sectionKey === "low_priority" && item.assignmentId) {
    const mute = document.createElement("button");
    mute.className = "secondary-action";
    mute.type = "button";
    mute.textContent = "Mute";
    mute.addEventListener("click", () => muteItem({ assignmentId: item.assignmentId }, card));
    actions.append(mute);
  }

  if (item.type === "prep" && item.prepKey) {
    const mute = document.createElement("button");
    mute.className = "secondary-action";
    mute.type = "button";
    mute.textContent = "Mute";
    mute.addEventListener("click", () => muteItem({ type: "prep", prepKey: item.prepKey }, card));
    actions.append(mute);
  }

  card.append(top, title, meta, disclosure, actions);
  return card;
}

function renderAgenda(agenda) {
  setReady();
  activeCountEl.textContent = agenda.summary.active;
  prepCountEl.textContent = agenda.summary.prep;
  doneCountEl.textContent = agenda.summary.done;
  updatedAtEl.textContent = agenda.generatedAtLabel;
  currentScopeEl.textContent = `${state.timeLabel} / ${modeLabel(agenda.selected?.mode || state.mode)}`;

  const sourceText = selectedSources().join(", ");
  const prefix = state.demo ? "Demo data. " : "";
  agentMessageEl.textContent = `${prefix}Showing ${state.timeLabel} in ${modeLabel(state.mode)} mode. Sources: assignments${sourceText ? `, ${sourceText}` : ""}.`;

  const visibleSections = agenda.sections.filter((section) => section.items.length > 0);

  if (visibleSections.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No tasks in this view.";
    agendaEl.replaceChildren(empty);
    return;
  }

  const nodes = visibleSections.map((section) => {
    const wrapper = document.createElement("section");
    wrapper.className = "section";

    const header = document.createElement("div");
    header.className = "section-header";

    const title = document.createElement("h2");
    title.textContent = section.label;

    const count = document.createElement("span");
    count.textContent = `${section.items.length} item${section.items.length === 1 ? "" : "s"}`;

    header.append(title, count);

    const cards = document.createElement("div");
    cards.className = "cards";
    section.items.forEach((item) => cards.append(renderTaskCard(item, section.key)));

    wrapper.append(header, cards);
    return wrapper;
  });

  if (agenda.warnings?.length) {
    const warning = document.createElement("div");
    warning.className = "empty-state";
    warning.textContent = `Some prep sources could not be read: ${agenda.warnings.slice(0, 2).join(" ")}`;
    nodes.push(warning);
  }

  agendaEl.replaceChildren(...nodes);
}

function readStoredIds(key) {
  try {
    return new Set(JSON.parse(localStorage.getItem(key) || "[]").map(String));
  } catch {
    return new Set();
  }
}

function storeId(key, value) {
  const ids = readStoredIds(key);
  ids.add(String(value));
  localStorage.setItem(key, JSON.stringify([...ids]));
}

function startOfDay(date) {
  const copy = new Date(date);
  copy.setHours(0, 0, 0, 0);
  return copy;
}

function addDays(date, days) {
  const copy = startOfDay(date);
  copy.setDate(copy.getDate() + days);
  return copy;
}

function sameDay(left, right) {
  return startOfDay(left).getTime() === startOfDay(right).getTime();
}

function clockLabel(date) {
  const minutes = String(date.getMinutes()).padStart(2, "0");
  const suffix = date.getHours() >= 12 ? "PM" : "AM";
  const hour = String(date.getHours() % 12 || 12).padStart(2, "0");
  return `${hour}:${minutes} ${suffix}`;
}

function dateLabel(date) {
  const weekday = date.toLocaleDateString("en-US", { weekday: "short" });
  const month = date.toLocaleDateString("en-US", { month: "short" });
  const day = String(date.getDate()).padStart(2, "0");
  return `${weekday} ${month} ${day} ${date.getFullYear()}, ${clockLabel(date)}`;
}

function generatedLabel(date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day} ${clockLabel(date)}`;
}

function dueFromOffset(offsetDays, time) {
  const [hour, minute] = String(time || "23:59").split(":").map(Number);
  const due = addDays(new Date(), offsetDays);
  due.setHours(hour, minute, 0, 0);
  return due;
}

function demoStatus(item, due, now) {
  if (item.status === "graded" || item.status === "submitted" || item.status === "submitted late") {
    return item.status;
  }
  if (due < now) return "missing";
  return "unsubmitted";
}

function activeStatus(status) {
  return status === "unsubmitted" || status === "missing";
}

function demoSection(item, status, dates, includeSubmitted) {
  const dueDate = startOfDay(item.due);
  const low = item.priority === "low";
  const overdue = dates.overdueStart <= dueDate && dueDate < dates.today;

  if (status === "missing" && overdue && low) return "low_priority";
  if (status === "missing" && overdue) return "overdue_missing";
  if (includeSubmitted && !activeStatus(status) && dates.today <= dueDate && dueDate <= dates.windowEnd) {
    return "submitted";
  }
  if (activeStatus(status) && low && dates.overdueStart <= dueDate && dueDate <= dates.windowEnd) {
    return "low_priority";
  }
  if (activeStatus(status) && sameDay(dueDate, dates.today)) return "due_today";
  if (activeStatus(status) && sameDay(dueDate, dates.tomorrow)) return "due_tomorrow";
  if (activeStatus(status) && dueDate > dates.tomorrow && dueDate <= dates.windowEnd) return "next_days";
  return null;
}

function buildDemoAgenda({ days, mode, sourceTypes, includeSubmitted }) {
  const now = new Date();
  const today = startOfDay(now);
  const dates = {
    today,
    tomorrow: addDays(today, 1),
    windowEnd: addDays(today, days),
    overdueStart: addDays(today, -30),
  };
  const mutedAssignments = readStoredIds(MUTED_ASSIGNMENTS);
  const mutedPrep = readStoredIds(MUTED_PREP);
  const buckets = {
    overdue_missing: [],
    due_today: [],
    due_tomorrow: [],
    next_days: [],
    low_priority: [],
    submitted: [],
  };

  state.demoData.assignments.forEach((item) => {
    if (mutedAssignments.has(String(item.assignmentId))) return;
    const due = dueFromOffset(item.offsetDays, item.time);
    const status = demoStatus(item, due, now);
    const section = demoSection({ ...item, due, priority: item.priority || "normal" }, status, dates, includeSubmitted);
    if (!section) return;
    buckets[section].push({
      type: "assignment",
      assignmentId: item.assignmentId,
      course: item.course,
      title: item.title,
      status,
      due: due.toISOString(),
      dueLabel: dateLabel(due),
      url: item.url,
      points: item.points,
      priority: item.priority || "normal",
      reason: item.reason,
      sortDue: due,
    });
  });

  Object.values(buckets).forEach((items) => items.sort((a, b) => a.sortDue - b.sortDue));

  const prep =
    mode === "focused"
      ? []
      : state.demoData.prep
          .filter((item) => days >= (item.minDays || 0))
          .filter((item) => sourceTypes.has(item.sourceType))
          .filter((item) => !mutedPrep.has(String(item.prepKey)))
          .map((item) => ({
            type: "prep",
            prepKey: item.prepKey,
            course: item.course,
            title: item.title,
            status: item.status,
            dueLabel: item.dueLabel,
            url: item.url,
            sourceType: item.sourceType,
            confidence: item.confidence,
            reason: item.reason,
            evidence: item.evidence,
            completionStatus: item.completionStatus,
            completionReason: item.completionReason,
          }));

  const sections = [
    ["overdue_missing", "Overdue / Missing"],
    ["due_today", "Due Today"],
    ["due_tomorrow", "Due Tomorrow"],
    ["next_days", `Next ${days} Days`],
    ["prep_work", "Possible Prep Work"],
    ["low_priority", "Low Priority / Optional"],
    ["submitted", "Submitted / Done"],
  ].map(([key, label]) => ({
    key,
    label,
    items: key === "prep_work" ? prep : buckets[key],
  }));

  const active = ["overdue_missing", "due_today", "due_tomorrow", "next_days"].reduce(
    (sum, key) => sum + buckets[key].length,
    0,
  );

  return {
    generatedAtLabel: generatedLabel(now),
    days,
    sections,
    summary: {
      active,
      prep: prep.length,
      done: buckets.submitted.length,
      lowPriority: buckets.low_priority.length,
    },
    warnings: [],
    selected: {
      mode,
      sourceTypes: [...sourceTypes].sort(),
    },
  };
}

function wordsOf(text) {
  return new Set(text.toLowerCase().replaceAll("?", " ").split(/\s+/).filter(Boolean));
}

function isStudyQuestion(text) {
  const words = wordsOf(text);
  const offTopic = [...OFF_TOPIC_KEYWORDS].some((word) => words.has(word));
  const study = [...STUDY_KEYWORDS].some((word) => words.has(word));
  if (offTopic && !study) return false;
  if (study) return true;
  const asks = text.toLowerCase().includes("what should") && words.has("do");
  return asks && [...TIME_KEYWORDS].some((word) => words.has(word));
}

function chooseToolCall(message) {
  const text = message.toLowerCase();
  if (!isStudyQuestion(text)) return null;

  const words = wordsOf(text);
  const asksGeneral = text.includes("what should") && words.has("do");
  const hardDeadlines = ["deadline", "deadlines", "due"].some((word) => text.includes(word));
  const prepWords = [
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
  ];
  const includePrep = prepWords.some((word) => text.includes(word)) || (asksGeneral && !hardDeadlines);
  const tool = { tool: "get_study_agenda", include_submitted: true, include_prep: includePrep };

  if (text.includes("week") || text.includes("7")) return { ...tool, days: 7 };
  if (text.includes("tomorrow")) return { ...tool, days: 1 };
  if (text.includes("overdue") || text.includes("missing") || text.includes("late")) {
    return { ...tool, days: 0, include_submitted: false };
  }
  if (text.includes("3") || text.includes("three")) return { ...tool, days: 3 };
  return { ...tool, days: 3 };
}

function unsupportedMessage() {
  return "I only know how to check Canvas study tasks right now. Try asking: What should I do tomorrow? / What is due this week? / Show overdue work.";
}

function requestMode(toolCall, mode) {
  if (!toolCall.include_prep) return "focused";
  if (mode === "focused") return "balanced";
  return mode;
}

async function ensureDemoData() {
  if (state.demoData) return;
  const response = await fetch(appUrl("demo-data.json"));
  if (!response.ok) throw new Error("Demo data failed to load");
  state.demoData = await response.json();
}

async function backendIsLive() {
  try {
    const response = await fetch(appUrl("api/health"), { signal: AbortSignal.timeout(1200) });
    const type = response.headers.get("content-type") || "";
    if (!response.ok || !type.includes("json")) return false;
    const payload = await response.json();
    return Boolean(payload.ok && payload.canvasConfigured);
  } catch {
    return false;
  }
}

async function loadAgenda() {
  updateSelectedButtons();
  setLoading(state.demo ? "Loading the sample agenda..." : "Checking Canvas...");

  try {
    if (state.demo) {
      await ensureDemoData();
      renderAgenda(
        buildDemoAgenda({
          days: Number(state.days),
          mode: state.mode,
          sourceTypes: selectedSourceSet(),
          includeSubmitted: true,
        }),
      );
      return;
    }

    const params = new URLSearchParams({
      days: state.days,
      mode: state.mode,
      sourceTypes: apiSourceTypes(),
    });
    renderAgenda(await requestJson(appUrl(`api/agenda?${params.toString()}`)));
  } catch (error) {
    setError(error.message);
  }
}

async function askAgent(message) {
  updateSelectedButtons();
  setLoading(state.demo ? "Reading the sample agenda..." : "Asking the agent...");

  try {
    if (state.demo) {
      await ensureDemoData();
      const toolCall = chooseToolCall(message);
      if (!toolCall) {
        setReady();
        agentMessageEl.textContent = unsupportedMessage();
        agendaEl.replaceChildren();
        updatedAtEl.textContent = "No Canvas call";
        return;
      }
      state.days = String(toolCall.days);
      state.timeLabel = timeLabelFromDays(state.days);
      updateSelectedButtons();
      renderAgenda(
        buildDemoAgenda({
          days: toolCall.days,
          mode: requestMode(toolCall, state.mode),
          sourceTypes: selectedSourceSet(),
          includeSubmitted: toolCall.include_submitted,
        }),
      );
      return;
    }

    const payload = await requestJson(appUrl("api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        mode: state.mode,
        sourceTypes: apiSourceTypes(),
      }),
    });

    if (payload.toolCall) {
      state.days = String(payload.toolCall.days);
      state.timeLabel = timeLabelFromDays(state.days);
      updateSelectedButtons();
    }

    if (payload.agenda) {
      renderAgenda(payload.agenda);
    } else {
      setReady();
      agentMessageEl.textContent = payload.message;
      agendaEl.replaceChildren();
      updatedAtEl.textContent = "No Canvas call";
    }
  } catch (error) {
    setError(error.message);
  }
}

function timeLabelFromDays(days) {
  if (String(days) === "0") return "Overdue";
  if (String(days) === "1") return "Tomorrow";
  if (String(days) === "3") return "Next 3 Days";
  if (String(days) === "7") return "This Week";
  return `Next ${days} Days`;
}

async function muteItem(payload, card) {
  card.classList.add("is-muted-pending");

  try {
    if (state.demo) {
      if (payload.prepKey) storeId(MUTED_PREP, payload.prepKey);
      if (payload.assignmentId) storeId(MUTED_ASSIGNMENTS, payload.assignmentId);
      card.remove();
      agentMessageEl.textContent = "Muted that demo item in this browser.";
      return;
    }

    await requestJson(appUrl("api/mute"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    card.remove();
    agentMessageEl.textContent = "Muted that item. It will stay hidden locally.";
  } catch (error) {
    card.classList.remove("is-muted-pending");
    agentMessageEl.textContent = `Could not mute item: ${error.message}`;
  }
}

timeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    state.days = button.dataset.days;
    state.timeLabel = button.dataset.label;
    loadAgenda();
  });
});

modeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    state.mode = button.dataset.mode;
    loadAgenda();
  });
});

sourceCheckboxes.forEach((checkbox) => {
  checkbox.addEventListener("change", () => {
    if (state.mode === "focused") return;
    loadAgenda();
  });
});

suggestedPromptButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const prompt = button.dataset.prompt;
    messageInput.value = prompt;
    askAgent(prompt);
  });
});

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) return;
  askAgent(message);
});

refreshButton.addEventListener("click", () => {
  if (!state.isLoading) loadAgenda();
});

async function start() {
  state.demo = !(await backendIsLive());
  updateChrome();
  loadAgenda();
}

start();
