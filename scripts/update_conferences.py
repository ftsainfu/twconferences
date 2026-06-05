#!/usr/bin/env python3
from __future__ import annotations

import email.utils
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCES_FILE = DATA_DIR / "sources.json"
OUTPUT_FILE = DATA_DIR / "conferences.json"
HISTORY_FILE = DATA_DIR / "history.json"
TZ = timezone(timedelta(hours=8))

KEYWORDS = ("商管", "管理", "行銷", "財務", "財金", "國貿", "企業", "服務創新", "經營")
CONFERENCE_WORDS = ("研討會", "學術研討", "徵稿", "論文")


def now_tw() -> datetime:
    return datetime.now(TZ)


def today_iso() -> str:
    return now_tw().date().isoformat()


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_url(url: str, timeout: int = 18) -> tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "twconferences-bot/1.0 (+https://github.com/)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get_content_charset() or "utf-8"
        body = response.read()
    return body.decode(content_type, errors="replace"), content_type


def normalize_text(raw: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def roc_to_iso(match: re.Match[str]) -> str:
    year = int(match.group("year"))
    if year < 1911:
        year += 1911
    month = int(match.group("month"))
    day = int(match.group("day"))
    return f"{year:04d}-{month:02d}-{day:02d}"


DATE_PATTERNS = [
    re.compile(r"(?P<year>20\d{2})[年/-]\s*(?P<month>\d{1,2})[月/-]\s*(?P<day>\d{1,2})"),
    re.compile(r"(?P<year>1\d{2})[年/-]\s*(?P<month>\d{1,2})[月/-]\s*(?P<day>\d{1,2})"),
]


def find_dates(text: str) -> list[str]:
    dates: list[str] = []
    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            try:
                dates.append(roc_to_iso(match))
            except ValueError:
                continue
    return sorted(set(dates))


def infer_deadline(text: str, fallback: str) -> str:
    if fallback:
        return fallback
    window_matches = re.finditer(r"(投稿|截稿|摘要|全文|收件|繳交).{0,30}", text)
    candidates: list[str] = []
    for match in window_matches:
        snippet = text[match.start() : min(len(text), match.end() + 30)]
        candidates.extend(find_dates(snippet))
    return sorted(set(candidates))[0] if candidates else fallback


def infer_event_date(text: str, fallback: str) -> str:
    if fallback:
        return fallback
    window_matches = re.finditer(r"(研討會日期|會議日期|會議時間|舉辦日期).{0,40}", text)
    candidates: list[str] = []
    for match in window_matches:
        snippet = text[match.start() : min(len(text), match.end() + 40)]
        candidates.extend(find_dates(snippet))
    return sorted(set(candidates))[0] if candidates else fallback


def infer_formats(text: str, fallback: list[str]) -> list[str]:
    formats = set(fallback)
    if "口頭" in text or "oral" in text.lower():
        formats.add("oral")
    if "海報" in text or "poster" in text.lower():
        formats.add("poster")
    if "線上" in text or "online" in text.lower():
        formats.add("online")
    return sorted(formats) if formats else ["other"]


def update_known_conferences(sources: dict, history: dict) -> tuple[list[dict], list[str]]:
    conferences: list[dict] = []
    errors: list[str] = []
    history_sources = history.setdefault("sources", {})

    for source in sources.get("conferences", []):
        item = dict(source)
        source_id = item["id"]
        previous = history_sources.get(source_id, {})
        text = ""
        current_hash = ""
        change_status = "unchanged"
        change_summary = ""

        try:
            raw, _ = fetch_url(item["homepage_url"])
            text = normalize_text(raw)
            current_hash = content_hash(text)
            if not previous:
                change_status = "new"
                change_summary = "首次納入追蹤。"
            elif previous.get("hash") != current_hash:
                change_status = "changed"
                change_summary = "來源頁面內容有異動，請檢查主辦單位最新公告。"

            item["submission_deadline"] = infer_deadline(text, item.get("submission_deadline", ""))
            item["event_start"] = infer_event_date(text, item.get("event_start", ""))
            item["presentation_formats"] = infer_formats(text, item.get("presentation_formats", []))
            history_sources[source_id] = {
                "hash": current_hash,
                "last_checked": today_iso(),
                "last_changed": today_iso() if change_status in {"new", "changed"} else previous.get("last_changed", ""),
                "url": item["homepage_url"],
            }
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
            errors.append(f"{source_id}: {exc}")
            if not previous:
                change_status = "new"
                change_summary = "首次納入追蹤；本次來源自動檢查失敗，保留人工確認資料。"
                history_sources[source_id] = {
                    "hash": "",
                    "last_checked": today_iso(),
                    "last_changed": today_iso(),
                    "url": item["homepage_url"],
                }
            else:
                change_status = previous.get("last_status", "unchanged")
                change_summary = "本次來源檢查失敗，保留前次資料。"

        item["last_checked"] = today_iso()
        item["last_changed"] = history_sources.get(source_id, previous).get("last_changed", "")
        item["change_status"] = change_status
        item["change_label"] = {"new": "新增", "changed": "資訊異動", "unchanged": "已檢查"}.get(change_status, "已檢查")
        item["change_summary"] = change_summary
        item["review_status"] = "verified"
        conferences.append(item)

    return conferences, errors


def unwrap_google_news_link(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.endswith("google.com") and parsed.path.startswith("/rss/articles/"):
        return url
    return url


def parse_rss_date(value: str) -> str:
    if not value:
        return today_iso()
    try:
        return email.utils.parsedate_to_datetime(value).astimezone(TZ).date().isoformat()
    except (TypeError, ValueError):
        return today_iso()


def discover_candidates(feeds: list[str], existing_ids: set[str]) -> list[dict]:
    candidates: list[dict] = []
    seen_urls: set[str] = set()
    for feed_url in feeds:
        try:
            raw, _ = fetch_url(feed_url, timeout=12)
            root = ET.fromstring(raw)
        except (urllib.error.URLError, TimeoutError, ET.ParseError):
            continue

        for node in root.findall(".//item"):
            title = html.unescape(node.findtext("title") or "").strip()
            link = unwrap_google_news_link((node.findtext("link") or "").strip())
            published = parse_rss_date(node.findtext("pubDate") or "")
            text = f"{title} {node.findtext('description') or ''}"
            if not link or link in seen_urls:
                continue
            if not any(word in text for word in KEYWORDS) or not any(word in text for word in CONFERENCE_WORDS):
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", urllib.parse.urlparse(link).netloc.lower()).strip("-")
            candidate_id = f"candidate-{slug}-{hashlib.sha1(link.encode('utf-8')).hexdigest()[:8]}"
            if candidate_id in existing_ids:
                continue
            seen_urls.add(link)
            candidates.append(
                {
                    "id": candidate_id,
                    "title": title,
                    "organizer": "待確認",
                    "homepage_url": link,
                    "submission_url": link,
                    "registration_url": "",
                    "event_start": "",
                    "event_end": "",
                    "location": "待確認",
                    "submission_deadline": "",
                    "fields": ["待確認"],
                    "presentation_formats": ["other"],
                    "attention_notes": ["由每日搜尋發現，尚待人工確認主辦單位、日期、投稿與發表形式。"],
                    "last_checked": today_iso(),
                    "last_changed": published,
                    "change_status": "new",
                    "change_label": "候選新增",
                    "change_summary": "搜尋來源發現的新候選項目。",
                    "review_status": "candidate",
                }
            )
    return candidates[:12]


def main() -> int:
    sources = read_json(SOURCES_FILE, {"conferences": [], "discovery_feeds": []})
    history = read_json(HISTORY_FILE, {"sources": {}})
    conferences, errors = update_known_conferences(sources, history)
    candidates = discover_candidates(sources.get("discovery_feeds", []), {item["id"] for item in conferences})
    payload = {
        "generated_at": now_tw().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "source_count": len(sources.get("conferences", [])) + len(sources.get("discovery_feeds", [])),
        "errors": errors,
        "conferences": conferences + candidates,
    }
    write_json(OUTPUT_FILE, payload)
    write_json(HISTORY_FILE, history)
    if errors:
        print("Completed with source errors:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    print(f"Wrote {len(payload['conferences'])} conferences to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
