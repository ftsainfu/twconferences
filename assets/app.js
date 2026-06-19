const state = {
  conferences: [],
  activeConferences: [],
  pastConferences: [],
  candidates: [],
  filtered: [],
  recurring: [],
  referenceDate: new Date(),
};

const els = {
  list: document.querySelector("#conferenceList"),
  historyList: document.querySelector("#historyList"),
  empty: document.querySelector("#emptyState"),
  historyEmpty: document.querySelector("#historyEmpty"),
  lastUpdated: document.querySelector("#lastUpdated"),
  sourceCount: document.querySelector("#sourceCount"),
  visibleCount: document.querySelector("#visibleCount"),
  newCount: document.querySelector("#newCount"),
  deadlineCount: document.querySelector("#deadlineCount"),
  upcomingCount: document.querySelector("#upcomingCount"),
  historyCount: document.querySelector("#historyCount"),
  keyword: document.querySelector("#keywordFilter"),
  month: document.querySelector("#monthFilter"),
  location: document.querySelector("#locationFilter"),
  eventStatus: document.querySelector("#eventStatusFilter"),
  deadlineBefore: document.querySelector("#deadlineBeforeFilter"),
  deadlineStatus: document.querySelector("#deadlineStatusFilter"),
  format: document.querySelector("#formatFilter"),
  englishPresentation: document.querySelector("#englishPresentationFilter"),
  sort: document.querySelector("#sortSelect"),
  reset: document.querySelector("#resetFilters"),
  recurringList: document.querySelector("#recurringList"),
  field: document.querySelector("#fieldFilter"),
  healthAlert: document.querySelector("#healthAlert"),
  candidateSection: document.querySelector("#candidateSection"),
  candidateList: document.querySelector("#candidateList"),
  candidateCount: document.querySelector("#candidateCount"),
  historyKeyword: document.querySelector("#historyKeyword"),
  historyYear: document.querySelector("#historyYear"),
  reportDialog: document.querySelector("#reportDialog"),
  reportForm: document.querySelector("#reportForm"),
  reportConferenceTitle: document.querySelector("#reportConferenceTitle"),
  reportType: document.querySelector("#reportType"),
  reportDetails: document.querySelector("#reportDetails"),
  correctionField: document.querySelector("#correctionField"),
  correctionValue: document.querySelector("#correctionValue"),
  evidenceUrl: document.querySelector("#evidenceUrl"),
  closeReportDialog: document.querySelector("#closeReportDialog"),
};

const fieldKeywords = {
  finance: ["財金", "財務", "金融", "投資", "證券", "銀行", "保險", "會計", "經濟", "理財", "風險管理", "fintech", "finance", "financial"],
  management: ["管理", "商管", "企業", "經營", "決策", "management", "business"],
  marketing: ["行銷", "品牌", "消費者", "通路", "marketing"],
  trade: ["國貿", "國際貿易", "國際企業", "跨國", "global business", "international trade"],
  sustainability: ["永續", "esg", "社會責任", "csr", "淨零", "碳"],
  technology: ["資訊", "數位", "科技", "人工智慧", "ai", "電子商務", "智慧"],
  health: ["健康", "醫療", "照護", "health", "hospital"],
};

let reportTarget = null;

const today = new Date();
today.setHours(0, 0, 0, 0);

