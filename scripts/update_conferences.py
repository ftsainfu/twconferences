#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import argparse
import time
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SOURCES_FILE = DATA_DIR / "sources.json"
OUTPUT_FILE = DATA_DIR / "conferences.json"
HISTORY_FILE = DATA_DIR / "history.json"
RECURRING_FILE = DATA_DIR / "recurring.json"
CANDIDATES_FILE = DATA_DIR / "candidates.json"
TZ = timezone(timedelta(hours=8))

KEYWORDS = ("商管", "管理", "行銷", "財務", "財金", "國貿", "企業", "服務創新", "經營")
CONFERENCE_WORDS = ("研討會", "學術研討", "徵稿", "論文", "conference", "symposium")
FORMAL_CONFERENCE_WORDS = ("研討會", "學術研討", "年會", "conference", "symposium")
FOLLOWUP_WORDS = ("議程", "審查", "結果", "論文集", "優秀論文", "得獎", "獲獎", "錄取名單", "公告名單")
NON_CONFERENCE_WORDS = (
    "專刊",
    "學刊",
    "期刊",
    "期末報告",
    "講座",
    "課程",
    "工作坊",
    "營隊",
    "招生",
    "說明會",
    "培育計畫",
    "研習",
    "徵才",
    "獎學金",
)
OFFICIAL_EXTERNAL_HOSTS = {"sites.google.com"}
OFFICIAL_REFERENCE_SUFFIXES = (".edu.tw", ".org.tw", ".gov.tw")
NON_OFFICIAL_REFERENCE_HOSTS = {"forms.gle", "docs.google.com", "forms.office.com"}
TAIWAN_LOCATION_WORDS = ("taiwan", "taipei", "kaohsiung", "taichung", "tainan", "hsinchu", "台灣", "臺灣", "台北", "臺北", "高雄", "台中", "臺中", "台南", "臺南", "新竹")
BUSINESS_REFERENCE_WORDS = ("finance", "financial", "accounting", "management", "business", "marketing", "economics", "財務", "財金", "會計", "管理", "商管", "行銷", "經濟")
LINK_RE = re.compile(r"<a\b[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<label>[\s\S]*?)</a>", re.I)


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


