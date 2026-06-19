#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import urllib.error
import urllib.parse
from datetime import date, datetime, timezone
from pathlib import Path

try:
    from .update_conferences import DATA_DIR, LINK_RE, OUTPUT_FILE, domain_key, fetch_url, normalize_text, normalize_url, now_tw, read_json, today_iso, validate_url, write_json
except ImportError:
    from update_conferences import DATA_DIR, LINK_RE, OUTPUT_FILE, domain_key, fetch_url, normalize_text, normalize_url, now_tw, read_json, today_iso, validate_url, write_json

SOURCES_FILE = DATA_DIR / "sources.json"
CANDIDATES_FILE = DATA_DIR / "candidates.json"
REPORTS_DIR = DATA_DIR / "reports"
ALLOWED_FIELDS = {
    "homepage_url",
    "submission_url",
    "registration_url",
    "event_start",
    "event_end",
    "submission_deadline",
    "submission_fee",
    "registration_fee",
    "location",
}
URL_FIELDS = {"homepage_url", "submission_url", "registration_url"}
DATE_FIELDS = {"event_start", "event_end", "submission_deadline"}
FEE_FIELDS = {"submission_fee", "registration_fee"}
TRUSTED_SUFFIXES = (".edu.tw", ".org.tw", ".gov.tw", ".com.tw")
FIELD_HINTS = {
    "registration_url": ("報名連結", "報名網址", "註冊連結", "註冊網址", "registration", "register"),
    "submission_url": ("投稿連結", "投稿網址", "繳交論文", "submission", "submit paper"),
    "homepage_url": ("官網", "首頁", "主頁", "homepage", "official website"),
}
LINK_HINTS = {
    "registration_url": ("registration", "register", "報名", "註冊"),
    "submission_url": ("submission", "submit", "投稿", "paper submission"),
    "homepage_url": ("home", "homepage", "首頁", "官網"),
}
COMMON_OFFICIAL_PATHS = {
    "registration_url": ("registration", "register"),
    "submission_url": ("submission", "submit"),
    "homepage_url": ("",),
}


