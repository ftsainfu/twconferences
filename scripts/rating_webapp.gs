const SHEET_NAME = "ratings";
const HEADERS = [
  "created_at",
  "conference_id",
  "conference_title",
  "rating",
  "participation",
  "confirmed",
  "nickname",
  "comment",
  "voter_id",
  "source",
  "submitted_at",
];

function jsonResponse(payload) {
  return ContentService
    .createTextOutput(JSON.stringify(payload))
    .setMimeType(ContentService.MimeType.JSON);
}

function getSheet() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = spreadsheet.getSheetByName(SHEET_NAME);
  if (!sheet) sheet = spreadsheet.insertSheet(SHEET_NAME);
  const currentHeaders = sheet.getRange(1, 1, 1, HEADERS.length).getValues()[0];
  if (currentHeaders.join("|") !== HEADERS.join("|")) {
    sheet.getRange(1, 1, 1, HEADERS.length).setValues([HEADERS]);
  }
  return sheet;
}

function validatePayload(payload) {
  const rating = Number(payload.rating);
  const participation = String(payload.participation || "");
  if (!payload.conference_id) throw new Error("conference_id is required");
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) throw new Error("rating must be 1-5");
  if (!["registered", "attended"].includes(participation)) throw new Error("participation is invalid");
  if (String(payload.confirmed).toLowerCase() !== "true") throw new Error("confirmed must be true");
  if (!payload.voter_id) throw new Error("voter_id is required");
}

function doPost(e) {
  try {
    const payload = JSON.parse(e.postData.contents || "{}");
    validatePayload(payload);
    const sheet = getSheet();
    sheet.appendRow([
      new Date().toISOString(),
      String(payload.conference_id || "").slice(0, 120),
      String(payload.conference_title || "").slice(0, 300),
      Number(payload.rating),
      String(payload.participation || ""),
      true,
      String(payload.nickname || "").slice(0, 80),
      String(payload.comment || "").slice(0, 500),
      String(payload.voter_id || "").slice(0, 120),
      String(payload.source || "twconferences-site").slice(0, 80),
      String(payload.submitted_at || ""),
    ]);
    return jsonResponse({ ok: true });
  } catch (error) {
    return jsonResponse({ ok: false, error: String(error.message || error) });
  }
}

function doGet(e) {
  const token = PropertiesService.getScriptProperties().getProperty("READ_TOKEN");
  if (!token || e.parameter.token !== token) {
    return jsonResponse({ ok: false, error: "unauthorized" });
  }
  const sheet = getSheet();
  const values = sheet.getDataRange().getValues();
  const headers = values.shift() || [];
  const ratings = values
    .filter((row) => row.some((cell) => cell !== ""))
    .map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index]])));
  return jsonResponse({ ok: true, ratings });
}
