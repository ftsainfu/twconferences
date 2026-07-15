#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

TITLE_PREFIX = "[研討會評分]"
PARTICIPATION_VALUES = {"registered", "attended"}


def parse_rating_body(body: str) -> dict[str, str]:
    values: dict[str, str] = {}
    comment: list[str] = []
    in_comment = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line == "comment:":
            in_comment = True
            continue
        if in_comment:
            comment.append(raw_line.strip())
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
    values["comment"] = "\n".join(comment).strip()
    return values


def author_login(issue: dict) -> str:
    author = issue.get("author")
    if isinstance(author, dict):
        return str(author.get("login") or "").strip()
    return str(author or issue.get("user") or "").strip()


def validate_rating(issue: dict, conference_ids: set[str]) -> tuple[dict | None, str]:
    if not str(issue.get("title") or "").startswith(TITLE_PREFIX):
        return None, "不是研討會評分。"
    values = parse_rating_body(str(issue.get("body") or ""))
    conference_id = values.get("conference_id", "")
    author = author_login(issue)
    try:
        rating = int(values.get("rating", ""))
    except ValueError:
        rating = 0
    participation = values.get("participation", "")
    if conference_id not in conference_ids:
        return None, "找不到可評分的正式研討會。"
    if not author:
        return None, "無法辨識 GitHub 使用者。"
    if rating not in range(1, 6):
        return None, "評分必須是 1 到 5 星。"
    if participation not in PARTICIPATION_VALUES:
        return None, "請確認是已報名或已參加。"
    if values.get("confirmed", "").lower() != "true":
        return None, "必須確認本人已報名或參加。"
    return {
        "conference_id": conference_id,
        "author": author.lower(),
        "rating": rating,
        "participation": participation,
        "created_at": str(issue.get("createdAt") or issue.get("created_at") or ""),
        "issue_number": int(issue.get("number") or 0),
    }, "評分格式有效，已納入彙整。"


def validate_external_rating(record: dict, conference_ids: set[str], row_number: int = 0) -> tuple[dict | None, str]:
    conference_id = str(record.get("conference_id") or "").strip()
    voter_id = str(record.get("voter_id") or record.get("nickname") or "").strip()
    try:
        rating = int(record.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0
    participation = str(record.get("participation") or "").strip()
    confirmed = str(record.get("confirmed") or "").strip().lower()
    if conference_id not in conference_ids:
        return None, "找不到可評分的正式研討會。"
    if not voter_id:
        return None, "缺少匿名評分識別碼，無法降低重複評分。"
    if rating not in range(1, 6):
        return None, "評分必須是 1 到 5 星。"
    if participation not in PARTICIPATION_VALUES:
        return None, "請確認是已報名或已參加。"
    if confirmed not in {"true", "1", "yes"}:
        return None, "必須確認本人已報名或參加。"
    return {
        "conference_id": conference_id,
        "author": f"external:{voter_id.lower()}",
        "rating": rating,
        "participation": participation,
        "created_at": str(record.get("created_at") or record.get("submitted_at") or ""),
        "issue_number": -row_number,
    }, "外部評分格式有效，已納入彙整。"


def normalize_external_payload(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("ratings", "records", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def aggregate_ratings(issues: list[dict], conferences: list[dict], external_ratings: list[dict] | None = None) -> tuple[dict, dict[int, dict]]:
    conference_ids = {
        str(item.get("id"))
        for item in conferences
        if item.get("id") and item.get("review_status") != "candidate"
    }
    latest_votes: dict[tuple[str, str], dict] = {}
    issue_results: dict[int, dict] = {}
    for issue in issues:
        vote, message = validate_rating(issue, conference_ids)
        issue_number = int(issue.get("number") or 0)
        issue_results[issue_number] = {"valid": vote is not None, "message": message}
        if not vote:
            continue
        key = (vote["conference_id"], vote["author"])
        previous = latest_votes.get(key)
        current_order = (vote["created_at"], vote["issue_number"])
        previous_order = (previous["created_at"], previous["issue_number"]) if previous else ("", -1)
        if current_order >= previous_order:
            latest_votes[key] = vote
    for row_number, record in enumerate(external_ratings or [], start=1):
        vote, _message = validate_external_rating(record, conference_ids, row_number)
        if not vote:
            continue
        key = (vote["conference_id"], vote["author"])
        previous = latest_votes.get(key)
        current_order = (vote["created_at"], vote["issue_number"])
        previous_order = (previous["created_at"], previous["issue_number"]) if previous else ("", -1)
        if current_order >= previous_order:
            latest_votes[key] = vote

    grouped: dict[str, list[dict]] = {}
    for vote in latest_votes.values():
        grouped.setdefault(vote["conference_id"], []).append(vote)

    ratings: dict[str, dict] = {}
    for conference_id, votes in sorted(grouped.items()):
        distribution = {str(value): 0 for value in range(1, 6)}
        for vote in votes:
            distribution[str(vote["rating"])] += 1
        ratings[conference_id] = {
            "average": round(sum(vote["rating"] for vote in votes) / len(votes), 2),
            "count": len(votes),
            "registered_count": sum(vote["participation"] == "registered" for vote in votes),
            "attended_count": sum(vote["participation"] == "attended" for vote in votes),
            "distribution": distribution,
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rating_count": len(latest_votes),
        "conference_count": len(ratings),
        "ratings": ratings,
    }
    return payload, issue_results


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate conference rating issues")
    parser.add_argument("--issues", required=True, type=Path)
    parser.add_argument("--conferences", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--external-ratings", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--issue-number", type=int)
    args = parser.parse_args()

    issues = json.loads(args.issues.read_text(encoding="utf-8"))
    external_ratings = []
    if args.external_ratings and args.external_ratings.exists():
        external_ratings = normalize_external_payload(json.loads(args.external_ratings.read_text(encoding="utf-8")))
    conference_payload = json.loads(args.conferences.read_text(encoding="utf-8"))
    payload, issue_results = aggregate_ratings(issues, conference_payload.get("conferences", []), external_ratings)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.result and args.issue_number is not None:
        result = issue_results.get(args.issue_number, {"valid": False, "message": "找不到本次評分。"})
        args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