def fetch_url(url: str, timeout: int = 18, attempts: int = 3) -> tuple[str, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "twconferences-bot/1.1 (+https://github.com/ftsainfu/twconferences)",
            "Accept": "text/html,application/xhtml+xml,application/json,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content_type = response.headers.get_content_charset() or "utf-8"
                body = response.read()
            return body.decode(content_type, errors="replace"), content_type
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


def current_year_markers(reference: date | None = None) -> tuple[str, ...]:
    reference = reference or now_tw().date()
    years = (reference.year, reference.year + 1)
    return tuple(str(value) for year in years for value in (year, year - 1911))


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
    return date(year, month, day).isoformat()


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
    window_matches = re.finditer(
        r"(研討會日期|研討會舉辦日期|研討會舉辦日|研討會舉辦|會議日期|會議時間|舉辦日期|舉辦日|活動日期|Conference Date).{0,50}",
        text,
        flags=re.I,
    )
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


def infer_languages(text: str, fallback: list[str]) -> list[str]:
    if fallback:
        return sorted(set(fallback))
    languages = set(fallback)
    lower_text = text.lower()
    if "英文" in text or "英語" in text or "english" in lower_text:
        languages.add("en")
    if "中文" in text or "華語" in text or "chinese" in lower_text:
        languages.add("zh")
    if "日文" in text or "日語" in text or "japanese" in lower_text:
        languages.add("ja")
    return sorted(languages) if languages else ["unknown"]


def infer_fee_information(text: str, fallback: str, keywords: tuple[str, ...]) -> str:
    if fallback:
        return fallback
    for keyword in keywords:
        match = re.search(rf"[^。\n]{{0,16}}{re.escape(keyword)}[^。\n]{{0,220}}", text, flags=re.I)
        if not match:
            continue
        snippet = re.sub(r"\s+", " ", match.group(0)).strip(" ：:，,")
        keyword_index = snippet.lower().find(keyword.lower())
        prefix = snippet[:keyword_index]
        if not re.search(r"(?:每篇|每人|論文|作者|不收|免收|免費|無須|免繳)", prefix):
            snippet = snippet[keyword_index:]
        for marker in (
            "發表類型",
            "註冊網址",
            "報名網址",
            "聯絡人",
            "聯邦銀行",
            "戶名:",
            "帳號:",
            "上一篇文章",
            "下一篇文章",
        ):
            marker_index = snippet.find(marker)
            if marker_index > 0:
                snippet = snippet[:marker_index].rstrip(" ：:，,；;")
        has_amount = re.search(
            r"(?:NT\$|TWD|USD|新台幣|臺幣|台幣|美元|日圓|\d[\d,]*(?:元整|元|台幣|臺幣|美元|日圓))",
            snippet,
            flags=re.I,
        )
        is_free = re.search(r"(?:不收|免收|免費|無須繳交|免繳).{0,8}(?:費|費用)|(?:費|費用).{0,8}(?:免費|免收)", snippet)
        if snippet and (has_amount or is_free):
            if len(snippet) > 240:
                snippet = snippet[:239].rstrip(" ：:，,；;") + "…"
            return snippet
    return ""


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
        check_status = "ok"

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
            item["presentation_languages"] = infer_languages(text, item.get("presentation_languages", []))
            item["submission_fee"] = infer_fee_information(
                text,
                item.get("submission_fee", ""),
                ("投稿費", "審稿費", "論文處理費"),
            )
            item["registration_fee"] = infer_fee_information(
                text,
                item.get("registration_fee", ""),
                ("註冊費", "報名費", "登記費"),
            )
            history_sources[source_id] = {
                "hash": current_hash,
                "last_attempted_at": today_iso(),
                "last_successful_at": today_iso(),
                "last_checked": today_iso(),
                "last_changed": today_iso() if change_status in {"new", "changed"} else previous.get("last_changed", ""),
                "last_status": change_status,
                "check_status": "ok",
                "last_error": "",
                "url": item["homepage_url"],
            }
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
            errors.append(f"{source_id}: {exc}")
            check_status = "error"
            if not previous:
                change_status = "new"
                change_summary = "首次納入追蹤；本次來源自動檢查失敗，保留人工確認資料。"
                history_sources[source_id] = {
                    "hash": "",
                    "last_attempted_at": today_iso(),
                    "last_successful_at": "",
                    "last_checked": "",
                    "last_changed": "",
                    "last_status": "new",
                    "check_status": "error",
                    "last_error": str(exc),
                    "url": item["homepage_url"],
                }
            else:
                change_status = previous.get("last_status", "unchanged")
                change_summary = "本次來源檢查失敗，保留前次資料。"
                history_sources[source_id] = {
                    **previous,
                    "last_attempted_at": today_iso(),
                    "last_successful_at": previous.get("last_successful_at") or previous.get("last_checked", ""),
                    "last_status": change_status,
                    "check_status": "error",
                    "last_error": str(exc),
                    "url": item["homepage_url"],
                }

        source_history = history_sources.get(source_id, previous)
        item["last_checked"] = source_history.get("last_successful_at") or source_history.get("last_checked", "")
        item["last_attempted_at"] = source_history.get("last_attempted_at", today_iso())
        item["check_status"] = check_status
        item["check_error"] = source_history.get("last_error", "")
        item["presentation_languages"] = item.get("presentation_languages") or ["unknown"]
        item["submission_fee"] = item.get("submission_fee", "")
        item["registration_fee"] = item.get("registration_fee", "")
        item["last_changed"] = source_history.get("last_changed", "")
        item["change_status"] = change_status
        item["change_label"] = (
            "檢查失敗"
            if check_status == "error"
            else {"new": "新增", "changed": "資訊異動", "unchanged": "已檢查"}.get(change_status, "已檢查")
        )
        item["change_summary"] = change_summary
        item["review_status"] = "verified"
        conferences.append(item)

    return conferences, errors


def normalize_url(base_url: str, href: str) -> str:
    href = html.unescape(href).strip()
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return ""
    return urllib.parse.urljoin(base_url, href)


def canonical_url(url: str) -> str:
    parsed = urllib.parse.urlparse(urllib.parse.unquote(url))
    path = re.sub(r"/+", "/", parsed.path).rstrip("/")
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if key.lower() not in {"lang", "authuser"}]
    return urllib.parse.urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",
            urllib.parse.urlencode(sorted(query)),
            "",
        )
    )


