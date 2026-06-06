#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
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
FOLLOWUP_WORDS = ("議程", "審查", "結果", "論文集", "優秀論文", "得獎", "獲獎", "錄取名單", "公告名單")
OFFICIAL_EXTERNAL_HOSTS = {"sites.google.com"}
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
            item["presentation_languages"] = infer_languages(text, item.get("presentation_languages", []))
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
        item["presentation_languages"] = item.get("presentation_languages") or ["unknown"]
        item["last_changed"] = history_sources.get(source_id, previous).get("last_changed", "")
        item["change_status"] = change_status
        item["change_label"] = {"new": "新增", "changed": "資訊異動", "unchanged": "已檢查"}.get(change_status, "已檢查")
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


def candidate_id(prefix: str, url: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", urllib.parse.urlparse(url).netloc.lower()).strip("-")
    return f"{prefix}-{slug}-{hashlib.sha1(url.encode('utf-8')).hexdigest()[:8]}"


def title_key(title: str) -> str:
    return re.sub(r"[\W_]+", "", title.lower())


def duplicates_known_title(title: str, known_titles: set[str]) -> bool:
    key = title_key(title)
    return bool(key) and any(key in known or known in key for known in known_titles)


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
            if not label or not any(word in text for word in CONFERENCE_WORDS):
                continue
            if duplicates_known_title(label, existing_titles):
                continue
            if not any(word in text for word in KEYWORDS) and "2026" not in text and "115" not in text:
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
                    summary="由主辦單位追蹤頁每日掃描發現，尚待人工確認日期、投稿與發表形式。",
                )
            )

    return candidates[:12], errors


def main() -> int:
    sources = read_json(SOURCES_FILE, {"conferences": [], "organizer_sources": []})
    history = read_json(HISTORY_FILE, {"sources": {}})
    conferences, errors = update_known_conferences(sources, history)
    existing_ids = {item["id"] for item in conferences}
    existing_urls = {canonical_url(item.get("homepage_url", "")) for item in conferences}
    existing_titles = {title_key(item.get("title", "")) for item in conferences}
    organizer_candidates, organizer_errors = discover_from_organizers(
        sources.get("organizer_sources", []),
        existing_ids,
        existing_urls,
        existing_titles,
    )
    errors.extend(organizer_errors)
    payload = {
        "generated_at": now_tw().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "source_count": len(sources.get("conferences", []))
        + len(sources.get("organizer_sources", [])),
        "errors": errors,
        "conferences": conferences + organizer_candidates,
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
