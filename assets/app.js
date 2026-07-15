const state = {
  conferences: [],
  activeConferences: [],
  pastConferences: [],
  candidates: [],
  filtered: [],
  recurring: [],
  grants: [],
  grantPayload: null,
  grantLanguage: "zh",
  ratings: {},
  siteConfig: { rating_api_url: "", rating_api_mode: "cors", rating_fallback: "github" },
  trackedIds: new Set(),
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
  dashboardYear: document.querySelector("#dashboardYear"),
  dashboardScope: document.querySelector("#dashboardScope"),
  monthlyChart: document.querySelector("#monthlyChart"),
  deadlinePeak: document.querySelector("#deadlinePeak"),
  eventPeak: document.querySelector("#eventPeak"),
  planningAdvice: document.querySelector("#planningAdvice"),
  historyCount: document.querySelector("#historyCount"),
  keyword: document.querySelector("#keywordFilter"),
  month: document.querySelector("#monthFilter"),
  location: document.querySelector("#locationFilter"),
  eventStatus: document.querySelector("#eventStatusFilter"),
  deadlineBefore: document.querySelector("#deadlineBeforeFilter"),
  deadlineStatus: document.querySelector("#deadlineStatusFilter"),
  format: document.querySelector("#formatFilter"),
  englishPresentation: document.querySelector("#englishPresentationFilter"),
  trackedOnly: document.querySelector("#trackedOnlyFilter"),
  sort: document.querySelector("#sortSelect"),
  reset: document.querySelector("#resetFilters"),
  recurringList: document.querySelector("#recurringList"),
  grantList: document.querySelector("#grantList"),
  grantNotice: document.querySelector("#grantNotice"),
  grantVerified: document.querySelector("#grantVerified"),
  grantLanguageButtons: [...document.querySelectorAll("[data-grant-language]")],
  grantTitle: document.querySelector("#grantsTitle"),
  grantIntro: document.querySelector("#grantIntro"),
  grantPriorityTitle: document.querySelector("#grantPriorityTitle"),
  grantPriorityPrimary: document.querySelector("#grantPriorityPrimary"),
  grantPrioritySecondary: document.querySelector("#grantPrioritySecondary"),
  eligibilityChecker: document.querySelector("#eligibilityChecker"),
  eligibilityEnrollment: document.querySelector("#eligibilityEnrollment"),
  eligibilityInService: document.querySelector("#eligibilityInService"),
  eligibilityConferenceScope: document.querySelector("#eligibilityConferenceScope"),
  eligibilityPaper: document.querySelector("#eligibilityPaper"),
  eligibilityFundedThisYear: document.querySelector("#eligibilityFundedThisYear"),
  eligibilityCoauthor: document.querySelector("#eligibilityCoauthor"),
  eligibilityAcceptance: document.querySelector("#eligibilityAcceptance"),
  eligibilityEventDate: document.querySelector("#eligibilityEventDate"),
  eligibilityResult: document.querySelector("#eligibilityResult"),
  eligibilityTitle: document.querySelector("#eligibilityTitle"),
  eligibilityHelp: document.querySelector("#eligibilityHelp"),
  eligibilitySubmit: document.querySelector("#eligibilitySubmit"),
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
  ratingDialog: document.querySelector("#ratingDialog"),
  ratingForm: document.querySelector("#ratingForm"),
  ratingConferenceTitle: document.querySelector("#ratingConferenceTitle"),
  ratingParticipation: document.querySelector("#ratingParticipation"),
  ratingNickname: document.querySelector("#ratingNickname"),
  ratingComment: document.querySelector("#ratingComment"),
  ratingConfirmed: document.querySelector("#ratingConfirmed"),
  ratingStatus: document.querySelector("#ratingStatus"),
  closeRatingDialog: document.querySelector("#closeRatingDialog"),
  pageTabs: document.querySelector(".page-tabs"),
  tabButtons: [...document.querySelectorAll("[data-tab]")],
  conferencesPanel: document.querySelector("#conferencesPanel"),
  grantsPanel: document.querySelector("#grants"),
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
let ratingTarget = null;

function setActiveTab(tabName, updateHash = true) {
  const activeName = tabName === "grants" ? "grants" : "conferences";
  const panels = {
    conferences: els.conferencesPanel,
    grants: els.grantsPanel,
  };
  Object.entries(panels).forEach(([name, panel]) => {
    if (panel) panel.hidden = name !== activeName;
  });
  els.tabButtons.forEach((button) => {
    const selected = button.dataset.tab === activeName;
    button.setAttribute("aria-selected", String(selected));
    button.tabIndex = selected ? 0 : -1;
  });
  if (updateHash) {
    const hash = activeName === "grants" ? "#grants" : "#conferences";
    window.history.replaceState(null, "", hash);
  }
}

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

function calendarDate(value, offsetDays = 0) {
  const match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return "";
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]) + offsetDays));
  return [
    date.getUTCFullYear(),
    String(date.getUTCMonth() + 1).padStart(2, "0"),
    String(date.getUTCDate()).padStart(2, "0"),
  ].join("");
}

