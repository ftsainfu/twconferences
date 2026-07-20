const REPORT_SHEET_NAME = "reports";
const REPORT_HEADERS = [
  "created_at",
  "conference_id",
  "conference_title",
  "current_url",
  "current_submission_url",
  "current_registration_url",
  "current_event_start",
  "current_submission_deadline",
  "current_acceptance_notification_date",
  "current_submission_fee",
  "current_registration_fee",
  "report_type",
  "correction_field",
  "correction_value",
  "evidence_url",
  "details",
  "reporter_id",
  "opened_after_ms",
  "suspicious",
  "suspicious_reason",
  "source",
  "submitted_at",
];

function reportJsonResponse(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function getReportSheet() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = spreadsheet.getSheetByName(REPORT_SHEET_NAME);
  if (!sheet) sheet = spreadsheet.insertSheet(REPORT_SHEET_NAME);
  const currentHeaders = sheet.getRange(1, 1, 1, REPORT_HEADERS.length).getValues()[0];
  if (currentHeaders.join("|") !== REPORT_HEADERS.join("|")) {
    sheet.getRange(1, 1, 1, REPORT_HEADERS.length).setValues([REPORT_HEADERS]);
  }
  return sheet;
}

function reportSuspicion(payload) {
  const reasons = [];
  if (String(payload.honeypot || "").trim()) reasons.push("honeypot");
  if (Number(payload.opened_after_ms || 0) < 2000) reasons.push("too_fast");
  if (String(payload.details || "").length > 1000) reasons.push("too_long");
  return reasons;
}

function validateReportPayload(payload) {
  if (!payload.conference_id) throw new Error("conference_id is required");
  if (!payload.report_type) throw new Error("report_type is required");
  if (!payload.reporter_id) throw new Error("reporter_id is required");
}

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents || "{}");
    validateReportPayload(payload);
    const suspiciousReasons = reportSuspicion(payload);
    const sheet = getReportSheet();
    sheet.appendRow([
      new Date().toISOString(),
      String(payload.conference_id || "").slice(0, 120),
      String(payload.conference_title || "").slice(0, 300),
      String(payload.current_url || "").slice(0, 500),
      String(payload.current_submission_url || "").slice(0, 500),
      String(payload.current_registration_url || "").slice(0, 500),
      String(payload.current_event_start || "").slice(0, 40),
      String(payload.current_submission_deadline || "").slice(0, 40),
      String(payload.current_acceptance_notification_date || "").slice(0, 40),
      String(payload.current_submission_fee || "").slice(0, 240),
      String(payload.current_registration_fee || "").slice(0, 240),
      String(payload.report_type || "").slice(0, 80),
      String(payload.correction_field || "").slice(0, 80),
      String(payload.correction_value || "").slice(0, 500),
      String(payload.evidence_url || "").slice(0, 500),
      String(payload.details || "").slice(0, 1000),
      String(payload.reporter_id || "").slice(0, 120),
      Number(payload.opened_after_ms || 0),
      suspiciousReasons.length > 0,
      suspiciousReasons.join(","),
      String(payload.source || "twconferences-site").slice(0, 80),
      String(payload.submitted_at || ""),
    ]);
    return reportJsonResponse({ ok: true, suspicious: suspiciousReasons.length > 0 });
  } catch (error) {
    return reportJsonResponse({ ok: false, error: String(error.message || error) });
  }
}

function doGet(e) {
  const token = PropertiesService.getScriptProperties().getProperty("READ_TOKEN");
  if (!token || e.parameter.token !== token) {
    return reportJsonResponse({ ok: false, error: "unauthorized" });
  }
  const sheet = getReportSheet();
  const values = sheet.getDataRange().getValues();
  const headers = values.shift() || [];
  const reports = values
    .filter((row) => row.some((cell) => cell !== ""))
    .map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
  return reportJsonResponse({ ok: true, reports });
}