def parse_report(body: str) -> dict[str, str]:
    values: dict[str, str] = {}
    details: list[str] = []
    in_details = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line == "details:":
            in_details = True
            continue
        if in_details:
            details.append(raw_line.strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    values["details"] = "\n".join(details).strip()
    return values


def find_record(conference_id: str, sources: dict, candidates: dict) -> tuple[dict | None, str]:
    for item in sources.get("conferences", []):
        if item.get("id") == conference_id:
            return item, "sources"
    for item in candidates.get("candidates", []):
        if item.get("id") == conference_id:
            return item, "candidates"
    return None, ""


def infer_correction_field(report: dict[str, str]) -> str:
    field = report.get("correction_field", "")
    if field in ALLOWED_FIELDS:
        return field
    details = report.get("details", "").lower()
    matches = [name for name, hints in FIELD_HINTS.items() if any(hint.lower() in details for hint in hints)]
    return matches[0] if len(matches) == 1 else ""


def discover_official_url_correction(record: dict, field: str) -> tuple[str, str]:
    if field not in LINK_HINTS:
        return "", "回報內容無法判斷需要修正的網址欄位。"

    homepage = str(record.get("homepage_url") or "")
    if not validate_url(homepage):
        return "", "目前資料沒有可供搜尋的官方網站。"
    parsed_homepage = urllib.parse.urlparse(homepage)
    root_url = urllib.parse.urlunparse((parsed_homepage.scheme, parsed_homepage.netloc, "/", "", "", ""))
    current_value = str(record.get(field) or "")
    candidates: dict[str, int] = {}

    # Check conventional official paths first. This resolves common conference
    # sites quickly even when navigation links are rendered only by JavaScript.
    for path in COMMON_OFFICIAL_PATHS[field]:
        link = urllib.parse.urljoin(root_url, path)
        if link == current_value:
            continue
        try:
            raw, _ = fetch_url(link, timeout=8, attempts=1)
        except (urllib.error.URLError, TimeoutError):
            continue
        page_text = normalize_text(raw).lower()
        if any(hint in page_text or hint in link.lower() for hint in LINK_HINTS[field]):
            return link, "已從同一官方網域找到並驗證對應連結。"

    for seed_url in dict.fromkeys((homepage, root_url)):
        try:
            raw, _ = fetch_url(seed_url, timeout=8, attempts=1)
        except (urllib.error.URLError, TimeoutError):
            continue
        for match in LINK_RE.finditer(raw):
            link = normalize_url(seed_url, match.group("href"))
            if not link or link == current_value or domain_key(link) != domain_key(homepage):
                continue
            label = normalize_text(match.group("label")).lower()
            search_text = f"{label} {urllib.parse.urlparse(link).path.lower()}"
            score = sum(3 if hint in label else 1 for hint in LINK_HINTS[field] if hint in search_text)
            if score:
                candidates[link] = max(score, candidates.get(link, 0))

    ranked = sorted(candidates.items(), key=lambda item: (-item[1], len(item[0]), item[0]))
    for link, _score in ranked[:5]:
        try:
            raw, _ = fetch_url(link, timeout=8, attempts=1)
        except (urllib.error.URLError, TimeoutError):
            continue
        page_text = normalize_text(raw).lower()
        if any(hint in page_text or hint in link.lower() for hint in LINK_HINTS[field]):
            return link, "已從同一官方網域找到並驗證對應連結。"
    return "", "官方網站中找不到可唯一驗證的對應連結。"


def trusted_correction_url(value: str, evidence_url: str, current_url: str) -> bool:
    if not validate_url(value):
        return False
    host = urllib.parse.urlparse(value).hostname or ""
    evidence_host = urllib.parse.urlparse(evidence_url).hostname or ""
    return (
        host == "sites.google.com"
        or host.endswith(TRUSTED_SUFFIXES)
        or domain_key(value) == domain_key(current_url)
        or (evidence_host and domain_key(value) == domain_key(evidence_url))
    )


def date_variants(value: str) -> list[str]:
    parsed = date.fromisoformat(value)
    roc = parsed.year - 1911
    return [
        value,
        f"{parsed.year}/{parsed.month:02d}/{parsed.day:02d}",
        f"{parsed.year}年{parsed.month}月{parsed.day}日",
        f"{roc}年{parsed.month}月{parsed.day}日",
    ]


def validate_correction(record: dict, field: str, value: str, evidence_url: str) -> tuple[bool, str]:
    if field not in ALLOWED_FIELDS or not value:
        return False, "未提供可自動修正的欄位與內容。"
    if field in URL_FIELDS:
        if not trusted_correction_url(value, evidence_url, record.get(field) or record.get("homepage_url", "")):
            return False, "建議網址不是可辨識的官方網域。"
        try:
            fetch_url(value, timeout=12, attempts=2)
        except (urllib.error.URLError, TimeoutError):
            return False, "建議網址目前無法連線。"
        return True, "建議網址可連線且符合官方網域規則。"
    if field in DATE_FIELDS:
        try:
            variants = date_variants(value)
        except ValueError:
            return False, "日期必須使用 YYYY-MM-DD 格式。"
        if not validate_url(evidence_url):
            return False, "日期修正需要主辦單位佐證網址。"
        try:
            raw, _ = fetch_url(evidence_url, timeout=12, attempts=2)
        except (urllib.error.URLError, TimeoutError):
            return False, "佐證網址目前無法連線。"
        text = re.sub(r"\s+", "", normalize_text(raw))
        if not any(re.sub(r"\s+", "", variant) in text for variant in variants):
            return False, "佐證頁面中找不到建議日期。"
        return True, "建議日期可在佐證頁面中找到。"
    if field == "location":
        if len(value) > 80 or not validate_url(evidence_url):
            return False, "地點修正需要 80 字內內容與主辦單位佐證網址。"
        try:
            raw, _ = fetch_url(evidence_url, timeout=12, attempts=2)
        except (urllib.error.URLError, TimeoutError):
            return False, "佐證網址目前無法連線。"
        if value.lower() not in normalize_text(raw).lower():
            return False, "佐證頁面中找不到建議地點。"
        return True, "建議地點可在佐證頁面中找到。"
    if field in FEE_FIELDS:
        if len(value) > 240 or not validate_url(evidence_url):
            return False, "費用修正需要 240 字內內容與主辦單位佐證網址。"
        try:
            raw, _ = fetch_url(evidence_url, timeout=12, attempts=2)
        except (urllib.error.URLError, TimeoutError):
            return False, "佐證網址目前無法連線。"
        page_text = re.sub(r"\s+", "", normalize_text(raw)).lower()
        if re.sub(r"\s+", "", value).lower() not in page_text:
            return False, "佐證頁面中找不到建議費用文字。"
        return True, "建議費用可在佐證頁面中找到。"
    return False, "此欄位不能自動修正。"


def process_event(event: dict) -> tuple[bool, bool, str]:
    issue = event.get("issue", {})
    title = str(issue.get("title") or "")
    if not title.startswith("[資料回報]"):
        return False, False, "不是研討會資料回報。"

    report = parse_report(str(issue.get("body") or ""))
    conference_id = report.get("conference_id", "")
    sources = read_json(SOURCES_FILE, {"conferences": []})
    candidates = read_json(CANDIDATES_FILE, {"candidates": []})
    record, record_file = find_record(conference_id, sources, candidates)
    correction_applied = False
    verification = "找不到對應的研討會 ID，需人工處理。"

    if record:
        field = infer_correction_field(report)
        value = report.get("correction_value", "")
        discovery_note = ""
        if field in URL_FIELDS and not value:
            value, discovery_note = discover_official_url_correction(record, field)
            if value:
                report["correction_field"] = field
                report["correction_value"] = value
                report["evidence_url"] = value
        valid, verification = validate_correction(record, field, value, report.get("evidence_url", ""))
        if discovery_note and not valid:
            verification = discovery_note
        elif discovery_note and valid:
            verification = f"{discovery_note} {verification}"
        if valid:
            old_value = str(record.get(field, ""))
            record[field] = value
            record["last_user_report"] = today_iso()
            record["last_changed"] = today_iso()
            record["attention_notes"] = list(record.get("attention_notes") or []) + [
                f"使用者回報後建議修正 {field}：{old_value or '未填'} → {value}；待 PR 審核。"
            ]
            correction_applied = True
        elif report.get("report_type") == "broken_link" and not value:
            try:
                fetch_url(record.get("homepage_url", ""), timeout=10, attempts=3)
                verification = "原連結目前可連線，未自動標記失效。"
            except (urllib.error.URLError, TimeoutError):
                record["link_status"] = "reported_broken"
                record["last_user_report"] = today_iso()
                verification = "原連結經三次檢查仍無法連線，已建議標示失效。"
                correction_applied = True

    report_record = {
        "issue_number": issue.get("number"),
        "issue_url": issue.get("html_url", ""),
        "reported_at": datetime.now(timezone.utc).isoformat(),
        "conference_id": conference_id,
        "report_type": report.get("report_type", ""),
        "details": report.get("details", "")[:1000],
        "correction_field": report.get("correction_field", ""),
        "correction_value": report.get("correction_value", "")[:500],
        "evidence_url": report.get("evidence_url", "")[:500],
        "auto_correction_applied": correction_applied,
        "verification": verification,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    write_json(REPORTS_DIR / f"issue-{issue.get('number')}.json", report_record)
    if correction_applied and record_file == "sources":
        write_json(SOURCES_FILE, sources)
    elif correction_applied and record_file == "candidates":
        write_json(CANDIDATES_FILE, candidates)
    if correction_applied:
        generated = read_json(OUTPUT_FILE, {"conferences": []})
        generated["generated_at"] = now_tw().strftime("%Y-%m-%d %H:%M:%S %Z")
        for item in generated.get("conferences", []):
            if item.get("id") != conference_id:
                continue
            for key in ALLOWED_FIELDS | {"attention_notes", "last_user_report", "last_changed", "link_status"}:
                if key in record:
                    item[key] = record[key]
            break
        write_json(OUTPUT_FILE, generated)

    summary = "\n".join(
        [
            f"研討會回報 #{issue.get('number', '')}",
            f"研討會：{report.get('conference_title') or conference_id}",
            f"類型：{report.get('report_type', '')}",
            f"說明：{report.get('details', '')}",
            f"建議修正：{report.get('correction_field', '')} = {report.get('correction_value', '')}",
            f"驗證結果：{verification}",
            f"自動修正：{'已建立建議變更' if correction_applied else '未套用，等待人工確認'}",
            f"原始回報：{issue.get('html_url', '')}",
        ]
    )
    return True, correction_applied, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    handled, applied, summary = process_event(event)
    args.summary.write_text(summary + "\n", encoding="utf-8")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"handled={'true' if handled else 'false'}\n")
            handle.write(f"applied={'true' if applied else 'false'}\n")
    print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