function parseDate(value) {
  if (!value) return null;
  const date = new Date(`${value}T00:00:00+08:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function parseGeneratedDate(value) {
  if (!value) return today;
  const match = String(value).match(/\d{4}-\d{2}-\d{2}/);
  return match ? parseDate(match[0]) || today : today;
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

function eventStatus(item) {
  const start = parseDate(item.event_start);
  const end = parseDate(item.event_end) || start;
  if (!start) return "unknown";
  if (end < state.referenceDate) return "past";
  if (start <= state.referenceDate && end >= state.referenceDate) return "ongoing";
  return "upcoming";
}

function eventStatusLabel(item) {
  const labels = {
    upcoming: "即將舉辦",
    ongoing: "進行中",
    past: "已結束",
    unknown: "未公告日期",
  };
  return labels[eventStatus(item)];
}

function matchesFormat(item, format) {
  if (!format) return true;
  const formats = item.presentation_formats || [];
  if (format === "other") return formats.length === 0 || formats.includes("other");
  return formats.includes(format);
}

function acceptsEnglishPresentation(item) {
  return (item.presentation_languages || []).includes("en");
}

function matchesEnglishPresentation(item, value) {
  if (!value) return true;
  const acceptsEnglish = acceptsEnglishPresentation(item);
  if (value === "accepted") return acceptsEnglish;
  if (value === "not_accepted") return !acceptsEnglish;
  return true;
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

function matchesEventStatus(item, status) {
  return !status || eventStatus(item) === status;
}

function matchesField(item, selectedField) {
  if (!selectedField) return true;
  const haystack = [item.title, item.organizer, ...(item.fields || []), ...(item.attention_notes || [])]
    .join(" ")
    .toLowerCase();
  return (fieldKeywords[selectedField] || []).some((keyword) => haystack.includes(keyword));
}

function applyFilters() {
  const keyword = els.keyword.value.trim().toLowerCase();
  const month = els.month.value;
  const selectedField = els.field.value;
  const location = els.location.value;
  const selectedEventStatus = els.eventStatus.value;
  const deadlineBefore = parseDate(els.deadlineBefore.value);
  const deadlineStatus = els.deadlineStatus.value;
  const format = els.format.value;
  const englishPresentation = els.englishPresentation.value;

  state.filtered = state.activeConferences.filter((item) => {
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
      matchesField(item, selectedField) &&
      (!month || eventMonth === month) &&
      (!location || item.location === location) &&
      matchesEventStatus(item, selectedEventStatus) &&
      (!deadlineBefore || (deadline && deadline <= deadlineBefore)) &&
      matchesDeadlineStatus(item, deadlineStatus) &&
      matchesFormat(item, format) &&
      matchesEnglishPresentation(item, englishPresentation)
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

  state.filtered.sort(sorters[sort] || sorters.event_asc);
}

function sortPastItems(items) {
  return [...items].sort((a, b) => {
    const av = parseDate(a.event_end || a.event_start)?.getTime() || 0;
    const bv = parseDate(b.event_end || b.event_start)?.getTime() || 0;
    return bv - av;
  });
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

function languageLabel(item) {
  const labels = {
    zh: "中文",
    en: "英文",
    ja: "日文",
    unknown: "未明",
  };
  const languages = item.presentation_languages || [];
  return languages.length ? languages.map((language) => labels[language] || language).join("、") : "未明";
}

function render() {
  els.visibleCount.textContent = state.filtered.length;
  els.newCount.textContent = state.filtered.filter(isRecent).length;
  els.deadlineCount.textContent = state.filtered.filter(isDeadlineOpen).length;
  els.upcomingCount.textContent = state.activeConferences.length;
  const filteredHistory = getFilteredHistory();
  els.historyCount.textContent = filteredHistory.length;
  els.candidateCount.textContent = state.candidates.length;
  els.candidateSection.hidden = state.candidates.length === 0;
  els.empty.hidden = state.filtered.length > 0;
  els.historyEmpty.hidden = filteredHistory.length > 0;
  els.list.innerHTML = state.filtered.map(renderCard).join("");
  els.candidateList.innerHTML = state.candidates.map(renderCard).join("");
  els.historyList.innerHTML = sortPastItems(filteredHistory).map(renderCard).join("");
  renderRecurring();
}

function getFilteredHistory() {
  const keyword = (els.historyKeyword?.value || "").trim().toLowerCase();
  const year = els.historyYear?.value || "";
  return state.pastConferences.filter((item) => {
    const haystack = [item.title, item.organizer, item.location, ...(item.fields || [])].join(" ").toLowerCase();
    return (!keyword || haystack.includes(keyword)) && (!year || (item.event_start || "").startsWith(year));
  });
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
  const homepage = item.link_status === "reported_broken"
    ? '<span class="unavailable-link">主頁暫時無法連線</span>'
    : `<a class="primary" href="${escapeAttr(item.homepage_url)}" target="_blank" rel="noreferrer">會議主頁</a>`;

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
          <div><span>舉辦狀態</span><strong>${escapeHtml(eventStatusLabel(item))}</strong></div>
          <div><span>投稿截止</span><strong>${formatDate(item.submission_deadline)}</strong></div>
          <div><span>主辦單位</span><strong>${escapeHtml(item.organizer || "未公告")}</strong></div>
          <div><span>發表形式</span><strong>${escapeHtml(presentationLabel(item))}</strong></div>
          <div><span>發表語言</span><strong>${escapeHtml(languageLabel(item))}</strong></div>
          <div><span>更新狀態</span><strong>${escapeHtml(item.change_label || "已檢查")}</strong></div>
        </div>
        ${item.change_summary ? `<p class="change-note">${escapeHtml(item.change_summary)}</p>` : ""}
        ${notes ? `<ul class="notes">${notes}</ul>` : ""}
      </div>
      <div class="card-actions">
        ${homepage}
        ${submission}
        ${registration}
        <button
          class="report-button"
          type="button"
          data-report-id="${escapeAttr(item.id)}"
          data-report-title="${escapeAttr(item.title)}"
          data-report-url="${escapeAttr(item.homepage_url)}"
        >回報資料問題</button>
      </div>
    </article>
  `;
}

function renderRecurring() {
  if (!els.recurringList) return;
  els.recurringList.innerHTML = (state.recurring || [])
    .map(
      (item) => `
        <tr>
          <td><strong>${escapeHtml(item.name)}</strong></td>
          <td>${escapeHtml(item.organizer)}</td>
          <td>${escapeHtml(item.usual_month)}</td>
          <td>${escapeHtml(item.focus)}</td>
          <td><a href="${escapeAttr(item.official_url)}" target="_blank" rel="noreferrer">官方連結</a></td>
        </tr>
      `,
    )
    .join("");
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
  const locations = [...new Set(state.activeConferences.map((item) => item.location).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, "zh-Hant"),
  );
  els.location.insertAdjacentHTML(
    "beforeend",
    locations.map((location) => `<option value="${escapeAttr(location)}">${escapeHtml(location)}</option>`).join(""),
  );
}

function hydrateHistoryYearFilter() {
  const years = [...new Set(state.pastConferences.map((item) => (item.event_start || "").slice(0, 4)).filter(Boolean))]
    .sort()
    .reverse();
  els.historyYear.insertAdjacentHTML(
    "beforeend",
    years.map((year) => `<option value="${escapeAttr(year)}">${escapeHtml(year)} 年</option>`).join(""),
  );
}

function renderHealth(payload) {
  const generated = parseGeneratedDate(payload.generated_at);
  const ageDays = Math.floor((today - generated) / 86400000);
  const errorCount = payload.health?.source_error_count ?? (payload.errors || []).length;
  const messages = [];
  if (errorCount > 0) messages.push(`${errorCount} 個來源檢查失敗，部分資料沿用前次成功結果。`);
  if (ageDays >= 2) messages.push(`資料已 ${ageDays} 天未成功更新。`);
  els.healthAlert.hidden = messages.length === 0;
  els.healthAlert.textContent = messages.join(" ");
}

function openReportDialog(button) {
  reportTarget = {
    id: button.dataset.reportId,
    title: button.dataset.reportTitle,
    url: button.dataset.reportUrl,
  };
  els.reportConferenceTitle.textContent = reportTarget.title;
  els.reportForm.reset();
  els.reportDialog.showModal();
}

function submitReport(event) {
  event.preventDefault();
  if (!reportTarget) return;
  const singleLine = (value) => String(value || "").replace(/[\r\n]+/g, " ").trim();
  const body = [
    `conference_id: ${singleLine(reportTarget.id)}`,
    `conference_title: ${singleLine(reportTarget.title)}`,
    `current_url: ${singleLine(reportTarget.url)}`,
    `report_type: ${els.reportType.value}`,
    `correction_field: ${els.correctionField.value}`,
    `correction_value: ${singleLine(els.correctionValue.value)}`,
    `evidence_url: ${singleLine(els.evidenceUrl.value)}`,
    "",
    "details:",
    els.reportDetails.value.trim(),
  ].join("\n");
  const params = new URLSearchParams({
    title: `[資料回報] ${reportTarget.id} ${reportTarget.title}`,
    body,
    labels: "conference-report",
  });
  window.open(`https://github.com/ftsainfu/twconferences/issues/new?${params}`, "_blank", "noopener,noreferrer");
  els.reportDialog.close();
}

function bindEvents() {
  [els.keyword, els.field, els.month, els.location, els.eventStatus, els.deadlineBefore, els.deadlineStatus, els.format, els.englishPresentation, els.sort].forEach((input) => {
    input.addEventListener("input", applyFilters);
    input.addEventListener("change", applyFilters);
  });
  els.reset.addEventListener("click", () => {
    els.keyword.value = "";
    els.field.value = "";
    els.month.value = "";
    els.location.value = "";
    els.eventStatus.value = "";
    els.deadlineBefore.value = "";
    els.deadlineStatus.value = "";
    els.format.value = "";
    els.englishPresentation.value = "";
    els.sort.value = "event_asc";
    applyFilters();
  });
  [els.historyKeyword, els.historyYear].forEach((input) => {
    input.addEventListener("input", render);
    input.addEventListener("change", render);
  });
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-report-id]");
    if (button) openReportDialog(button);
  });
  els.closeReportDialog.addEventListener("click", () => els.reportDialog.close());
  els.reportForm.addEventListener("submit", submitReport);
}