function googleCalendarLink({ date, title, details = "", location = "", label = "加入日曆" }) {
  const start = calendarDate(date);
  if (!start) return "";
  const end = calendarDate(date, 1);
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: title,
    dates: `${start}/${end}`,
    details,
    location,
    ctz: "Asia/Taipei",
  });
  return `<a class="date-action" href="https://calendar.google.com/calendar/render?${params.toString()}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`;
}

function acceptanceCalendarLink(item) {
  return googleCalendarLink({
    date: item.acceptance_notification_date,
    title: `審查結果通知：${item.title || "研討會"}`,
    details: [
      "提醒確認研討會投稿審查結果或錄取通知。",
      item.homepage_url ? `官方頁面：${item.homepage_url}` : "",
    ].filter(Boolean).join("\n"),
    location: item.location || "",
  });
}

function deadlineLabel(item) {
  const current = formatDate(item.submission_deadline);
  if (item.submission_deadline_status === "extended" && item.submission_deadline_previous) {
    return `${current}（已延後，原 ${formatDate(item.submission_deadline_previous)}）`;
  }
  return current;
}

function milestoneState(dateValue) {
  const date = parseDate(dateValue);
  if (!date) return "unknown";
  return date < today ? "past" : "upcoming";
}

function nextImportantMilestone(item) {
  const milestones = [
    { key: "submission", label: "投稿截止", date: item.submission_deadline },
    { key: "acceptance", label: "審查結果", date: item.acceptance_notification_date },
    { key: "event", label: "會議開始", date: item.event_start },
  ]
    .map((milestone) => ({ ...milestone, parsed: parseDate(milestone.date) }))
    .filter((milestone) => milestone.parsed && milestone.parsed >= today)
    .sort((a, b) => a.parsed - b.parsed);
  if (!milestones.length) return "重要日期皆已過或尚未公告。";
  const next = milestones[0];
  const days = Math.ceil((next.parsed - today) / 86400000);
  if (days === 0) return `今天是${next.label}。`;
  return `下一個重要日期：${next.label}，還有 ${days} 天。`;
}

function renderDateTimeline(item) {
  const details = (label) => [
    `提醒：${label}`,
    item.title ? `研討會：${item.title}` : "",
    item.homepage_url ? `官方頁面：${item.homepage_url}` : "",
  ].filter(Boolean).join("\n");
  const milestones = [
    {
      label: "投稿截止",
      date: item.submission_deadline,
      display: deadlineLabel(item),
      title: `投稿截止：${item.title || "研討會"}`,
    },
    {
      label: "審查結果",
      date: item.acceptance_notification_date,
      display: formatDate(item.acceptance_notification_date),
      title: `審查結果通知：${item.title || "研討會"}`,
    },
    {
      label: "會議日期",
      date: item.event_start,
      display: item.event_end && item.event_end !== item.event_start
        ? `${formatDate(item.event_start)} – ${formatDate(item.event_end)}`
        : formatDate(item.event_start),
      title: `會議開始：${item.title || "研討會"}`,
    },
  ];
  return `
    <section class="date-planner" aria-label="重要日期時程">
      <p class="next-milestone">${escapeHtml(nextImportantMilestone(item))}</p>
      <ol class="date-timeline">
        ${milestones.map((milestone) => `
          <li class="timeline-item timeline-item--${milestoneState(milestone.date)}">
            <span>${escapeHtml(milestone.label)}</span>
            <strong>${escapeHtml(milestone.display)}</strong>
            ${googleCalendarLink({
              date: milestone.date,
              title: milestone.title,
              details: details(milestone.label),
              location: item.location || "",
              label: "加入日曆",
            })}
          </li>
        `).join("")}
      </ol>
    </section>
  `;
}

function loadTrackedIds() {
  try {
    return new Set(JSON.parse(localStorage.getItem("twconferences.trackedIds") || "[]"));
  } catch {
    return new Set();
  }
}

function saveTrackedIds() {
  localStorage.setItem("twconferences.trackedIds", JSON.stringify([...state.trackedIds]));
}

