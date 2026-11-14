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

const state = {
  days: "1",
  timeLabel: "Tomorrow",
  mode: "balanced",
  isLoading: false,
};

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

function setLoading(message) {
  state.isLoading = true;
  refreshButton.disabled = true;
  agentMessageEl.textContent = message;
  agendaEl.replaceChildren();
  activeCountEl.textContent = "-";
  prepCountEl.textContent = "-";
  doneCountEl.textContent = "-";
  updatedAtEl.textContent = "Checking Canvas";
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
  empty.textContent = "Check that the local server is running and your Canvas .env settings are correct.";
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
  agentMessageEl.textContent = `Showing ${state.timeLabel} in ${modeLabel(state.mode)} mode. Sources: assignments${sourceText ? `, ${sourceText}` : ""}.`;

  const visibleSections = agenda.sections.filter((section) => section.items.length > 0);

  if (visibleSections.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No Canvas tasks found for this view.";
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

async function loadAgenda() {
  updateSelectedButtons();
  setLoading("Checking Canvas...");

  const params = new URLSearchParams({
    days: state.days,
    mode: state.mode,
    sourceTypes: apiSourceTypes(),
  });

  try {
    const agenda = await requestJson(`/api/agenda?${params.toString()}`);
    renderAgenda(agenda);
  } catch (error) {
    setError(error.message);
  }
}

async function askAgent(message) {
  updateSelectedButtons();
  setLoading("Asking the agent...");

  try {
    const payload = await requestJson("/api/chat", {
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
    await requestJson("/api/mute", {
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
    if (state.mode === "focused") {
      return;
    }
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
  if (!state.isLoading) {
    loadAgenda();
  }
});

loadAgenda();
