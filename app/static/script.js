// ---------- View switching ----------
const navItems = document.querySelectorAll(".nav-item");
const views = {
  chat: document.getElementById("view-chat"),
  library: document.getElementById("view-library"),
  stats: document.getElementById("view-stats"),
};
const topbarTitle = document.getElementById("topbarTitle");
const titles = {
  chat: "Factory Knowledge Assistant",
  library: "Document Library",
  stats: "System Status",
};

function showToast(msg) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.classList.add("is-visible");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.remove("is-visible"), 2600);
}

navItems.forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.classList.contains("is-soon")) {
      showToast(btn.dataset.soon || "This section is coming soon.");
      return;
    }
    navItems.forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    Object.values(views).forEach((v) => v.classList.add("is-hidden"));
    const view = btn.dataset.view;
    views[view].classList.remove("is-hidden");
    topbarTitle.textContent = titles[view];
    if (view === "library" || view === "stats") loadStats();
  });
});

// ---------- Language toggle (UI chrome only) ----------
const langToggle = document.getElementById("langToggle");
const langLabel = document.getElementById("langLabel");
let uiLang = "en";
langToggle.addEventListener("click", () => {
  uiLang = uiLang === "en" ? "ja" : "en";
  langLabel.textContent = uiLang === "en" ? "English / 日本語" : "日本語 / English";
  document.getElementById("questionInput").placeholder =
    uiLang === "en" ? "Ask a question in English or 日本語…" : "質問を日本語または英語でどうぞ…";
});

// ---------- Text formatting helpers ----------

// Renders **bold** markers inside a line as real <strong> text, safely
// (builds DOM nodes, never uses innerHTML on model output directly).
function appendFormattedText(el, text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  parts.forEach((part) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      const strong = document.createElement("strong");
      strong.textContent = part.slice(2, -2);
      el.appendChild(strong);
    } else if (part) {
      el.appendChild(document.createTextNode(part));
    }
  });
}

// Detects numbered ("1. ") or bulleted ("- ") steps anywhere in the answer
// and renders them as a proper indented list instead of one run-on
// paragraph, so multi-step answers read neatly. Falls back to a plain
// paragraph (still with bold support) for normal answers.
function renderAnswer(container, text) {
  text = text || "(no answer)";

  let lines = text.split("\n").map((l) => l.trim()).filter((l) => l);
  if (lines.length <= 1) {
    const bySteps = text.split(/(?=\d+[\.\)]\s)/).map((l) => l.trim()).filter((l) => l);
    if (bySteps.length > 1) lines = bySteps;
  }

  const stepPattern = /^\d+[\.\)]\s+/;
  const bulletPattern = /^[-•]\s+/;
  const stepLines = lines.filter((l) => stepPattern.test(l));
  const bulletLines = lines.filter((l) => bulletPattern.test(l));

  if (stepLines.length >= 2 || bulletLines.length >= 2) {
    const pattern = stepLines.length >= 2 ? stepPattern : bulletPattern;
    const tag = stepLines.length >= 2 ? "ol" : "ul";
    const intro = [];
    const items = [];
    lines.forEach((l) => {
      if (pattern.test(l)) {
        items.push(l.replace(pattern, ""));
      } else {
        intro.push(l);
      }
    });
    if (intro.length) {
      const p = document.createElement("p");
      appendFormattedText(p, intro.join(" "));
      container.appendChild(p);
    }
    const list = document.createElement(tag);
    list.className = "answer-list";
    items.forEach((item) => {
      const li = document.createElement("li");
      appendFormattedText(li, item);
      list.appendChild(li);
    });
    container.appendChild(list);
  } else {
    const p = document.createElement("p");
    appendFormattedText(p, text);
    container.appendChild(p);
  }
}

function docIcon() {
  return `<svg viewBox="0 0 20 20" fill="none"><path d="M4 4.5h7.5a2 2 0 0 1 2 2V16H6a2 2 0 0 1-2-2V4.5Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>`;
}

function imageIcon() {
  return `<svg viewBox="0 0 20 20" fill="none"><rect x="3" y="4" width="14" height="12" rx="1.4" stroke="currentColor" stroke-width="1.3"/><circle cx="7.2" cy="8" r="1.1" stroke="currentColor" stroke-width="1.2"/><path d="M4 14.5 8 10l3 3 2-2.2L17 14" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>`;
}

// Renders the "Sources" tag row directly inside a message bubble, so it
// stays attached to that specific answer permanently (not just in the
// separate side panel, which only ever reflects the latest question).
function renderInlineSources(container, sources) {
  if (!sources || !sources.length || sources[0] === "No specific source cited") return;
  const row = document.createElement("div");
  row.className = "inline-sources";
  const label = document.createElement("span");
  label.className = "inline-sources-label";
  label.textContent = "Sources:";
  row.appendChild(label);
  sources.forEach((s) => {
    const tag = document.createElement("span");
    tag.className = "source-inline";
    tag.textContent = s;
    row.appendChild(tag);
  });
  container.appendChild(row);
}

// Renders supporting images inline, with a visible fallback (not a raw
// path, not a silently broken image icon) if a file genuinely can't load.
function renderImages(container, imageUrls) {
  if (!imageUrls || !imageUrls.length) return;
  const imgDiv = document.createElement("div");
  imgDiv.className = "qa-images";
  imageUrls.forEach((u) => {
    const wrap = document.createElement("div");
    wrap.className = "qa-image-wrap";
    const img = document.createElement("img");
    img.src = u;
    img.loading = "lazy";
    img.alt = "Supporting diagram";
    img.onerror = () => {
      wrap.innerHTML = `<div class="qa-image-fallback">${imageIcon()}<span>Image could not be loaded</span></div>`;
    };
    wrap.appendChild(img);
    imgDiv.appendChild(wrap);
  });
  container.appendChild(imgDiv);
}