function loadVoterId() {
  const storageKey = "twconferences.ratingVoterId";
  try {
    const existing = localStorage.getItem(storageKey);
    if (existing) return existing;
    const generated = window.crypto?.randomUUID
      ? window.crypto.randomUUID()
      : `voter-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem(storageKey, generated);
    return generated;
  } catch {
    return `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
}

function isTracked(item) {
  return state.trackedIds.has(item.id);
}

function toggleTracked(conferenceId) {
  if (state.trackedIds.has(conferenceId)) {
    state.trackedIds.delete(conferenceId);
  } else {
    state.trackedIds.add(conferenceId);
  }
  saveTrackedIds();
  applyFilters();
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
  const publicationText = (item.publication_opportunities || []).flatMap((publication) => [
    publication.journal_name,
    publication.notes,
  ]);
  const haystack = [item.title, item.organizer, ...(item.fields || []), ...(item.attention_notes || []), ...publicationText]
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
  const trackedOnly = Boolean(els.trackedOnly?.checked);

  state.filtered = state.activeConferences.filter((item) => {
    const publicationText = (item.publication_opportunities || []).flatMap((publication) => [
      publication.journal_name,
      publication.notes,
    ]);
    const haystack = [
      item.title,
      item.organizer,
      item.location,
      item.submission_fee,
      item.registration_fee,
      ...(item.fields || []),
      ...(item.attention_notes || []),
      ...publicationText,
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
      matchesEnglishPresentation(item, englishPresentation) &&
      (!trackedOnly || isTracked(item))
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
    rating_desc: (a, b) => {
      const aRating = state.ratings[a.id];
      const bRating = state.ratings[b.id];
      const averageDifference = (bRating?.average || 0) - (aRating?.average || 0);
      return averageDifference || (bRating?.count || 0) - (aRating?.count || 0) || byDate("event_start")(a, b);
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

function monthlyConferenceCounts(items, year) {
  const months = Array.from({ length: 12 }, (_, index) => ({
    month: index + 1,
    deadline: 0,
    event: 0,
  }));
  items.forEach((item) => {
    const eventMatch = String(item.event_start || "").match(/^(\d{4})-(\d{2})-/);
    if (eventMatch && eventMatch[1] === String(year)) {
      months[Number(eventMatch[2]) - 1].event += 1;
    }
    const deadlineMatch = String(item.submission_deadline || "").match(/^(\d{4})-(\d{2})-/);
    if (deadlineMatch && deadlineMatch[1] === String(year)) {
      months[Number(deadlineMatch[2]) - 1].deadline += 1;
    }
  });
  return months;
}

function peakMonthLabel(months, key) {
  const peak = Math.max(...months.map((item) => item[key]));
  if (!peak) return "尚無資料";
  const peakMonths = months.filter((item) => item[key] === peak).map((item) => `${item.month} 月`);
  return `${peakMonths.join("、")}（${peak} 場）`;
}

function renderMonthlyDashboard() {
  if (!els.monthlyChart || !els.dashboardYear) return;
  const verified = state.conferences.filter((item) => item.review_status !== "candidate");
  const sourceItems = els.dashboardScope?.value === "all" ? verified : state.filtered;
  const year = els.dashboardYear.value || String(state.referenceDate.getFullYear());
  const months = monthlyConferenceCounts(sourceItems, year);
  const contributingItems = sourceItems.filter(
    (item) => String(item.event_start || "").startsWith(year) || String(item.submission_deadline || "").startsWith(year),
  );
  const maxCount = Math.max(1, ...months.flatMap((item) => [item.deadline, item.event]));
  els.deadlinePeak.textContent = peakMonthLabel(months, "deadline");
  els.eventPeak.textContent = peakMonthLabel(months, "event");
  const deadlinePeak = Math.max(...months.map((item) => item.deadline));
  const peakLead = deadlinePeak ? "高峰前 2–3 個月開始準備" : "目前資料不足，請持續追蹤";
  els.planningAdvice.textContent = `${contributingItems.length} 場；${peakLead}`;
  els.monthlyChart.setAttribute(
    "aria-label",
    `${year} 年各月研討會數量：${months.map((item) => `${item.month} 月投稿截止 ${item.deadline} 場、活動舉辦 ${item.event} 場`).join("；")}`,
  );
  els.monthlyChart.innerHTML = months
    .map((item) => {
      const deadlineHeight = item.deadline ? Math.max(8, Math.round((item.deadline / maxCount) * 100)) : 0;
      const eventHeight = item.event ? Math.max(8, Math.round((item.event / maxCount) * 100)) : 0;
      return `
        <div class="month-column" aria-label="${item.month} 月：投稿截止 ${item.deadline} 場，活動舉辦 ${item.event} 場">
          <div class="month-bars" aria-hidden="true">
            <div class="month-bar-slot">
              <span class="month-count">${item.deadline}</span>
              <i class="month-bar month-bar--deadline" style="height: ${deadlineHeight}%"></i>
            </div>
            <div class="month-bar-slot">
              <span class="month-count">${item.event}</span>
              <i class="month-bar month-bar--event" style="height: ${eventHeight}%"></i>
            </div>
          </div>
          <strong>${item.month} 月</strong>
        </div>
      `;
    })
    .join("");
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

function feeLabel(value) {
  return value ? escapeHtml(value) : "未公告";
}

function starText(value) {
  const score = Math.max(0, Math.min(5, Math.round(Number(value) || 0)));
  return `${"★".repeat(score)}${"☆".repeat(5 - score)}`;
}

function renderRatingSummary(item) {
  const quality = item.information_quality || { score: 0, max_score: 5, label: "資料不足" };
  const attendee = state.ratings[item.id];
  const qualityCriteria = (quality.criteria || []).join("、") || "尚無符合項目";
  const attendeeValue = item.review_status === "candidate"
    ? '<span class="rating-value">正式收錄後開放評分</span>'
    : attendee
    ? `<span class="stars" aria-label="參加者推薦 ${escapeAttr(attendee.average)} 分">${starText(attendee.average)}</span><span class="rating-value">${escapeHtml(attendee.average)} / 5・${escapeHtml(attendee.count)} 票</span>`
    : '<span class="rating-value">尚無參加者評分</span>';
  return `
    <div class="rating-summary">
      <div class="rating-metric" title="${escapeAttr(qualityCriteria)}">
        <span>資料完整度</span>
        <span class="stars" aria-label="資料完整度 ${escapeAttr(quality.score)} 分">${starText(quality.score)}</span>
        <span class="rating-value">${escapeHtml(quality.score)} / ${escapeHtml(quality.max_score)}・${escapeHtml(quality.label)}</span>
      </div>
      <div class="rating-metric">
        <span>參加者推薦</span>
        ${attendeeValue}
      </div>
    </div>
  `;
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
  renderMonthlyDashboard();
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
  const tracked = isTracked(item);
  const tags = (item.fields || []).map((field) => `<span class="field-tag">${escapeHtml(field)}</span>`).join("");
  const notes = (item.attention_notes || [])
    .map((note) => `<li>${escapeHtml(note)}</li>`)
    .join("");
  const linkHealth = item.link_health || {};
  const renderActionLink = (field, label, className = "") => {
    const url = item[field];
    if (!url) return "";
    const health = linkHealth[field] || {};
    if (health.status === "broken") {
      return `<span class="unavailable-link">${escapeHtml(label)}可能失效</span>`;
    }
    const warningClass = health.status === "warning" ? " link-warning" : "";
    const title = health.status === "warning" ? ' title="最近一次檢查失敗；連續失敗後才會標示為可能失效"' : "";
    const classes = `${className}${warningClass}`.trim();
    const classAttr = classes ? ` class="${escapeAttr(classes)}"` : "";
    return `<a${classAttr} href="${escapeAttr(url)}" target="_blank" rel="noreferrer"${title}>${escapeHtml(label)}</a>`;
  };
  const registration = renderActionLink("registration_url", "報名連結");
  const submission = renderActionLink("submission_url", "投稿連結");
  const homepage = renderActionLink("homepage_url", "會議主頁", "primary");
  const publications = (item.publication_opportunities || [])
    .map((publication) => {
      const journalName = publication.journal_url
        ? `<a href="${escapeAttr(publication.journal_url)}" target="_blank" rel="noreferrer">${escapeHtml(publication.journal_name)}</a>`
        : `<strong>${escapeHtml(publication.journal_name)}</strong>`;
      const journalSubmission = publication.submission_url
        ? ` <a href="${escapeAttr(publication.submission_url)}" target="_blank" rel="noreferrer">期刊投稿</a>`
        : "";
      const publicationNotes = publication.notes ? `<span>${escapeHtml(publication.notes)}</span>` : "";
      return `<li>${journalName}${journalSubmission}${publicationNotes}</li>`;
    })
    .join("");
  const corroboration = item.is_corroborated
    ? `<p class="corroboration-note">已由 ${Number(item.independent_source_count) || 2} 個獨立來源交叉發現</p>`
    : "";

  return `
    <article class="conference-card ${recent ? "is-new" : ""} ${tracked ? "is-tracked" : ""}">
      <div>
        <h2 class="card-title">
          ${recent ? '<span class="new-badge">[NEW!]</span>' : ""}
          <span>${escapeHtml(item.title)}</span>
          ${item.review_status === "candidate" ? '<span class="status-badge">待確認</span>' : ""}
          ${tracked ? '<span class="tracked-badge">追蹤中</span>' : ""}
        </h2>
        <div>${tags}</div>
        ${renderRatingSummary(item)}
        ${renderDateTimeline(item)}
        <div class="meta-grid">
          <div><span>舉辦日期</span><strong>${formatDate(item.event_start)}</strong></div>
          <div><span>地點</span><strong>${escapeHtml(item.location || "未公告")}</strong></div>
          <div><span>舉辦狀態</span><strong>${escapeHtml(eventStatusLabel(item))}</strong></div>
          <div><span>投稿截止</span><strong>${escapeHtml(deadlineLabel(item))}</strong></div>
          <div><span>審查結果</span><strong>${formatDate(item.acceptance_notification_date)}</strong>${acceptanceCalendarLink(item)}</div>
          <div class="fee-meta"><span>投稿／審稿費</span><strong>${feeLabel(item.submission_fee)}</strong></div>
          <div class="fee-meta"><span>註冊／報名費</span><strong>${feeLabel(item.registration_fee)}</strong></div>
          <div><span>主辦單位</span><strong>${escapeHtml(item.organizer || "未公告")}</strong></div>
          <div><span>發表形式</span><strong>${escapeHtml(presentationLabel(item))}</strong></div>
          <div><span>發表語言</span><strong>${escapeHtml(languageLabel(item))}</strong></div>
          <div><span>更新狀態</span><strong>${escapeHtml(item.change_label || "已檢查")}</strong></div>
        </div>
        ${item.change_summary ? `<p class="change-note">${escapeHtml(item.change_summary)}</p>` : ""}
        ${item.link_health_summary ? `<p class="link-health-note">${escapeHtml(item.link_health_summary)}</p>` : ""}
        ${corroboration}
        ${publications ? `<section class="publication-info"><h3>合作期刊／專刊投稿</h3><ul>${publications}</ul></section>` : ""}
        ${notes ? `<ul class="notes">${notes}</ul>` : ""}
      </div>
      <div class="card-actions">
        ${item.review_status === "candidate" ? "" : `
          <button
            class="track-button"
            type="button"
            data-track-id="${escapeAttr(item.id)}"
            aria-pressed="${tracked ? "true" : "false"}"
          >${tracked ? "取消追蹤" : "加入追蹤"}</button>
        `}
        ${homepage}
        ${submission}
        ${registration}
        ${item.review_status === "candidate" ? "" : `
          <button
            class="rating-button"
            type="button"
            data-rating-id="${escapeAttr(item.id)}"
            data-rating-title="${escapeAttr(item.title)}"
          >評分推薦度</button>
        `}
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

function renderGrantSection(title, items, ordered = false) {
  if (!items?.length) return "";
  const tag = ordered ? "ol" : "ul";
  return `
    <section class="grant-detail">
      <h4>${escapeHtml(title)}</h4>
      <${tag}>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</${tag}>
    </section>
  `;
}

function renderGrants(payload = state.grantPayload) {
  if (!els.grantList) return;
  if (!payload) return;
  state.grantPayload = payload;
  const isEnglish = state.grantLanguage === "en";
  const labels = isEnglish
    ? {
        eligibility: "Eligibility",
        funding: "Funding and awards",
        deadline: "Key deadlines",
        documents: "Required documents",
        steps: "Application and reimbursement process",
        cautions: "Important notes",
      }
    : {
        eligibility: "申請資格",
        funding: "補助內容",
        deadline: "期限重點",
        documents: "應備文件",
        steps: "申請與核銷流程",
        cautions: "重要提醒",
      };
  const programs = [...(payload.programs || [])].sort((a, b) => (a.priority || 99) - (b.priority || 99));
  state.grants = programs;
  els.grantLanguageButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.grantLanguage === state.grantLanguage));
  });
  els.grantTitle.textContent = isEnglish ? "Conference Funding and Student Awards" : "學生研討會獎補助專區";
  els.grantIntro.textContent = isEnglish
    ? "Funding for graduate students presenting at international conferences, plus NFU awards for students who win eligible conference competitions."
    : "整理國科會研究生出席國際學術會議補助，以及虎科大學生於研討會競賽獲獎後可查詢的技藝獎金，包含資格、期限、文件與申請流程。";
  els.grantVerified.textContent = payload.last_verified
    ? isEnglish ? `Official information checked: ${payload.last_verified}` : `官方資料查核日：${payload.last_verified}`
    : isEnglish ? "Verification date unavailable" : "查核日期未提供";
  const notice = isEnglish ? payload.notice_en : payload.notice;
  els.grantNotice.hidden = !notice;
  els.grantNotice.textContent = notice || "";
  els.grantPriorityTitle.textContent = isEnglish ? "Recommended order" : "建議申請順序";
  els.grantPriorityPrimary.textContent = isEnglish
    ? "1. Apply first for the NSTC International Conference Grant for Graduate Students."
    : "① 國科會研究生出席國際學術會議補助";
  els.grantPrioritySecondary.textContent = isEnglish
    ? "2. If the approved amount is insufficient, ask NFU about current internal programs or cost sharing."
    : "② 核定不足時，再詢問虎科大研發處是否有當年度校內專案或可分攤經費";
  els.eligibilityTitle.textContent = isEnglish ? "NSTC Grant Preliminary Eligibility Check" : "國科會補助資格初篩";
  els.eligibilityHelp.textContent = isEnglish
    ? "For preparation only. This does not replace formal review by NFU and NSTC."
    : "僅供準備申請使用，不取代虎科大及國科會正式審查。";
  els.eligibilitySubmit.textContent = isEnglish ? "Check eligibility" : "開始初篩／Check eligibility";
  els.grantList.innerHTML = programs
    .map((program) => {
      const view = isEnglish && program.english ? { ...program, ...program.english } : program;
      const links = (program.links || [])
        .map(
          (link) =>
            `<a href="${escapeAttr(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(isEnglish ? link.label_en || link.label : link.label)}</a>`,
        )
        .join("");
      return `
        <article class="grant-card grant-card--${escapeAttr(program.status || "unknown")}" lang="${isEnglish ? "en" : "zh-Hant"}">
          <div class="grant-heading">
            <div>
              <span class="grant-status">${escapeHtml(view.status_label || (isEnglish ? "Pending verification" : "待確認"))}</span>
              <p>${escapeHtml(view.provider || "")}</p>
              <h3>${escapeHtml(view.title)}</h3>
            </div>
          </div>
          <p class="grant-summary">${escapeHtml(view.summary || "")}</p>
          ${view.priority_note ? `<p class="grant-priority-note">${escapeHtml(view.priority_note)}</p>` : ""}
          <div class="grant-detail-grid">
            ${renderGrantSection(labels.eligibility, view.eligibility)}
            ${renderGrantSection(labels.funding, view.funding)}
            ${renderGrantSection(labels.deadline, view.deadline)}
            ${renderGrantSection(labels.documents, view.documents)}
          </div>
          ${renderGrantSection(labels.steps, view.steps, true)}
          ${renderGrantSection(labels.cautions, view.cautions)}
          ${links ? `<div class="grant-links">${links}</div>` : ""}
        </article>
      `;
    })
    .join("");
}

function grantDeadlineDates(eventDate) {
  const match = String(eventDate || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const eventUtc = Date.UTC(year, month - 1, day);
  if (Number.isNaN(eventUtc)) return null;
  const institutionDeadline = new Date(Date.UTC(year, month - 2, 1)).toISOString().slice(0, 10);
  const acceptanceDeadline = new Date(eventUtc - 28 * 86400000).toISOString().slice(0, 10);
  return { institutionDeadline, acceptanceDeadline };
}

function checkGrantEligibility(event) {
  event.preventDefault();
  const isEnglish = state.grantLanguage === "en";
  const message = (zh, en) => isEnglish ? en : `${zh}／${en}`;
  const blockers = [];
  const followUps = [];
  if (!['master', 'doctoral'].includes(els.eligibilityEnrollment.value)) {
    blockers.push(message("須為在學碩士生或博士生", "Must be an enrolled master's or doctoral student."));
  }
  if (els.eligibilityInService.value === "yes") {
    blockers.push(message("在職專班不屬本補助資格", "In-service programs are not eligible."));
  }
  if (els.eligibilityConferenceScope.value === "domestic") {
    blockers.push(message("須為國際學術會議；僅國內性會議不符", "The event must be an international academic conference."));
  } else if (els.eligibilityConferenceScope.value === "unknown") {
    followUps.push(message("請向主辦單位確認會議是否具有國際學術會議性質", "Confirm the conference's international academic status."));
  }
  if (els.eligibilityPaper.value !== "first_time") {
    blockers.push(message("須發表首次發表的研究論文", "You must present a paper being presented for the first time."));
  }
  if (els.eligibilityFundedThisYear.value === "yes") {
    blockers.push(message("每位研究生每年度以補助一次為限", "Only one grant per student per calendar year is allowed."));
  }
  if (els.eligibilityCoauthor.value === "yes") {
    blockers.push(message("同一篇合著論文僅補助一位研究生", "Only one student may be funded for the same co-authored paper."));
  } else if (els.eligibilityCoauthor.value === "unknown") {
    followUps.push(message("請確認同篇合著論文是否已有其他研究生申請", "Check whether another co-author has applied for the same paper."));
  }
  if (els.eligibilityAcceptance.value === "pending") {
    followUps.push(message("接受函可註明補送，但須在會議首日四週前送達國科會", "Submit the pending acceptance letter at least four weeks before the conference."));
  } else if (els.eligibilityAcceptance.value === "none") {
    blockers.push(message("尚未投稿時無法完成本補助申請", "A grant application cannot be completed before the paper is submitted."));
  }

  const deadlineDates = grantDeadlineDates(els.eligibilityEventDate.value);
  const resultStatus = blockers.length ? "ineligible" : followUps.length ? "conditional" : "eligible";
  const headings = isEnglish
    ? { eligible: "Likely eligible", conditional: "Potentially eligible; follow-up required", ineligible: "Eligibility issues found" }
    : { eligible: "初步符合申請條件／Likely eligible", conditional: "可能符合，但仍有項目待確認／Potentially eligible; follow-up required", ineligible: "目前有不符合項目／Eligibility issues found" };
  const deadlineHtml = deadlineDates
    ? `<div class="eligibility-deadlines">
        <strong>${isEnglish ? "Estimated deadlines" : "期限試算／Estimated deadlines"}</strong>
        <span>${isEnglish ? "Latest NFU-to-NSTC forwarding baseline: " : "虎科大對國科會最遲彙送基準："}${deadlineDates.institutionDeadline}</span>
        <span>${isEnglish ? "Acceptance-letter supplement baseline: " : "接受函最遲補件基準："}${deadlineDates.acceptanceDeadline}</span>
        <small>${isEnglish ? "NFU's internal deadline is usually earlier. Confirm it with the R&D Office before applying." : "虎科大校內截止日通常會更早，申請前務必向研發處確認。"}</small>
      </div>`
    : "";
  els.eligibilityResult.className = `eligibility-result eligibility-result--${resultStatus}`;
  els.eligibilityResult.innerHTML = `
    <h4>${headings[resultStatus]}</h4>
    ${blockers.length ? `<ul>${blockers.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
    ${followUps.length ? `<ul>${followUps.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}
    ${deadlineHtml}
    <p>${isEnglish ? "This is a preliminary check only. Formal eligibility, internal deadlines, and funding amounts remain subject to NFU and NSTC review." : "此結果僅供初篩，正式資格、校內期限與補助額度仍以虎科大及國科會審查為準。"}</p>
  `;
  els.eligibilityResult.hidden = false;
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

function hydrateDashboardYearFilter() {
  if (!els.dashboardYear) return;
  const verified = state.conferences.filter((item) => item.review_status !== "candidate");
  const years = [...new Set(
    verified.flatMap((item) => [item.event_start, item.submission_deadline])
      .filter(Boolean)
      .map((value) => String(value).slice(0, 4))
      .filter((value) => /^\d{4}$/.test(value)),
  )].sort((a, b) => b.localeCompare(a));
  const referenceYear = String(state.referenceDate.getFullYear());
  if (!years.includes(referenceYear)) years.unshift(referenceYear);
  els.dashboardYear.innerHTML = years.map((year) => `<option value="${escapeAttr(year)}">${escapeHtml(year)} 年</option>`).join("");
  els.dashboardYear.value = referenceYear;
}

function renderHealth(payload) {
  const generated = parseGeneratedDate(payload.generated_at);
  const ageDays = Math.floor((today - generated) / 86400000);
  const errorCount = payload.health?.source_error_count ?? (payload.errors || []).length;
  const linkErrorCount = payload.health?.link_error_count ?? 0;
  const messages = [];
  if (errorCount > 0) messages.push(`${errorCount} 個來源檢查失敗，部分資料沿用前次成功結果。`);
  if (linkErrorCount > 0) messages.push(`${linkErrorCount} 個連結連續檢查失敗，已標示為可能失效。`);
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

function openRatingDialog(button) {
  ratingTarget = {
    id: button.dataset.ratingId,
    title: button.dataset.ratingTitle,
  };
  els.ratingConferenceTitle.textContent = ratingTarget.title;
  els.ratingForm.reset();
  if (els.ratingStatus) {
    els.ratingStatus.hidden = true;
    els.ratingStatus.textContent = "";
    els.ratingStatus.removeAttribute("data-status");
  }
  els.ratingDialog.showModal();
}

function buildRatingIssueUrl(payload) {
  const singleLine = (value) => String(value || "").replace(/[\r\n]+/g, " ").trim();
  const body = [
    `conference_id: ${singleLine(payload.conference_id)}`,
    `conference_title: ${singleLine(payload.conference_title)}`,
    `rating: ${payload.rating}`,
    `participation: ${payload.participation}`,
    "confirmed: true",
    "",
    "comment:",
    payload.comment.trim(),
  ].join("\n");
  const params = new URLSearchParams({
    title: `[研討會評分] ${payload.conference_id} ${payload.conference_title}`,
    body,
  });
  return `https://github.com/ftsainfu/twconferences/issues/new?${params}`;
}

async function submitRating(event) {
  event.preventDefault();
  if (!ratingTarget || !els.ratingConfirmed.checked) return;
  const rating = new FormData(els.ratingForm).get("rating");
  if (!rating) return;
  const submitButton = els.ratingForm.querySelector('button[type="submit"]');
  const payload = {
    conference_id: ratingTarget.id,
    conference_title: ratingTarget.title,
    rating: Number(rating),
    participation: els.ratingParticipation.value,
    confirmed: true,
    nickname: els.ratingNickname?.value.trim() || "",
    comment: els.ratingComment.value.trim(),
    voter_id: loadVoterId(),
    source: "twconferences-site",
    submitted_at: new Date().toISOString(),
  };
  const apiUrl = String(state.siteConfig.rating_api_url || "").trim();
  const fallback = state.siteConfig.rating_fallback !== "none";
  if (submitButton) submitButton.disabled = true;
  if (els.ratingStatus) {
    els.ratingStatus.hidden = false;
    els.ratingStatus.textContent = apiUrl ? "評分送出中…" : "此網站尚未設定免登入評分 API，將開啟 GitHub 備援表單。";
    els.ratingStatus.removeAttribute("data-status");
  }
  try {
    if (apiUrl) {
      const apiMode = state.siteConfig.rating_api_mode === "no-cors" ? "no-cors" : "cors";
      const response = await fetch(apiUrl, {
        method: "POST",
        mode: apiMode,
        headers: { "Content-Type": "text/plain;charset=utf-8" },
        body: JSON.stringify(payload),
      });
      if (apiMode !== "no-cors" && !response.ok) throw new Error(`Rating API returned ${response.status}`);
      if (els.ratingStatus) {
        els.ratingStatus.textContent = "評分已送出，系統會在下一次彙整後更新推薦分數。";
      }
      window.setTimeout(() => els.ratingDialog.close(), 700);
      return;
    }
    if (!fallback) throw new Error("Rating API is not configured");
    window.open(buildRatingIssueUrl(payload), "_blank", "noopener,noreferrer");
    els.ratingDialog.close();
  } catch (error) {
    if (!fallback) {
      if (els.ratingStatus) {
        els.ratingStatus.hidden = false;
        els.ratingStatus.dataset.status = "error";
        els.ratingStatus.textContent = "評分暫時無法送出，請稍後再試。";
      }
      return;
    }
    if (els.ratingStatus) {
      els.ratingStatus.dataset.status = "error";
      els.ratingStatus.textContent = "免登入評分暫時失敗，已改用 GitHub 備援表單。";
    }
    window.open(buildRatingIssueUrl(payload), "_blank", "noopener,noreferrer");
    els.ratingDialog.close();
    console.warn(error);
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
}

function bindEvents() {
  els.dashboardYear?.addEventListener("change", renderMonthlyDashboard);
  els.dashboardScope?.addEventListener("change", renderMonthlyDashboard);
  els.grantLanguageButtons.forEach((button) => {
    button.addEventListener("click", () => {
      state.grantLanguage = button.dataset.grantLanguage === "en" ? "en" : "zh";
      renderGrants();
    });
  });
  els.tabButtons.forEach((button) => {
    button.addEventListener("click", () => setActiveTab(button.dataset.tab));
    button.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
      event.preventDefault();
      const nextName = button.dataset.tab === "grants" ? "conferences" : "grants";
      setActiveTab(nextName);
      els.tabButtons.find((item) => item.dataset.tab === nextName)?.focus();
    });
  });
  document.querySelectorAll("[data-open-tab]").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      setActiveTab(link.dataset.openTab);
      els.pageTabs?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
  window.addEventListener("hashchange", () => {
    setActiveTab(window.location.hash === "#grants" ? "grants" : "conferences", false);
  });
  [els.keyword, els.field, els.month, els.location, els.eventStatus, els.deadlineBefore, els.deadlineStatus, els.format, els.englishPresentation, els.trackedOnly, els.sort].forEach((input) => {
    if (!input) return;
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
    if (els.trackedOnly) els.trackedOnly.checked = false;
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
    const ratingButton = event.target.closest("[data-rating-id]");
    if (ratingButton) openRatingDialog(ratingButton);
    const trackButton = event.target.closest("[data-track-id]");
    if (trackButton) toggleTracked(trackButton.dataset.trackId);
  });
  els.closeReportDialog.addEventListener("click", () => els.reportDialog.close());
  els.reportForm.addEventListener("submit", submitReport);
  els.closeRatingDialog.addEventListener("click", () => els.ratingDialog.close());
  els.ratingForm.addEventListener("submit", submitRating);
  els.eligibilityChecker?.addEventListener("submit", checkGrantEligibility);
}

async function init() {
  const [response, recurringResponse, ratingsResponse, grantsResponse, siteConfigResponse] = await Promise.all([
    fetch("data/conferences.json", { cache: "no-store" }),
    fetch("data/recurring.json", { cache: "no-store" }),
    fetch("data/ratings.json", { cache: "no-store" }),
    fetch("data/grants.json", { cache: "no-store" }),
    fetch("data/site_config.json", { cache: "no-store" }),
  ]);
  if (!response.ok) throw new Error("Failed to load conference data");
  const payload = await response.json();
  const recurringPayload = recurringResponse.ok ? await recurringResponse.json() : { recurring_conferences: [] };
  const ratingsPayload = ratingsResponse.ok ? await ratingsResponse.json() : { ratings: {} };
  const grantsPayload = grantsResponse.ok ? await grantsResponse.json() : { programs: [], notice: "獎補助資料目前無法讀取。" };
  const siteConfigPayload = siteConfigResponse.ok ? await siteConfigResponse.json() : {};
  state.conferences = payload.conferences || [];
  state.trackedIds = loadTrackedIds();
  state.referenceDate = parseGeneratedDate(payload.generated_at);
  const verified = state.conferences.filter((item) => item.review_status !== "candidate");
  state.candidates = state.conferences.filter((item) => item.review_status === "candidate");
  state.activeConferences = verified.filter((item) => eventStatus(item) !== "past");
  state.pastConferences = verified.filter((item) => eventStatus(item) === "past");
  state.recurring = recurringPayload.recurring_conferences || [];
  state.ratings = ratingsPayload.ratings || {};
  state.siteConfig = { ...state.siteConfig, ...siteConfigPayload };
  renderGrants(grantsPayload);
  els.lastUpdated.textContent = payload.generated_at || "未產生";
  els.sourceCount.textContent = `${payload.source_count || state.conferences.length} 個來源`;
  renderHealth(payload);
  hydrateLocationFilter();
  hydrateHistoryYearFilter();
  hydrateDashboardYearFilter();
  bindEvents();
  const initialTab = window.location.hash === "#grants" ? "grants" : "conferences";
  setActiveTab(initialTab, false);
  if (initialTab === "grants") {
    window.requestAnimationFrame(() => els.pageTabs?.scrollIntoView({ block: "start" }));
  }
  applyFilters();
}

init().catch((error) => {
  els.lastUpdated.textContent = "資料讀取失敗";
  els.sourceCount.textContent = error.message;
});
