/*
 * Copyright (c) 2026 Vishalan Karunanithi.
 * All Rights Reserved.
 * This repository is published for hackathon review only. No permission is granted to copy,
 * modify, distribute, sublicense, or commercially use this software without written permission.
 */

const state = {
  roles: [],
  selectedRole: null,
  latest: null,
  profiles: [],
  graph: null,
  timeline: null,
  notes: [],
  draftSaveTimer: null
};

const MIN_ANSWER_CHARS = 80;
const MAX_ANSWER_CHARS = 2200;
const MIN_NOTE_CHARS = 25;
const MAX_NOTE_CHARS = 12000;
const DRAFT_STORAGE_KEY = "legacyosLiteDraftsV1";

const groupColors = {
  Role: "#0e7c66",
  System: "#2878c7",
  Risk: "#c84f5d",
  Process: "#d58a17",
  "Knowledge Source": "#6d6bb3",
  "Person or Team": "#2f855a"
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed with ${response.status}`);
  }
  return response.json();
}

async function init() {
  wireNavigation();
  wireActions();

  const roleResponse = await api("/api/roles");
  state.roles = roleResponse.roles;
  state.selectedRole = state.roles[0]?.name || null;
  renderRoles();
  renderQuestions();
  clearInterviewError();
  updateNoteCharCount();
  wireNoteInputTracking();

  try {
    await refreshProfiles();
    if (state.profiles.length) {
      state.latest = await api(`/api/interviews/${encodeURIComponent(state.profiles[0].id)}`);
      await refreshGeneratedViews({ refreshProfileDirectory: false });
    } else {
      renderEmptyDashboard();
      renderTimeline();
      renderGraph();
    }
  } catch {
    renderEmptyDashboard();
    renderTimeline();
    renderGraph();
  }

  await refreshNotes();
}

function wireNavigation() {
  document.querySelectorAll(".navButton").forEach((button) => {
    button.addEventListener("click", () => activateView(button.dataset.view));
  });
}

function wireActions() {
  document.getElementById("runInterviewButton").addEventListener("click", submitInterview);
  document.getElementById("clearDraftButton").addEventListener("click", clearCurrentDraft);
  document.getElementById("searchForm").addEventListener("submit", submitSearch);
  document.getElementById("noteForm").addEventListener("submit", submitNote);
  document.getElementById("reloadNotesButton").addEventListener("click", refreshNotes);
  document.getElementById("graphExportButton").addEventListener("click", exportGraphToCypher);
}

function wireNoteInputTracking() {
  const noteInput = document.getElementById("noteContentInput");
  noteInput?.addEventListener("input", updateNoteCharCount);
  const noteFileInput = document.getElementById("noteFileInput");
  noteFileInput?.addEventListener("change", handleNoteFileUpload);
}

function getCanonicalRole(roleInput) {
  if (!roleInput) {
    return null;
  }
  const normalized = roleInput.trim().toLowerCase();
  const match = state.roles.find((role) => role.name.toLowerCase() === normalized);
  return match ? match.name : null;
}

function handleNoteFileUpload(event) {
  const fileInput = event.currentTarget;
  const file = fileInput?.files?.[0];
  if (!file) {
    return;
  }
  if (!(file.type.startsWith("text/") || /\.(txt|md|log|csv|json)$/i.test(file.name))) {
    setNoteError("Only plain text note files can be imported (txt/md/log/csv/json).");
    fileInput.value = "";
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    const noteText = String(reader.result || "").trim();
    const noteContentInput = document.getElementById("noteContentInput");
    const noteTitleInput = document.getElementById("noteTitleInput");
    const noteSourceInput = document.getElementById("noteSourceInput");
    if (!noteText) {
      setNoteError("Uploaded file has no readable text content.");
      return;
    }
    if (noteText.length > MAX_NOTE_CHARS) {
      setNoteError(`Uploaded file exceeds ${MAX_NOTE_CHARS} characters.`);
      return;
    }
    noteContentInput.value = noteText;
    updateNoteCharCount();
    if (!noteTitleInput.value.trim()) {
      noteTitleInput.value = file.name.replace(/\.[^/.]+$/, "").slice(0, 180);
    }
    if (!noteSourceInput.value.trim()) {
      noteSourceInput.value = "Uploaded meeting notes";
    }
    setNoteError(`Imported ${file.name}.`);
  };
  reader.onerror = () => {
    setNoteError("Could not read the uploaded notes file.");
    fileInput.value = "";
  };
  reader.readAsText(file);
}

function activateView(viewName) {
  document.querySelectorAll(".navButton").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `${viewName}View`);
  });
}

function renderRoles() {
  const root = document.getElementById("roleCards");
  root.innerHTML = "";
  state.roles.forEach((role) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `roleCard${role.name === state.selectedRole ? " active" : ""}`;
    card.innerHTML = `
      <strong>${escapeHtml(role.name)}</strong>
      <span>${role.questions.length} focused interview prompts</span>
    `;
    card.addEventListener("click", () => {
      state.selectedRole = role.name;
      clearInterviewError();
      renderRoles();
      renderQuestions();
    });
    root.appendChild(card);
  });
}

function renderQuestions() {
  const root = document.getElementById("interviewForm");
  root.innerHTML = "";
  const role = state.roles.find((item) => item.name === state.selectedRole);
  if (!role) {
    return;
  }
  const draft = getDraftForRole(role.name);
  role.questions.forEach((question, index) => {
    const card = document.createElement("article");
    card.className = "questionCard";
    card.innerHTML = `
      <label for="answer-${index}">
        <span>${escapeHtml(question)}</span>
        <span class="questionNumber">${index + 1}/${role.questions.length}</span>
      </label>
      <textarea
        id="answer-${index}"
        data-question="${escapeHtml(question)}"
        maxlength="${MAX_ANSWER_CHARS}"
        data-min="${MIN_ANSWER_CHARS}"
      >${escapeHtml(draft[question] || "")}</textarea>
      <p class="inputMeta">Minimum <span class="charCount">0</span> characters (need <span class="requiredChars">${MIN_ANSWER_CHARS}</span>+)</p>
    `;
    const textarea = card.querySelector("textarea");
    textarea.addEventListener("input", () => {
      updateQuestionMeta(textarea);
      validateQuestionCard(textarea.closest(".questionCard"), textarea.value.trim());
      updateInterviewProgress();
      queueDraftSave();
    });
    textarea.addEventListener("blur", () => {
      validateQuestionCard(textarea.closest(".questionCard"), textarea.value.trim());
    });
    updateQuestionMeta(textarea);
    validateQuestionCard(card, textarea.value.trim());
    root.appendChild(card);
  });
  updateInterviewProgress();
}

async function submitInterview() {
  if (!state.selectedRole) {
    return;
  }
  const button = document.getElementById("runInterviewButton");
  if (button && button.disabled) {
    setInterviewError("Complete all interview prompts before generating.");
    return;
  }
  const fields = Array.from(document.querySelectorAll("#interviewForm textarea"));
  const errors = [];
  const answers = {};

  fields.forEach((textarea) => {
    const question = textarea.dataset.question;
    const rawValue = textarea.value.trim();
    const questionCard = textarea.closest(".questionCard");
    const short = rawValue.length < MIN_ANSWER_CHARS;
    const empty = !rawValue;
    validateQuestionCard(questionCard, rawValue);

    if (empty) {
      errors.push(`"${question}" has no answer`);
    } else if (short) {
      errors.push(`"${question}" needs ${MIN_ANSWER_CHARS}+ chars`);
    } else {
      answers[question] = rawValue;
    }
  });

  if (errors.length) {
    setInterviewError(`Please complete all prompts before generating: ${errors.join("; ")}.`);
    return;
  }

  button.disabled = true;
  button.textContent = "Generating...";
  clearInterviewError();

  try {
    state.latest = await api("/api/interviews", {
      method: "POST",
      body: JSON.stringify({ role: state.selectedRole, answers })
    });
    clearCurrentDraft();
    await refreshProfiles();
    await refreshGeneratedViews({ refreshProfileDirectory: false });
    activateView("dashboard");
  } catch (error) {
    setInterviewError(error.message || "Interview generation failed.");
  } finally {
    button.disabled = false;
    button.textContent = "Generate Profile";
  }
}

async function submitNote(event) {
  event.preventDefault();
  const button = document.getElementById("submitNoteButton");
  const title = document.getElementById("noteTitleInput").value.trim();
  const source = document.getElementById("noteSourceInput").value.trim();
  const rawRole = document.getElementById("noteRoleInput").value.trim();
  const content = document.getElementById("noteContentInput").value.trim();
  const attachLatest = document.getElementById("noteAttachLatest").checked;
  const validations = [];
  const canonicalRole = getCanonicalRole(rawRole);

  if (title.length < 3) {
    validations.push("note title must be at least 3 characters.");
  }
  if (source.length < 2) {
    validations.push("source must be at least 2 characters.");
  }
  if (content.length < MIN_NOTE_CHARS) {
    validations.push(`note content must be at least ${MIN_NOTE_CHARS} characters.`);
  }
  if (content.length > MAX_NOTE_CHARS) {
    validations.push(`note content must be ${MAX_NOTE_CHARS} characters or fewer.`);
  }
  if (rawRole && !canonicalRole) {
    validations.push("role must match one of the available interview roles.");
  }
  if (validations.length) {
    setNoteError(`Cannot add note: ${validations.join(" ")}`);
    return;
  }

  if (button) {
    button.disabled = true;
    button.textContent = "Saving...";
  }
  clearNoteError();

  const payload = {
    title,
    source,
    content,
    attach_latest: attachLatest
  };
  const effectiveRole = canonicalRole || state.latest?.role || null;
  if (effectiveRole) {
    payload.role = effectiveRole;
  }
  if (attachLatest && state.latest?.id) {
    payload.interview_id = state.latest.id;
  }

  try {
    await api("/api/repository/notes", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    document.getElementById("noteTitleInput").value = "";
    document.getElementById("noteSourceInput").value = "";
    document.getElementById("noteRoleInput").value = "";
    document.getElementById("noteContentInput").value = "";
    document.getElementById("noteAttachLatest").checked = false;
    const noteFileInput = document.getElementById("noteFileInput");
    if (noteFileInput) {
      noteFileInput.value = "";
    }
    updateNoteCharCount();
    setNoteError("Note added to repository.");
    await refreshNotes();
  } catch (error) {
    setNoteError(error.message || "Could not save note.");
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "Add repository note";
    }
  }
}

async function refreshProfiles() {
  const payload = await api("/api/interviews?limit=100");
  state.profiles = Array.isArray(payload.interviews) ? payload.interviews : [];
  renderProfileDirectory();
}

async function selectProfile(profileId, roleName = "") {
  if (!profileId) {
    return;
  }
  try {
    state.latest = await api(`/api/interviews/${encodeURIComponent(profileId)}`);
    await refreshGeneratedViews({ refreshProfileDirectory: false });
    activateView("dashboard");
  } catch (error) {
    await refreshProfiles();
    const fallbackPath = roleName
      ? `/api/interviews/latest?role=${encodeURIComponent(roleName)}`
      : "/api/interviews/latest";
    state.latest = await api(fallbackPath);
    await refreshGeneratedViews({ refreshProfileDirectory: false });
    activateView("dashboard");
  }
}

async function refreshGeneratedViews(options = {}) {
  const shouldRefreshProfiles = options.refreshProfileDirectory !== false;
  if (!state.latest) {
    renderEmptyDashboard();
    await refreshNotes();
    return;
  }
  if (shouldRefreshProfiles) {
    await refreshProfiles();
  }
  state.graph = await api(profileScopedPath("/api/graph"));
  state.timeline = await api(profileScopedPath("/api/timeline"));
  renderDashboard();
  renderTimeline();
  renderGraph();
  await refreshNotes();
}

async function refreshNotes() {
  try {
    const params = new URLSearchParams();
    const activeInterviewId = state.latest?.id;
    if (activeInterviewId) {
      params.set("interview_id", activeInterviewId);
    }
    params.set("limit", "20");
    state.notes = await api(`/api/repository/notes?${params.toString()}`).then((payload) => payload.notes);
    renderNotes();
  } catch {
    state.notes = [];
    renderNotesEmpty();
  }
}

async function removeNote(noteId) {
  if (!noteId) {
    return;
  }
  const confirmed = window.confirm("Remove this repository note? This cannot be undone in the demo store.");
  if (!confirmed) {
    return false;
  }
  try {
    await api(`/api/repository/notes/${encodeURIComponent(noteId)}`, { method: "DELETE" });
    state.notes = state.notes.filter((note) => note.id !== noteId);
    renderNotes();
    setNoteError("Repository note removed.");
    return true;
  } catch (error) {
    setNoteError(error.message || "Could not remove note.");
    return false;
  }
}

function renderDashboard() {
  const latest = state.latest;
  const profile = latest.profile || {};
  const risk = latest.risk_score || 0;
  const riskLevel = (latest.risk_level || "Neutral").toLowerCase();

  renderProfileDirectory();
  document.getElementById("metricRole").textContent = latest.role;
  document.getElementById("metricRisk").textContent = `${risk}/100`;
  document.getElementById("metricNodes").textContent = String(latest.entities.length);
  document.getElementById("metricCoverage").textContent = profile.coverage || "Starter";
  document.getElementById("summaryText").textContent = latest.summary;

  const riskPill = document.getElementById("riskPill");
  riskPill.className = `riskPill ${riskLevel}`;
  riskPill.textContent = `${latest.risk_level} risk`;

  const fill = document.getElementById("riskFill");
  fill.style.width = `${risk}%`;
  fill.style.background = risk < 35 ? "#0e7c66" : risk < 70 ? "#d58a17" : "#c84f5d";
  const riskValue = document.getElementById("riskValue");
  if (riskValue) {
    riskValue.textContent = `${risk}/100`;
  }

  renderChips("topEntities", profile.top_entities || []);
  renderRiskDrivers(profile.risk_breakdown || []);
  renderActions(profile.recommended_actions || []);
}

function renderProfileDirectory() {
  const root = document.getElementById("profileDirectoryList");
  const countNode = document.getElementById("profileDirectoryCount");
  if (!root || !countNode) {
    return;
  }
  const count = state.profiles.length;
  countNode.textContent = `${count} ${count === 1 ? "profile" : "profiles"}`;
  root.innerHTML = "";
  if (!count) {
    root.appendChild(emptyState("No profiles captured yet.", "Generate role interviews to build the profile directory."));
    return;
  }
  state.profiles.forEach((profile) => {
    const card = document.createElement("button");
    const isActive = state.latest?.id === profile.id;
    const riskClass = (profile.risk_level || "Neutral").toLowerCase();
    card.type = "button";
    card.className = `profileSummaryCard${isActive ? " active" : ""}`;
    card.innerHTML = `
      <span class="profileRole">${escapeHtml(profile.role)}</span>
      <strong>${escapeHtml(profile.risk_score)}/100</strong>
      <span class="profileMeta">${escapeHtml(profile.coverage || "Starter")} coverage - ${escapeHtml(profile.entity_count || 0)} nodes</span>
      <p>${escapeHtml(sentencePreview(profile.summary || "No summary captured yet.", 22))}</p>
      <span class="riskPill ${escapeHtml(riskClass)}">${escapeHtml(profile.risk_level || "Neutral")} risk</span>
    `;
    card.addEventListener("click", () => selectProfile(profile.id, profile.role));
    root.appendChild(card);
  });
}

function clearInterviewError() {
  const root = document.getElementById("interviewValidation");
  if (!root) {
    return;
  }
  root.textContent = "";
  root.hidden = true;
  setProgressStatus("Ready");
}

function setNoteError(message) {
  const root = document.getElementById("notesValidation");
  if (!root) {
    return;
  }
  root.textContent = message;
  root.hidden = false;
}

function clearNoteError() {
  const root = document.getElementById("notesValidation");
  if (!root) {
    return;
  }
  root.hidden = true;
}

function setInterviewError(message) {
  const root = document.getElementById("interviewValidation");
  if (!root) {
    return;
  }
  root.textContent = message;
  root.hidden = false;
  setProgressStatus("Needs attention", "warningText");
}

function setProgressStatus(text, variant = "neutralText") {
  const progressStatus = document.getElementById("progressStatus");
  if (!progressStatus) {
    return;
  }
  progressStatus.textContent = text;
  progressStatus.className = variant;
}

function setProgressFill(percent) {
  const progressFill = document.getElementById("progressFill");
  if (progressFill) {
    progressFill.style.width = `${percent}%`;
  }
}

function updateQuestionMeta(textarea) {
  const questionCard = textarea.closest(".questionCard");
  const count = textarea.value.trim().length;
  const charNode = questionCard?.querySelector(".charCount");
  if (charNode) {
    charNode.textContent = String(count);
  }
}

function validateQuestionCard(questionCard, value) {
  if (!questionCard) {
    return;
  }
  const min = Number(questionCard.querySelector("textarea")?.dataset.min || 0);
  const hasText = !!value.trim();
  const meetsMinimum = value.length >= min;
  questionCard.classList.toggle("hasInput", hasText);
  questionCard.classList.toggle("ready", meetsMinimum);
  questionCard.classList.toggle("needsInput", !meetsMinimum);
}

function updateInterviewProgress() {
  const fields = Array.from(document.querySelectorAll("#interviewForm textarea"));
  const runButton = document.getElementById("runInterviewButton");
  if (!fields.length) {
    setProgressFill(0);
    if (runButton) {
      runButton.disabled = true;
    }
    const progressText = document.getElementById("progressText");
    if (progressText) {
      progressText.textContent = "No questions loaded.";
    }
    return;
  }

  let completed = 0;
  fields.forEach((textarea) => {
    if (textarea.value.trim().length >= MIN_ANSWER_CHARS) {
      completed += 1;
    }
  });

  const total = fields.length;
  const percent = Math.round((completed / total) * 100);
  setProgressFill(percent);

  const progressText = document.getElementById("progressText");
  const progressStatus = document.getElementById("progressStatus");
  if (progressText && progressStatus) {
    progressText.textContent = `${completed} / ${total} questions meet quality threshold`;
    if (completed === total) {
      progressStatus.textContent = "Ready";
      progressStatus.className = "successText";
      if (runButton) {
        runButton.disabled = false;
      }
    } else {
      progressStatus.textContent = "In progress";
      progressStatus.className = "warningText";
      if (runButton) {
        runButton.disabled = true;
      }
    }
  }
}

function getDraftStore() {
  if (typeof localStorage === "undefined") {
    return {};
  }
  try {
    return JSON.parse(localStorage.getItem(DRAFT_STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function getDraftForRole(role) {
  const store = getDraftStore();
  return store[role] || {};
}

function persistDraftForRole(role, values) {
  if (typeof localStorage === "undefined") {
    return;
  }
  const store = getDraftStore();
  store[role] = values;
  localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(store));
}

function clearCurrentDraft() {
  if (!state.selectedRole) {
    return;
  }
  if (typeof localStorage === "undefined") {
    return;
  }
  const store = getDraftStore();
  delete store[state.selectedRole];
  localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(store));
  renderQuestions();
  setProgressStatus("Draft cleared", "neutralText");
}

function queueDraftSave() {
  if (!state.selectedRole) {
    return;
  }
  if (state.draftSaveTimer) {
    clearTimeout(state.draftSaveTimer);
  }
  state.draftSaveTimer = setTimeout(() => {
    const inputs = document.querySelectorAll("#interviewForm textarea");
    const values = {};
    inputs.forEach((textarea) => {
      const value = textarea.value.trim();
      if (value) {
        values[textarea.dataset.question] = value;
      }
    });
    persistDraftForRole(state.selectedRole, values);
    setProgressStatus("Draft saved", "neutralText");
  }, 400);
}

function renderNotesEmpty() {
  const root = document.getElementById("noteList");
  root.innerHTML = "";
  root.appendChild(emptyState("No repository notes yet.", "Add meeting notes, handover notes, or audit notes in the form above."));
  const headline = document.getElementById("notesHeadline");
  if (headline) {
    headline.textContent = "No repository notes yet";
  }
}

function renderNotes() {
  const root = document.getElementById("noteList");
  root.innerHTML = "";
  const count = state.notes.length;
  const headline = document.getElementById("notesHeadline");
  if (headline) {
    if (state.latest?.id) {
      headline.textContent = `Latest interview notes (${count})`;
    } else {
      headline.textContent = `Recent repository notes (${count})`;
    }
  }

  if (!count) {
    renderNotesEmpty();
    return;
  }

  state.notes.forEach((note) => {
    const noteCard = document.createElement("article");
    noteCard.className = "noteCard";
    const roleLabel = note.role ? `<span class="noteMetaItem">Role: ${escapeHtml(note.role)}</span>` : "";
    noteCard.innerHTML = `
      <div class="noteHeader">
        <div>
          <strong>${escapeHtml(note.title)}</strong>
          <span class="noteSource">${escapeHtml(note.source)}</span>
        </div>
        <button type="button" class="dangerTextButton" data-note-remove="${escapeHtml(note.id)}">Remove</button>
      </div>
      <p>${escapeHtml(note.content)}</p>
      <div class="noteMeta">
        <span>${escapeHtml(note.created_at || "")}</span>
        ${roleLabel}
      </div>
    `;
    const removeButton = noteCard.querySelector("[data-note-remove]");
    if (removeButton) {
      removeButton.addEventListener("click", () => removeNote(note.id));
    }
    root.appendChild(noteCard);
  });
}

function updateNoteCharCount() {
  const node = document.getElementById("noteContentInput");
  const countNode = document.getElementById("noteCharCount");
  if (!node || !countNode) {
    return;
  }
  countNode.textContent = String(node.value.length);
  const limitNode = document.getElementById("noteCharLimit");
  if (limitNode) {
    limitNode.textContent = String(MAX_NOTE_CHARS);
  }
  if (node.value.length > MAX_NOTE_CHARS) {
    countNode.style.color = "#c84f5d";
  } else {
    countNode.style.color = "var(--muted)";
  }
}

function renderEmptyDashboard() {
  renderProfileDirectory();
  document.getElementById("metricRole").textContent = "Not captured";
  document.getElementById("metricRisk").textContent = "--";
  document.getElementById("metricNodes").textContent = "0";
  document.getElementById("metricCoverage").textContent = "Starter";
  document.getElementById("summaryText").textContent = "Complete an interview to generate a knowledge profile.";
  document.getElementById("riskPill").className = "riskPill neutral";
  document.getElementById("riskPill").textContent = "No risk yet";
  document.getElementById("riskFill").style.width = "0%";
  const riskValue = document.getElementById("riskValue");
  if (riskValue) {
    riskValue.textContent = "--/100";
  }
  renderRiskDrivers([]);
  renderChips("topEntities", []);
  renderActions([]);
}

function renderChips(elementId, values) {
  const root = document.getElementById(elementId);
  root.innerHTML = "";
  if (!values.length) {
    root.appendChild(emptyState("No nodes yet."));
    return;
  }
  values.forEach((value) => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = value;
    root.appendChild(chip);
  });
}

function renderActions(values) {
  const root = document.getElementById("actionList");
  root.innerHTML = "";
  if (!values.length) {
    root.appendChild(emptyState("No actions yet."));
    return;
  }
  values.forEach((value) => {
    const item = document.createElement("span");
    item.className = "actionItem";
    item.textContent = value;
    root.appendChild(item);
  });
}

function renderRiskDrivers(factors) {
  const root = document.getElementById("riskDrivers");
  root.innerHTML = "";
  if (!Array.isArray(factors) || !factors.length) {
    root.appendChild(emptyState("No specific risk escalators yet."));
    return;
  }
  factors.slice(0, 6).forEach((factor) => {
    const item = document.createElement("span");
    item.className = "riskDriver";
    const impact = Number(factor.impact || 0);
    const note = factor.factor || "Risk factor";
    const detail = factor.note || "";
    item.textContent = `${note}${impact > 0 ? ` (+${impact})` : ""} ${detail ? `— ${detail}` : ""}`.trim();
    root.appendChild(item);
  });
}

function renderTimeline() {
  const root = document.getElementById("timelineList");
  root.innerHTML = "";
  const events = state.timeline?.events || [];
  if (!events.length) {
    root.appendChild(emptyState("No timeline yet."));
    return;
  }
  events.forEach((event) => {
    const row = document.createElement("article");
    row.className = "timelineEvent";
    row.innerHTML = `
      <time>${escapeHtml(event.date_label)}</time>
      <div>
        <h3>${escapeHtml(event.title)}</h3>
        <p>${escapeHtml(event.description)}</p>
      </div>
    `;
    root.appendChild(row);
  });
}

function renderGraph() {
  const svg = document.getElementById("graphSvg");
  svg.innerHTML = "";
  const nodes = state.graph?.nodes || [];
  const links = state.graph?.links || [];
  if (!nodes.length) {
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", "50%");
    text.setAttribute("y", "50%");
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("fill", "#617064");
    text.textContent = "No graph yet";
    svg.appendChild(text);
    return;
  }

  const width = Math.max(svg.clientWidth || 0, 1120);
  const height = Math.max(svg.clientHeight || 0, 680);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  const groups = ["Role", "System", "Person or Team", "Process", "Knowledge Source", "Risk"];
  const groupedNodes = Object.fromEntries(groups.map((group) => [group, []]));
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  nodes.forEach((node) => {
    const bucket = groupedNodes[node.group] ? node.group : "Knowledge Source";
    groupedNodes[bucket].push(node);
  });

  const laneConfig = {
    System: { x: width * 0.18, yMin: 105, yMax: height - 105 },
    "Person or Team": { x: width * 0.36, yMin: 125, yMax: height - 125 },
    Role: { x: width * 0.50, yMin: height / 2, yMax: height / 2 },
    Process: { x: width * 0.64, yMin: 125, yMax: height - 125 },
    "Knowledge Source": { x: width * 0.79, yMin: 105, yMax: height - 105 },
    Risk: { x: width * 0.91, yMin: 150, yMax: height - 150 }
  };

  const placed = [];
  groups.forEach((group) => {
    const members = groupedNodes[group];
    if (!members.length) {
      return;
    }
    const lane = laneConfig[group] || laneConfig["Knowledge Source"];
    const step = members.length > 1 ? (lane.yMax - lane.yMin) / (members.length - 1) : 0;
    members.forEach((node, index) => {
      placed.push({
        ...node,
        x: lane.x,
        y: clamp(lane.yMin + step * index, 70, height - 70),
      });
    });
  });

  const byId = new Map();
  placed.forEach((node) => {
    byId.set(node.id, node);
  });

  groups.forEach((group) => {
    const lane = laneConfig[group];
    if (!lane || !groupedNodes[group]?.length) {
      return;
    }
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", lane.x);
    label.setAttribute("y", 42);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("font-size", "13");
    label.setAttribute("font-weight", "800");
    label.setAttribute("fill", groupColors[group] || "#617064");
    label.textContent = group;
    svg.appendChild(label);
  });

  links.forEach((link) => {
    const source = byId.get(link.source);
    const target = byId.get(link.target);
    if (!source || !target) {
      return;
    }
    const linkConfidence = clamp(Number(link.confidence ?? link.strength) || 0.55, 0.2, 1);
    const strokeWidth = 1 + linkConfidence * 2.7;
    const strokeColor = linkConfidence >= 0.85 ? "#8f1d3f" : linkConfidence >= 0.7 ? "#0e7c66" : "#7f8f87";
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", source.x);
    line.setAttribute("y1", source.y);
    line.setAttribute("x2", target.x);
    line.setAttribute("y2", target.y);
    line.setAttribute("stroke", strokeColor);
    line.setAttribute("stroke-width", String(strokeWidth));
    line.setAttribute("opacity", "0.48");
    line.setAttribute("stroke-linecap", "round");
    line.setAttribute("title", `${link.evidence || "No evidence summary"}`);
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    const sourceText = link.source_name || "";
    const targetText = link.target_name || "";
    const route = [sourceText, targetText].filter(Boolean).join(" -> ");
    const relationEvidence = link.evidence || "No evidence captured";
    title.textContent = `${route}: ${link.label_readable || link.label || "Related"} - ${relationEvidence}`;
    line.appendChild(title);

    svg.appendChild(line);
  });

  placed.forEach((node) => {
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", node.x);
    circle.setAttribute("cy", node.y);
    circle.setAttribute("r", node.group === "Role" ? "34" : "22");
    circle.setAttribute("fill", groupColors[node.group] || "#617064");
    circle.setAttribute("stroke", "#ffffff");
    circle.setAttribute("stroke-width", "3");

    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", node.x);
    text.setAttribute("y", node.group === "Role" ? node.y + 54 : node.y + 38);
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("fill", "#17211b");
    text.setAttribute("font-size", node.group === "Role" ? "13" : "11");
    text.setAttribute("font-weight", node.group === "Role" ? "800" : "700");
    text.textContent = trimLabel(node.label);
    const nodeTitle = `${node.label} (${node.group || "Knowledge"}), confidence ${Math.round((Number(node.confidence) || 0.7) * 100)}%`;
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = nodeTitle;
    text.appendChild(title);

    group.appendChild(circle);
    group.appendChild(text);
    svg.appendChild(group);
  });
}

function exportGraphToCypher() {
  const button = document.getElementById("graphExportButton");
  if (button) {
    button.disabled = true;
    button.textContent = "Preparing...";
  }
  api(profileScopedPath("/api/graph/export/neo4j"))
    .then((payload) => {
      const lines = payload.cypher || "";
      const fileName = `legacyos-graph-${(payload.interview_id || "latest").slice(0, 12)}.cypher`;
      const blob = new Blob([lines], { type: "text/plain;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = fileName;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      URL.revokeObjectURL(url);
      setGraphExportStatus(`Neo4j export downloaded: ${fileName}`);
    })
    .catch((error) => {
      setGraphExportStatus(error.message || "Graph export failed.");
    })
    .finally(() => {
      if (button) {
        button.disabled = false;
        button.textContent = "Export to Neo4j";
      }
    });
}

function setGraphExportStatus(message) {
  const status = document.getElementById("graphExportStatus");
  if (!status) {
    return;
  }
  status.textContent = message;
  status.hidden = false;
  status.className = "graphExportStatus";
  setTimeout(() => {
    status.hidden = true;
  }, 2800);
}

async function submitSearch(event) {
  event.preventDefault();
  const input = document.getElementById("searchInput");
  const searchButton = document.querySelector("#searchForm button[type='submit']");
  const question = input.value.trim();
  if (!question) {
    setSearchState("Type a question before searching.");
    return;
  }

  searchButton.disabled = true;
  searchButton.textContent = "Searching...";
  setSearchState("Querying interview profile and repository notes...");
  try {
    const result = await requestSearchAnswer(question);
    input.value = "";
    setSearchState("Search complete.");
    renderSearchResult(result);
  } catch (error) {
    try {
      const recovered = await recoverSearchAfterProfileError(error, question);
      if (recovered) {
        input.value = "";
        setSearchState("Search recovered after refreshing profile context.");
        renderSearchResult(recovered);
      } else {
        setSearchState(`<strong>Search failed:</strong> ${escapeHtml(error.message || "Unable to answer right now.")}`);
      }
    } catch (recoveryError) {
      setSearchState(`<strong>Search failed:</strong> ${escapeHtml(recoveryError.message || "Unable to recover profile context.")}`);
    }
  } finally {
    searchButton.disabled = false;
    searchButton.textContent = "Ask";
  }
}

async function requestSearchAnswer(question) {
  const payload = {
    question,
    include_repository_notes: true
  };
  if (state.latest?.id) {
    payload.interview_id = state.latest.id;
  }
  if (state.latest?.role) {
    payload.role = state.latest.role;
  }
  return api("/api/search", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

async function recoverSearchAfterProfileError(error, question) {
  const message = String(error?.message || "");
  if (!message.includes("Interview not found") && !message.includes("No interview found")) {
    return null;
  }
  const previousRole = state.latest?.role || "";
  await refreshProfiles();
  if (!state.profiles.length) {
    throw new Error("The Vercel demo data appears to have reset. Please regenerate a profile or run locally for persistent storage.");
  }
  const replacement = state.profiles.find((profile) => profile.role === previousRole) || state.profiles[0];
  state.latest = await api(`/api/interviews/${encodeURIComponent(replacement.id)}`);
  await refreshGeneratedViews({ refreshProfileDirectory: false });
  return requestSearchAnswer(question);
}

function profileScopedPath(basePath) {
  const params = new URLSearchParams();
  if (state.latest?.id) {
    params.set("interview_id", state.latest.id);
  }
  if (state.latest?.role) {
    params.set("role", state.latest.role);
  }
  const query = params.toString();
  return query ? `${basePath}?${query}` : basePath;
}

function setSearchState(message) {
  const stateElement = document.getElementById("searchState");
  if (!stateElement) {
    return;
  }
  stateElement.innerHTML = message;
  stateElement.hidden = false;
}

function renderSearchResult(result) {
  const root = document.getElementById("searchResults");
  const card = document.createElement("article");
  card.className = "answerCard";
  const sources = Array.isArray(result.source_summary) ? result.source_summary : [];
  const when = result.created_at ? `<p class="searchModel">Asked: ${escapeHtml(result.created_at)}</p>` : "";
  const sourceHtml = sources.length
    ? `<div class="searchSources"><strong>Evidence you can inspect:</strong>${sources
        .map((source) => renderSourceDetail(source))
        .join("")}</div>`
    : "";
  const modelLabel = result.model ? `<p class="searchModel">Responder: ${escapeHtml(result.model)}</p>` : "";
  card.innerHTML = `
    <strong>${escapeHtml(result.question)}</strong>
    ${when}
    ${modelLabel}
    <p>${escapeHtml(result.answer)}</p>
    ${sourceHtml}
  `;
  card.querySelectorAll("[data-source-note-remove]").forEach((button) => {
    button.addEventListener("click", async () => {
      const removed = await removeNote(button.dataset.sourceNoteRemove);
      if (removed) {
        const sourceNode = button.closest(".sourceDetail");
        if (sourceNode) {
          sourceNode.remove();
        }
        setSearchState("Repository note removed from the demo store.");
      }
    });
  });
  root.prepend(card);
}

function renderSourceDetail(source) {
  const title = source.title || "Unknown source";
  const kind = source.kind === "note" ? "Repository note" : "Interview profile";
  const meta = [kind, source.source, source.role, formatShortDate(source.created_at)]
    .filter(Boolean)
    .join(" - ");
  const content = source.content || source.excerpt || "No source detail was captured.";
  const preview = source.excerpt || sentencePreview(content, 24);
  const removeAction = source.kind === "note" && source.id
    ? `<button type="button" class="dangerTextButton sourceRemoveButton" data-source-note-remove="${escapeHtml(source.id)}">Remove sensitive note</button>`
    : "";
  return `
    <details class="sourceDetail">
      <summary>
        <span>${escapeHtml(title)}</span>
        <small>${escapeHtml(meta)}</small>
        <em>${escapeHtml(preview)}</em>
      </summary>
      <p>${escapeHtml(content)}</p>
      ${removeAction}
    </details>
  `;
}

function formatShortDate(value) {
  if (!value) {
    return "";
  }
  return String(value).slice(0, 10);
}

function emptyState(label, detail = "Run an interview first.") {
  const node = document.createElement("div");
  node.className = "emptyState";
  node.innerHTML = `<strong>${escapeHtml(label)}</strong><span>${escapeHtml(detail)}</span>`;
  return node;
}

function trimLabel(value) {
  return value.length > 18 ? `${value.slice(0, 16)}..` : value;
}

function sentencePreview(value, limit = 24) {
  const words = String(value || "").trim().split(/\s+/).filter(Boolean);
  if (words.length <= limit) {
    return words.join(" ");
  }
  return `${words.slice(0, limit).join(" ")}...`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

init().catch((error) => {
  console.error(error);
  document.body.insertAdjacentHTML(
    "beforeend",
    `<div class="fatalError">${escapeHtml(error.message)}</div>`
  );
});