// ---------- Ask form ----------
const askForm = document.getElementById("askForm");
const questionInput = document.getElementById("questionInput");
const askButton = document.getElementById("askButton");
const thread = document.getElementById("thread");
const sourcesPanel = document.getElementById("sourcesPanel");

questionInput.addEventListener("input", () => {
  questionInput.style.height = "auto";
  questionInput.style.height = Math.min(questionInput.scrollHeight, 130) + "px";
});

questionInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    askForm.requestSubmit();
  }
});

document.querySelectorAll(".example-chip, .quick-action").forEach((el) => {
  el.addEventListener("click", () => {
    questionInput.value = el.dataset.q;
    askForm.requestSubmit();
  });
});

askForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  const userMsg = document.createElement("div");
  userMsg.className = "msg msg-user";
  userMsg.innerHTML = `<div class="avatar-sm avatar-user">You</div><div class="bubble bubble-user"></div>`;
  userMsg.querySelector(".bubble").textContent = question;
  thread.appendChild(userMsg);

  const botMsg = document.createElement("div");
  botMsg.className = "msg msg-bot";
  botMsg.innerHTML = `<div class="avatar-sm avatar-bot">NI</div><div class="bubble bubble-bot"><div class="qa-loading">Searching and generating answer <span class="dots"><span></span><span></span><span></span></span></div></div>`;
  thread.appendChild(botMsg);

  thread.scrollIntoView({ block: "end" });
  questionInput.value = "";
  questionInput.style.height = "auto";
  askButton.disabled = true;

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();

    // Helpful during setup: log exactly what the backend returned for
    // images, so a missing-image issue can be diagnosed from DevTools
    // Console instead of guessing.
    console.log("Answer response:", data);

    const bubble = botMsg.querySelector(".bubble");

    // If the backend returned an error status (e.g. the model call timed
    // out or Ollama was unreachable), show that error clearly instead of
    // falling through to the normal answer-rendering path - otherwise
    // data.answer/data.sources are undefined and this would silently look
    // like a false "not found, no sources" answer instead of a real failure.
    if (!res.ok) {
      bubble.classList.remove("is-clarification");
      bubble.innerHTML = "";
      const p = document.createElement("p");
      p.textContent = data.error || "Something went wrong answering this question. Please try again.";
      bubble.appendChild(p);
      sourcesPanel.innerHTML = `<div class="panel-empty">No answer was generated for this question.</div>`;
      return;
    }

    const isClarification = /could you specify|which product|which equipment|どの製品|教えていただけます/i.test(data.answer || "");
    bubble.classList.toggle("is-clarification", isClarification);
    bubble.innerHTML = "";

    renderAnswer(bubble, data.answer);
    renderImages(bubble, data.image_urls);
    renderInlineSources(bubble, data.sources);

    const langDiv = document.createElement("div");
    langDiv.className = "qa-lang";
    langDiv.textContent = data.detected_language || "English";
    bubble.appendChild(langDiv);

    // also refresh the side panel to reflect the latest answer
    sourcesPanel.innerHTML = "";
    if (data.sources && data.sources.length && data.sources[0] !== "No specific source cited") {
      data.sources.forEach((s) => {
        const row = document.createElement("div");
        row.className = "panel-source";
        row.innerHTML = `${docIcon()}<span class="panel-source-text"></span>`;
        row.querySelector(".panel-source-text").textContent = s;
        sourcesPanel.appendChild(row);
      });
    } else {
      sourcesPanel.innerHTML = `<div class="panel-empty">No specific source was cited for this answer.</div>`;
    }

  } catch (err) {
    botMsg.querySelector(".bubble").innerHTML =
      `<p>Could not reach the local server. Confirm app.py is still running, then try again.</p>`;
    console.error(err);
  } finally {
    askButton.disabled = false;
    thread.scrollIntoView({ block: "end" });
  }
});

// ---------- Connection status ----------
async function checkStatus() {
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("statusText");
  try {
    const res = await fetch("/api/stats");
    if (res.ok) {
      dot.classList.add("is-online");
      dot.classList.remove("is-offline");
      text.textContent = "Connected — running locally";
      const data = await res.json();
      const badge = document.getElementById("badgeDocs");
      if (badge) badge.textContent = `${data.total_documents ?? "—"} manuals indexed`;
    } else {
      throw new Error();
    }
  } catch {
    dot.classList.add("is-offline");
    dot.classList.remove("is-online");
    text.textContent = "Not connected";
  }
}

// ---------- Library / Stats data ----------
async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();

    const statDocs = document.getElementById("statDocs");
    if (statDocs) statDocs.textContent = data.total_documents ?? "—";
    const statChunks = document.getElementById("statChunks");
    if (statChunks) statChunks.textContent = data.total_chunks ?? "—";
    const statAccuracy = document.getElementById("statAccuracy");
    if (statAccuracy) statAccuracy.textContent = data.measured_accuracy != null ? data.measured_accuracy + "%" : "Not yet measured";
    const statQuestions = document.getElementById("statQuestions");
    if (statQuestions) statQuestions.textContent = data.total_test_questions ?? "—";

    const docList = document.getElementById("docList");
    if (docList) {
      docList.innerHTML = "";
      (data.documents || []).forEach((d) => {
        const row = document.createElement("div");
        row.className = "doc-row";
        row.innerHTML = `${docIcon()}<span></span>`;
        row.querySelector("span").textContent = d;
        docList.appendChild(row);
      });
    }
  } catch {
    // leave placeholders if the server isn't reachable
  }
}

checkStatus();
setInterval(checkStatus, 15000);