def domain_key(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower()
    labels = [label for label in host.split(".") if label]
    if len(labels) >= 3 and labels[-1] == "tw" and labels[-2] in {"edu", "com", "org", "net"}:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def same_official_domain(source_url: str, link: str) -> bool:
    link_host = urllib.parse.urlparse(link).netloc.lower()
    return domain_key(source_url) == domain_key(link) or link_host in OFFICIAL_EXTERNAL_HOSTS


def valid_external_reference_url(source_url: str, link: str) -> bool:
    parsed = urllib.parse.urlparse(link)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.netloc.lower().split(":", 1)[0]
    if host in NON_OFFICIAL_REFERENCE_HOSTS:
        return False
    if domain_key(source_url) == domain_key(link):
        return False
    return host in OFFICIAL_EXTERNAL_HOSTS or host.endswith(OFFICIAL_REFERENCE_SUFFIXES)


def is_formal_conference_text(text: str) -> bool:
    lower_text = text.lower()
    if any(word in text for word in NON_CONFERENCE_WORDS):
        return False
    return any(word in text for word in FORMAL_CONFERENCE_WORDS) or any(
        word in lower_text for word in FORMAL_CONFERENCE_WORDS
    )


def is_relevant_conference_text(text: str) -> bool:
    lower_text = text.lower()
    if not any(marker in text for marker in current_year_markers()):
        return False
    if not any(word in text for word in CONFERENCE_WORDS) and not any(word in lower_text for word in CONFERENCE_WORDS):
        return False
    if not any(word in text for word in KEYWORDS):
        return False
    return is_formal_conference_text(text)


def recurring_organizer_sources(recurring_payload: dict) -> list[dict]:
    sources: list[dict] = []
    for item in recurring_payload.get("recurring_conferences", []):
        url = item.get("official_url", "")
        if not url:
            continue
        sources.append(
            {
                "name": item.get("name") or item.get("organizer") or "常態性研討會",
                "url": url,
                "recurring": True,
            }
        )
    return sources


def merge_sources(*groups: list[dict]) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for group in groups:
        for source in group:
            key = canonical_url(source.get("url", ""))
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(source)
    return merged


def candidate_id(prefix: str, url: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", urllib.parse.urlparse(url).netloc.lower()).strip("-")
    return f"{prefix}-{slug}-{hashlib.sha1(url.encode('utf-8')).hexdigest()[:8]}"


def title_key(title: str) -> str:
    return re.sub(r"[\W_]+", "", title.lower())


def duplicate_title_key(title: str) -> str:
    key = title_key(title)
    key = re.sub(r"20\d{2}|1\d{2}", "", key)
    key = re.sub(r"第[一二三四五六七八九十百千\d]+屆", "", key)
    return key.replace("論文", "")


def duplicates_known_title(title: str, known_titles: set[str]) -> bool:
    key = title_key(title)
    duplicate_key = duplicate_title_key(title)
    if not key:
        return False
    for known in known_titles:
        known_duplicate_key = duplicate_title_key(known)
        if key in known or known in key:
            return True
        if duplicate_key and known_duplicate_key:
            if duplicate_key in known_duplicate_key or known_duplicate_key in duplicate_key:
                return True
            if min(len(duplicate_key), len(known_duplicate_key)) >= 8:
                if SequenceMatcher(None, duplicate_key, known_duplicate_key).ratio() >= 0.86:
                    return True
    return False


def make_candidate(
    *,
    candidate_prefix: str,
    title: str,
    link: str,
    organizer: str,
    published: str,
    summary: str,
) -> dict:
    return {
        "id": candidate_id(candidate_prefix, link),
        "title": title,
        "organizer": organizer,
        "homepage_url": link,
        "submission_url": link,
        "registration_url": "",
        "event_start": "",
        "event_end": "",
        "location": "待確認",
        "submission_deadline": "",
        "submission_fee": "",
        "registration_fee": "",
        "fields": ["待確認"],
        "presentation_formats": ["other"],
        "presentation_languages": ["unknown"],
        "attention_notes": [summary],
        "last_checked": today_iso(),
        "last_changed": published,
        "change_status": "new",
        "change_label": "候選新增",
        "change_summary": "每日來源掃描發現的新候選項目。",
        "review_status": "candidate",
    }


def parse_ics_events(raw: str) -> list[dict[str, str]]:
    unfolded = re.sub(r"\r?\n[ \t]", "", raw)
    events: list[dict[str, str]] = []
    for block in re.findall(r"BEGIN:VEVENT\r?\n([\s\S]*?)\r?\nEND:VEVENT", unfolded):
        event: dict[str, str] = {}
        for line in block.splitlines():
            key, separator, value = line.partition(":")
            if not separator:
                continue
            base_key = key.split(";", 1)[0]
            if base_key in {"SUMMARY", "LOCATION", "URL", "DESCRIPTION", "DTSTART", "DTEND"}:
                event[base_key.lower()] = html.unescape(value.replace("\\,", ",").replace("\\n", " "))
            elif 'NAME="Country"' in key:
                event["country"] = html.unescape(value)
        if event:
            events.append(event)
    return events


def ics_date(value: str) -> str:
    match = re.match(r"(?P<year>20\d{2})(?P<month>\d{2})(?P<day>\d{2})", value)
    if not match:
        return ""
    try:
        return date(int(match.group("year")), int(match.group("month")), int(match.group("day"))).isoformat()
    except ValueError:
        return ""


def discover_from_ics_reference(
    source: dict,
    raw: str,
    existing_ids: set[str],
    existing_urls: set[str],
    existing_titles: set[str],
) -> list[dict]:
    candidates: list[dict] = []
    name = source.get("name", "外部行事曆")
    base_url = source.get("url", "")
    for record in parse_ics_events(raw):
        title = record.get("summary", "").strip()
        location_text = f"{record.get('country', '')} {record.get('location', '')} {record.get('description', '')[:400]}".lower()
        topic_text = f"{title} {record.get('description', '')[:800]}".lower()
        event_start = ics_date(record.get("dtstart", ""))
        link = normalize_url(base_url, record.get("url", ""))
        canonical = canonical_url(link)
        if not title or not event_start or event_start < today_iso():
            continue
        if not any(word in location_text for word in TAIWAN_LOCATION_WORDS):
            continue
        if not any(word in topic_text for word in BUSINESS_REFERENCE_WORDS):
            continue
        if not is_formal_conference_text(title):
            continue
        if not link or canonical in existing_urls or duplicates_known_title(title, existing_titles):
            continue
        item_id = candidate_id("reference", link)
        if item_id in existing_ids:
            continue
        item = make_candidate(
            candidate_prefix="reference",
            title=title[:120],
            link=link,
            organizer=name,
            published=today_iso(),
            summary=f"由「{name}」公開行事曆發現的台灣商管候選，須回到主辦單位官方頁確認。",
        )
        item["event_start"] = event_start
        end_date = ics_date(record.get("dtend", ""))
        if end_date and end_date > event_start:
            # RFC 5545 all-day DTEND is exclusive.
            item["event_end"] = (date.fromisoformat(end_date) - timedelta(days=1)).isoformat()
        else:
            item["event_end"] = event_start
        item["location"] = normalize_text(record.get("location", ""))[:80] or "台灣（待確認）"
        item["fields"] = ["財金", "商管"]
        candidates.append(item)
    return candidates


def discover_from_organizers(
    sources: list[dict],
    existing_ids: set[str],
    existing_urls: set[str],
    existing_titles: set[str],
) -> tuple[list[dict], list[str]]:
    candidates: list[dict] = []
    errors: list[str] = []
    seen_urls: set[str] = set()

    for source in sources:
        name = source.get("name", "待確認")
        url = source.get("url", "")
        if not url:
            continue
        try:
            raw, _ = fetch_url(url, timeout=12)
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError) as exc:
            errors.append(f"organizer:{name}: {exc}")
            continue

        for match in LINK_RE.finditer(raw):
            label = normalize_text(match.group("label"))
            link = normalize_url(url, match.group("href"))
            canonical = canonical_url(link)
            if not link or canonical in seen_urls or canonical in existing_urls:
                continue
            if not same_official_domain(url, link):
                continue
            text = f"{label} {link}"
            if any(word in text for word in FOLLOWUP_WORDS):
                continue
            if not label or not is_relevant_conference_text(text):
                continue
            if duplicates_known_title(label, existing_titles):
                continue
            item_id = candidate_id("organizer", link)
            if item_id in existing_ids:
                continue
            seen_urls.add(canonical)
            candidates.append(
                make_candidate(
                    candidate_prefix="organizer",
                    title=label[:120],
                    link=link,
                    organizer=name,
                    published=today_iso(),
                    summary=(
                        "由常態性研討會或主辦單位官方頁每日掃描發現，"
                        "已通過正式研討會初步篩選，仍待人工確認日期、投稿與發表形式。"
                    ),
                )
            )

    return candidates[:12], errors


def discover_from_references(
    sources: list[dict],
    existing_ids: set[str],
    existing_urls: set[str],
    existing_titles: set[str],
) -> tuple[list[dict], list[str]]:
    candidates: list[dict] = []
    errors: list[str] = []
    seen_urls: set[str] = set()

    for source in sources:
        name = source.get("name", "外部參考來源")
        base_url = source.get("url", "")
        api_url = source.get("api_url") or base_url
        if not api_url:
            continue
        source_format = source.get("format", "json")
        try:
            raw, _ = fetch_url(api_url, timeout=12)
            if source_format == "ics":
                candidates.extend(
                    discover_from_ics_reference(source, raw, existing_ids, existing_urls, existing_titles)
                )
                continue
            if source_format == "html_index":
                # SSRN's public index currently exposes conference names but not
                # reliable location metadata. Keep it as a monitored reference;
                # only explicit Taiwan links can become candidates.
                for match in LINK_RE.finditer(raw):
                    label = normalize_text(match.group("label"))
                    link = normalize_url(base_url, match.group("href"))
                    text = f"{label} {link}".lower()
                    if not any(word in text for word in TAIWAN_LOCATION_WORDS):
                        continue
                    if not any(word in text for word in BUSINESS_REFERENCE_WORDS):
                        continue
                    if not is_relevant_conference_text(text) or duplicates_known_title(label, existing_titles):
                        continue
                    if not link or canonical_url(link) in existing_urls:
                        continue
                    candidates.append(
                        make_candidate(
                            candidate_prefix="reference",
                            title=label[:120],
                            link=link,
                            organizer=name,
                            published=today_iso(),
                            summary=f"由「{name}」索引發現的台灣商管候選，須回到主辦單位官方頁確認。",
                        )
                    )
                continue
            records = json.loads(raw)
        except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"reference:{name}: {exc}")
            continue
        if not isinstance(records, list):
            errors.append(f"reference:{name}: API response is not a list")
            continue

        for record in records:
            if not isinstance(record, dict):
                continue
            title = str(record.get("title") or "").strip()
            if not title:
                continue
            text = " ".join(
                str(value)
                for value in (
                    title,
                    record.get("organizer") or "",
                    record.get("location") or "",
                    " ".join(record.get("tags") or []),
                )
            )
            if any(word in text for word in FOLLOWUP_WORDS):
                continue
            if not is_relevant_conference_text(text):
                continue
            if duplicates_known_title(title, existing_titles):
                continue

            link = normalize_url(base_url, str(record.get("registrationUrl") or record.get("href") or ""))
            canonical = canonical_url(link)
            if not link or canonical in seen_urls or canonical in existing_urls:
                continue
            if not valid_external_reference_url(base_url, link):
                continue
            item_id = candidate_id("reference", link)
            if item_id in existing_ids:
                continue

            seen_urls.add(canonical)
            published = str(record.get("updatedAt") or record.get("crawledAt") or today_iso())[:10]
            item = make_candidate(
                candidate_prefix="reference",
                title=title[:120],
                link=link,
                organizer=str(record.get("organizer") or name),
                published=published,
                summary=f"由外部研討會資訊站「{name}」每日比對發現，須回到主辦單位官方頁確認日期、投稿與發表形式。",
            )
            event_date = str(record.get("date") or "").strip()
            deadline = str(record.get("registrationDeadline") or "").strip()
            location = str(record.get("location") or "").strip()
            tags = [str(tag).strip() for tag in record.get("tags") or [] if str(tag).strip()]
            if event_date:
                item["event_start"] = event_date[:10]
                item["event_end"] = event_date[:10]
            if deadline:
                item["submission_deadline"] = deadline[:10]
            item["submission_fee"] = str(record.get("submissionFee") or "")[:240]
            item["registration_fee"] = str(record.get("registrationFee") or record.get("fee") or "")[:240]
            if location:
                item["location"] = location[:80]
            if tags:
                item["fields"] = tags[:6]
            candidates.append(item)

    return candidates[:12], errors


