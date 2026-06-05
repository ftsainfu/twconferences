const state = {
  conferences: [],
  filtered: [],
};

const els = {
  list: document.querySelector("#conferenceList"),
  empty: document.querySelector("#emptyState"),
  lastUpdated: document.querySelector("#lastUpdated"),
  sourceCount: document.querySelector("#sourceCount"),
  visibleCount: document.querySelector("#visibleCount"),
  newCount: document.querySelector("#newCount"),
  deadlineCount: document.querySelector("#deadlineCount"),
  keyword: document.querySelector("#keywordFilter"),
  month: document.querySelector("#monthFilter"),
  location: document.querySelector("#locationFilter"),
  deadlineBefore: document.querySelector("#deadlineBeforeFilter"),
  deadlineStatus: document.querySelector("#deadlineStatusFilter"),
  format: document.querySelector("#formatFilter"),
  sort: document.querySelector("#sortSelect"),
  reset: document.querySelector("#resetFilters"),
};

const today = new Date();
today.setHours(0, 0, 0, 0);

function parseDate(value) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00+08:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDate(value) {
  const date = parseDate(value);
  if (!date) return "未公告";
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    weekday: "short",
  }).format(date);
}

function isRecent(item) {
  const updated = parseDate(item.last_changed || item.created_at);
  if (!updated) return false;
  const diffDays = (today - updated) / 86400000;
  return diffDays <= 14;
}

function isDeadlineOpen(item) {
  const deadline = parseDate(item.submission_deadline);
  return deadline && deadline >= today;
}

function matchesFormat(item, format) {
  if (!format) return true;
  const formats = item.presentation_formats || [];
  if (format === "other") return formats.length === 0 || formats.includes("other");
  return formats.includes(format);
}

function matchesDeadlineStatus(item, status) {
  if (!status) return true;
  const deadline = parseDate(item.submission_deadline);
  if (status === "unknown") return !deadline;
  if (!deadline) return false;
  if (status === "open") return deadline >= today;
  if (status === "closed") return deadline < today;
  return true;
}

function applyFilters() {
  const keyword = els.keyword.value.trim().toLowerCase();
  const month = els.month.value;
  const location = els.location.value;
  const deadlineBefore = parseDate(els.deadlineBefore.value);
  const deadlineStatus = els.deadlineStatus.value;
  const format = els.format.value;

  state.filtered = state.conferences.filter((item) => {
    const haystack = [
      item.title,
      item.organizer,
      item.location,
      ...(item.fields || []),
      ...(item.attention_notes || []),
    ]
      .join(" ")
      .toLowerCase();
    const eventMonth = item.event_start ? item.event_start.slice(0, 7) : "";
    const deadline = parseDate(item.submission_deadline);

    return (
      (!keyword || haystack.includes(keyword)) &&
      (!month || eventMonth === month) &&
      (!location || item.location === location) &&
      (!deadlineBefore || (deadline && deadline <= deadlineBefore)) &&
      matchesDeadlineStatus(item, deadlineStatus) &&
      matchesFormat(item, format)
    );
  });

  sortItems();
  render();
}

function sortItems() {
  const sort = els.sort.value;
  const byDate = (key) => (a, b) => {
    const av = parseDate(a[key])?.getTime() || Number.MAX_SAFE_INTEGER;
    const bv = parseDate(b[key])?.getTime() || Number.MAX_SAFE_INTEGER;
    return av - bv;
  };

  const sorters = {
    event_asc: byDate("event_start"),
    deadline_asc: byDate("submission_deadline"),
    name_asc: (a, b) => a.title.localeCompare(b.title, "zh-Hant"),
    updated_desc: (a, b) => {
      const av = parseDate(a.last_checked || a.last_changed)?.getTime() || 0;
      const bv = parseDate(b.last_checked || b.last_changed)?.getTime() || 0;
      return bv - av;
    },
  };

  state.filtered.sort(sorters[sort] || sorters.updated_desc);
}

function presentationLabel(item) {
  const labels = {
    oral: "口頭發表",
    poster: "海報發表",
    online: "線上發表",
    other: "其他形式",
  };
  const formats = item.presentation_formats || [];
  return formats.length ? formats.map((format) => labels[format] || format).join("、") : "未明";
}