async function init() {
  const response = await fetch("data/conferences.json", { cache: "no-store" });
  if (!response.ok) throw new Error("Failed to load conference data");
  const payload = await response.json();
  const recurringResponse = await fetch("data/recurring.json", { cache: "no-store" });
  const recurringPayload = recurringResponse.ok ? await recurringResponse.json() : { recurring_conferences: [] };
  state.conferences = payload.conferences || [];
  state.referenceDate = parseGeneratedDate(payload.generated_at);
  const verified = state.conferences.filter((item) => item.review_status !== "candidate");
  state.candidates = state.conferences.filter((item) => item.review_status === "candidate");
  state.activeConferences = verified.filter((item) => eventStatus(item) !== "past");
  state.pastConferences = verified.filter((item) => eventStatus(item) === "past");
  state.recurring = recurringPayload.recurring_conferences || [];
  els.lastUpdated.textContent = payload.generated_at || "未產生";
  els.sourceCount.textContent = `${payload.source_count || state.conferences.length} 個來源`;
  renderHealth(payload);
  hydrateLocationFilter();
  hydrateHistoryYearFilter();
  bindEvents();
  applyFilters();
}

init().catch((error) => {
  els.lastUpdated.textContent = "資料讀取失敗";
  els.sourceCount.textContent = error.message;
});