def merge_candidate_store(discovered: list[dict], stored: list[dict]) -> list[dict]:
    """Keep review decisions and first-seen dates across daily discovery runs."""
    today = today_iso()
    by_id = {item.get("id"): dict(item) for item in stored if item.get("id")}
    discovered_ids: set[str] = set()
    for candidate in discovered:
        candidate_id_value = candidate["id"]
        discovered_ids.add(candidate_id_value)
        previous = by_id.get(candidate_id_value, {})
        by_id[candidate_id_value] = {
            **candidate,
            "first_seen": previous.get("first_seen") or candidate.get("last_changed") or today,
            "last_seen": today,
            "candidate_status": previous.get("candidate_status", "pending"),
            "review_notes": previous.get("review_notes", ""),
            "is_stale": False,
        }

    for candidate_id_value, candidate in by_id.items():
        if candidate_id_value not in discovered_ids:
            candidate["is_stale"] = True

    return sorted(by_id.values(), key=lambda item: (item.get("candidate_status", "pending"), item.get("first_seen", ""), item["id"]))


def validate_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_payload(payload: dict, previous_payload: dict | None = None) -> list[str]:
    errors: list[str] = []
    items = payload.get("conferences")
    if not isinstance(items, list):
        return ["conferences must be a list"]

    required = ("id", "title", "homepage_url", "organizer", "review_status")
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for index, item in enumerate(items):
        prefix = f"conferences[{index}]"
        for key in required:
            if not item.get(key):
                errors.append(f"{prefix}.{key} is required")
        item_id = item.get("id", "")
        if item_id in seen_ids:
            errors.append(f"duplicate id: {item_id}")
        seen_ids.add(item_id)
        url = item.get("homepage_url", "")
        canonical = canonical_url(url)
        if not validate_url(url):
            errors.append(f"{prefix}.homepage_url is invalid: {url}")
        if canonical in seen_urls:
            errors.append(f"duplicate homepage_url: {url}")
        seen_urls.add(canonical)
        for key in ("event_start", "event_end", "submission_deadline", "last_checked", "last_changed"):
            value = item.get(key)
            if value:
                try:
                    date.fromisoformat(str(value))
                except ValueError:
                    errors.append(f"{prefix}.{key} is not ISO date: {value}")
        for key in ("submission_fee", "registration_fee"):
            value = item.get(key, "")
            if not isinstance(value, str) or len(value) > 240:
                errors.append(f"{prefix}.{key} must be a string of at most 240 characters")

    if previous_payload:
        old_verified = sum(item.get("review_status") == "verified" for item in previous_payload.get("conferences", []))
        new_verified = sum(item.get("review_status") == "verified" for item in items)
        if old_verified >= 5 and new_verified < old_verified * 0.65:
            errors.append(f"verified conference count dropped unexpectedly: {old_verified} -> {new_verified}")
    return errors


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh conference data")
    parser.add_argument("--fail-on-errors", action="store_true", help="write valid output but return non-zero when a source fails")
    parser.add_argument("--validate-only", action="store_true", help="validate the current generated data without network access")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.validate_only:
        validation_errors = validate_payload(read_json(OUTPUT_FILE, {}))
        for error in validation_errors:
            print(f"- {error}", file=sys.stderr)
        return 1 if validation_errors else 0

    sources = read_json(SOURCES_FILE, {"conferences": [], "organizer_sources": [], "reference_sources": []})
    recurring = read_json(RECURRING_FILE, {"recurring_conferences": []})
    history = read_json(HISTORY_FILE, {"sources": {}})
    previous_payload = read_json(OUTPUT_FILE, {"conferences": []})
    candidate_payload = read_json(CANDIDATES_FILE, {"candidates": []})
    migrated_candidates = [
        item for item in previous_payload.get("conferences", []) if item.get("review_status") == "candidate"
    ]
    conferences, errors = update_known_conferences(sources, history)
    existing_ids = {item["id"] for item in conferences}
    existing_urls = {canonical_url(item.get("homepage_url", "")) for item in conferences}
    existing_titles = {title_key(item.get("title", "")) for item in conferences}
    organizer_sources = merge_sources(
        sources.get("organizer_sources", []),
        recurring_organizer_sources(recurring),
    )
    organizer_candidates, organizer_errors = discover_from_organizers(
        organizer_sources,
        existing_ids,
        existing_urls,
        existing_titles,
    )
    errors.extend(organizer_errors)
    reference_candidates, reference_errors = discover_from_references(
        sources.get("reference_sources", []),
        existing_ids | {item["id"] for item in organizer_candidates},
        existing_urls | {canonical_url(item.get("homepage_url", "")) for item in organizer_candidates},
        existing_titles | {title_key(item.get("title", "")) for item in organizer_candidates},
    )
    errors.extend(reference_errors)
    stored_candidates = candidate_payload.get("candidates", []) or migrated_candidates
    candidate_store = merge_candidate_store(organizer_candidates + reference_candidates, stored_candidates)
    visible_candidates = [
        item for item in candidate_store if item.get("candidate_status") == "pending" and not item.get("is_stale")
    ]
    payload = {
        "generated_at": now_tw().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "source_count": len(sources.get("conferences", []))
        + len(organizer_sources)
        + len(sources.get("reference_sources", [])),
        "errors": errors,
        "health": {
            "status": "degraded" if errors else "healthy",
            "source_error_count": len(errors),
            "verified_count": len(conferences),
            "candidate_count": len(visible_candidates),
        },
        "conferences": conferences + visible_candidates,
    }
    validation_errors = validate_payload(payload, previous_payload)
    if validation_errors:
        print("Refusing to replace data because validation failed:", file=sys.stderr)
        for error in validation_errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    write_json(OUTPUT_FILE, payload)
    write_json(HISTORY_FILE, history)
    write_json(CANDIDATES_FILE, {"generated_at": payload["generated_at"], "candidates": candidate_store})
    if errors:
        print("Completed with source errors:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
    print(f"Wrote {len(payload['conferences'])} conferences to {OUTPUT_FILE}")
    return 2 if errors and args.fail_on_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