function render() {
  els.visibleCount.textContent = state.filtered.length;
  els.newCount.textContent = state.filtered.filter(isRecent).length;
  els.deadlineCount.textContent = state.filtered.filter(isDeadlineOpen).length;
  els.empty.hidden = state.filtered.length > 0;
  els.list.innerHTML = state.filtered.map(renderCard).join("");
}

function renderCard(item) {
  const recent = isRecent(item);
  const tags = (item.fields || []).map((field) => `<span class="field-tag">${escapeHtml(field)}</span>`).join("");
  const notes = (item.attention_notes || [])
    .map((note) => `<li>${escapeHtml(note)}</li>`)
    .join("");
  const registration = item.registration_url
    ? `<a href="${escapeAttr(item.registration_url)}" target="_blank" rel="noreferrer">報名連結</a>`
    : "";
  const submission = item.submission_url
    ? `<a href="${escapeAttr(item.submission_url)}" target="_blank" rel="noreferrer">投稿連結</a>`
    : "";

  return `
    <article class="conference-card ${recent ? "is-new" : ""}">
      <div>
        <h2 class="card-title">
          ${recent ? '<span class="new-badge">[NEW!]</span>' : ""}
          <span>${escapeHtml(item.title)}</span>
          ${item.review_status === "candidate" ? '<span class="status-badge">待確認</span>' : ""}
        </h2>
        <div>${tags}</div>
        <div class="meta-grid">
          <div><span>舉辦日期</span><strong>${formatDate(item.event_start)}</strong></div>
          <div><span>地點</span><strong>${escapeHtml(item.location || "未公告")}</strong></div>
          <div><span>投稿截止</span><strong>${formatDate(item.submission_deadline)}</strong></div>
          <div><span>主辦單位</span><strong>${escapeHtml(item.organizer || "未公告")}</strong></div>
          <div><span>發表形式</span><strong>${escapeHtml(presentationLabel(item))}</strong></div>
          <div><span>更新狀態</span><strong>${escapeHtml(item.change_label || "已檢查")}</strong></div>
        </div>
        ${item.change_summary ? `<p class="change-note">${escapeHtml(item.change_summary)}</p>` : ""}
        ${notes ? `<ul class="notes">${notes}</ul>` : ""}
      </div>
      <div class="card-actions">
        <a class="primary" href="${escapeAttr(item.homepage_url)}" target="_blank" rel="noreferrer">會議主頁</a>
        ${submission}
        ${registration}
      </div>
    </article>
  `;
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttr(value = "") {
  return escapeHtml(value);
}

function hydrateLocationFilter() {
  const locations = [...new Set(state.conferences.map((item) => item.location).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, "zh-Hant"),
  );
  els.location.insertAdjacentHTML(
    "beforeend",
    locations.map((location) => `<option value="${escapeAttr(location)}">${escapeHtml(location)}</option>`).join(""),
  );
}

function bindEvents() {
  [els.keyword, els.month, els.location, els.deadlineBefore, els.deadlineStatus, els.format, els.sort].forEach((input) => {
    input.addEventListener("input", applyFilters);
    input.addEventListener("change", applyFilters);
  });
  els.reset.addEventListener("click", () => {
    els.keyword.value = "";
    els.month.value = "";
    els.location.value = "";
    els.deadlineBefore.value = "";
    els.deadlineStatus.value = "";
    els.format.value = "";
    els.sort.value = "updated_desc";
    applyFilters();
  });
}

async function init() {
  const response = await fetch("data/conferences.json", { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load conference data");
  const payload = await response.json();
  state.conferences = payload.conferences || [];
  els.lastUpdated.textContent = payload.generated_at || "未產生";
  els.sourceCount.textContent = `${payload.source_count || state.conferences.length} 個來源`;
  hydrateLocationFilter();
  bindEvents();
  applyFilters();
}

init().catch((error) => {
  els.lastUpdated.textContent = "資料讀取失敗";
  els.sourceCount.textContent = error.message;
});
