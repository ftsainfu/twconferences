#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

TITLE_PREFIX = "[研討會評分]"
PARTICIPATION_VALUES = {"registered", "attended"}
DIMENSION_FIELDS = [
    "agenda_quality",
    "review_transparency",
    "organizer_communication",
    "networking_value",
    "cost_value",
]
MIN_COMMENT_LENGTH = 20


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


def parse_int_score(value: object) -> int:
    try:
        score = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return score if score in range(1, 6) else 0


def normalized_comment(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def extract_dimension_scores(values: dict) -> dict[str, int]:
    return {field: parse_int_score(values.get(field)) for field in DIMENSION_FIELDS}


def validate_rating(issue: dict, conference_ids: set[str]) -> tuple[dict | None, str]:
    if not str(issue.get("title") or "").startswith(TITLE_PREFIX):
        return None, "不是研討會評分。"
    values = parse_rating_body(str(issue.get("body") or ""))
    conference_id = values.get("conference_id", "")
    author = author_login(issue)
    rating = parse_int_score(values.get("rating", ""))
    dimensions = extract_dimension_scores(values)
    participation = values.get("participation", "")
    comment = normalized_comment(values.get("comment", ""))
    if conference_id not in conference_ids:
        return None, "找不到可評分的正式研討會。"
    if not author:
        return None, "無法辨識 GitHub 使用者。"
    if not rating:
        return None, "評分必須是 1 到 5 星。"
    if any(not score for score in dimensions.values()):
        return None, "五個面向都必須評 1 到 5 星。"
    if len(comment) < MIN_COMMENT_LENGTH:
        return None, f"評分原因至少需要 {MIN_COMMENT_LENGTH} 字。"
    if participation not in PARTICIPATION_VALUES:
        return None, "請確認是已報名或已參加。"
    if values.get("confirmed", "").lower() != "true":
        return None, "必須確認本人已報名或參加。"
    return {
        "conference_id": conference_id,
        "author": author.lower(),
        "rating": rating,
        "dimensions": dimensions,
        "participation": participation,
        "comment": comment,
        "created_at": str(issue.get("createdAt") or issue.get("created_at") or ""),
        "issue_number": int(issue.get("number") or 0),
    }, "評分格式有效，已納入彙整。"


def validate_external_rating(record: dict, conference_ids: set[str], row_number: int = 0) -> tuple[dict | None, str]:
    conference_id = str(record.get("conference_id") or "").strip()
    voter_id = str(record.get("voter_id") or record.get("nickname") or "").strip()
    rating = parse_int_score(record.get("rating"))
    dimensions = record.get("dimensions") if isinstance(record.get("dimensions"), dict) else record
    dimension_scores = extract_dimension_scores(dimensions)
    participation = str(record.get("participation") or "").strip()
    confirmed = str(record.get("confirmed") or "").strip().lower()
    comment = normalized_comment(record.get("comment", ""))
    if conference_id not in conference_ids:
        return None, "找不到可評分的正式研討會。"
    if not voter_id:
        return None, "缺少匿名評分識別碼，無法降低重複評分。"
    if not rating:
        return None, "評分必須是 1 到 5 星。"
    if any(not score for score in dimension_scores.values()):
        return None, "五個面向都必須評 1 到 5 星。"
    if len(comment) < MIN_COMMENT_LENGTH:
        return None, f"評分原因至少需要 {MIN_COMMENT_LENGTH} 字。"
    if participation not in PARTICIPATION_VALUES:
        return None, "請確認是已報名或已參加。"
    if confirmed not in {"true", "1", "yes"}:
        return None, "必須確認本人已報名或參加。"
    return {
        "conference_id": conference_id,
        "author": f"external:{voter_id.lower()}",
        "rating": rating,
        "dimensions": dimension_scores,
        "participation": participation,
        "comment": comment,
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


def mark_suspicious_votes(votes: dict[tuple[str, str], dict]) -> None:
    author_counts: dict[str, int] = {}
    comment_counts: dict[str, int] = {}
    for vote in votes.values():
        author_counts[vote["author"]] = author_counts.get(vote["author"], 0) + 1
        comment_key = vote.get("comment", "").lower()
        if comment_key:
            comment_counts[comment_key] = comment_counts.get(comment_key, 0) + 1
    for vote in votes.values():
        reasons: list[str] = []
        if author_counts.get(vote["author"], 0) > 5:
            reasons.append("high_volume_voter")
        comment_key = vote.get("comment", "").lower()
        if comment_key and comment_counts.get(comment_key, 0) > 1:
            reasons.append("duplicate_reason")
        dimension_values = list((vote.get("dimensions") or {}).values())
        if vote["rating"] in {1, 5} and len(set(dimension_values + [vote["rating"]])) == 1 and len(vote.get("comment", "")) < 40:
            reasons.append("thin_extreme_rating")
        vote["suspicious_reasons"] = reasons
        vote["is_suspicious"] = bool(reasons)


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
    mark_suspicious_votes(latest_votes)

    grouped: dict[str, list[dict]] = {}
    for vote in latest_votes.values():
        grouped.setdefault(vote["conference_id"], []).append(vote)

    ratings: dict[str, dict] = {}
    for conference_id, votes in sorted(grouped.items()):
        counted_votes = [vote for vote in votes if not vote.get("is_suspicious")]
        if not counted_votes:
            ratings[conference_id] = {
                "average": 0,
                "count": 0,
                "submitted_count": len(votes),
                "flagged_count": len(votes),
                "registered_count": 0,
                "attended_count": 0,
                "distribution": {str(value): 0 for value in range(1, 6)},
                "dimension_averages": {},
            }
            continue
        distribution = {str(value): 0 for value in range(1, 6)}
        for vote in counted_votes:
            distribution[str(vote["rating"])] += 1
        dimension_averages = {
            field: round(sum(vote["dimensions"][field] for vote in counted_votes) / len(counted_votes), 2)
            for field in DIMENSION_FIELDS
        }
        ratings[conference_id] = {
            "average": round(sum(vote["rating"] for vote in counted_votes) / len(counted_votes), 2),
            "count": len(counted_votes),
            "submitted_count": len(votes),
            "flagged_count": sum(vote.get("is_suspicious", False) for vote in votes),
            "registered_count": sum(vote["participation"] == "registered" for vote in counted_votes),
            "attended_count": sum(vote["participation"] == "attended" for vote in counted_votes),
            "distribution": distribution,
            "dimension_averages": dimension_averages,
        }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rating_count": sum(not vote.get("is_suspicious", False) for vote in latest_votes.values()),
        "submitted_rating_count": len(latest_votes),
        "flagged_rating_count": sum(vote.get("is_suspicious", False) for vote in latest_votes.values()),
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
