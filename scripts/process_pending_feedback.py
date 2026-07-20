#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .process_feedback import process_event
except ImportError:
    from process_feedback import process_event


def process_issues(issues: list[dict], summary_dir: Path) -> dict:
    summary_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for issue in issues:
        title = str(issue.get("title") or "")
        if not title.startswith("[資料回報]"):
            continue
        issue_number = int(issue["number"])
        event = {
            "issue": {
                "number": issue_number,
                "title": title,
                "body": str(issue.get("body") or ""),
                "html_url": str(issue.get("url") or ""),
                "created_at": str(issue.get("createdAt") or ""),
            }
        }
        handled, applied, summary = process_event(event)
        if not handled:
            continue
        summary_path = summary_dir / f"issue-{issue_number}.txt"
        summary_path.write_text(
            summary + "\n\n每日排程已重新檢查此回報。\n",
            encoding="utf-8",
        )
        results.append(
            {
                "source": "github",
                "issue_number": issue_number,
                "applied": applied,
                "summary_path": str(summary_path),
                "report_label": f"#{issue_number}",
            }
        )
    return {
        "processed": len(results),
        "resolved": sum(1 for item in results if item["applied"]),
        "results": results,
    }


def normalize_external_reports(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("reports", "records", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def external_report_body(report: dict) -> str:
    suspicious = str(report.get("suspicious") or "").lower() in {"true", "1", "yes"}
    lines = [
        f"conference_id: {report.get('conference_id', '')}",
        f"conference_title: {report.get('conference_title', '')}",
        f"current_url: {report.get('current_url', '')}",
        f"current_submission_url: {report.get('current_submission_url', '')}",
        f"current_registration_url: {report.get('current_registration_url', '')}",
        f"current_event_start: {report.get('current_event_start', '')}",
        f"current_submission_deadline: {report.get('current_submission_deadline', '')}",
        f"current_acceptance_notification_date: {report.get('current_acceptance_notification_date', '')}",
        f"current_submission_fee: {report.get('current_submission_fee', '')}",
        f"current_registration_fee: {report.get('current_registration_fee', '')}",
        f"report_type: {report.get('report_type', '')}",
        f"correction_field: {report.get('correction_field', '')}",
        f"correction_value: {report.get('correction_value', '')}",
        f"evidence_url: {report.get('evidence_url', '')}",
        f"reporter_id: {report.get('reporter_id', '')}",
        f"opened_after_ms: {report.get('opened_after_ms', '')}",
        f"anti_spam_suspicious: {str(suspicious).lower()}",
        f"anti_spam_reason: {report.get('suspicious_reason', '')}",
        "",
        "details:",
        str(report.get("details") or ""),
    ]
    return "\n".join(lines)


def process_external_reports(reports: list[dict], summary_dir: Path) -> dict:
    summary_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for index, report in enumerate(reports, start=1):
        conference_id = str(report.get("conference_id") or "")
        if not conference_id:
            continue
        external_id = str(report.get("id") or report.get("created_at") or f"external-{index}").replace("/", "-")
        event = {
            "issue": {
                "external_id": external_id,
                "title": f"[資料回報] {conference_id}",
                "body": external_report_body(report),
                "html_url": "",
                "created_at": str(report.get("created_at") or report.get("submitted_at") or ""),
            }
        }
        handled, applied, summary = process_event(event)
        if not handled:
            continue
        summary_path = summary_dir / f"{external_id}.txt"
        summary_path.write_text(
            summary + "\n\n每日排程已重新檢查此免登入回報。\n",
            encoding="utf-8",
        )
        results.append(
            {
                "source": "external",
                "external_id": external_id,
                "issue_number": None,
                "applied": applied,
                "summary_path": str(summary_path),
                "report_label": external_id,
            }
        )
    return {
        "processed": len(results),
        "resolved": sum(1 for item in results if item["applied"]),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Retry unresolved GitHub conference reports")
    parser.add_argument("--issues", required=True, type=Path)
    parser.add_argument("--external-reports", type=Path)
    parser.add_argument("--summary-dir", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    args = parser.parse_args()

    issues = json.loads(args.issues.read_text(encoding="utf-8"))
    if not isinstance(issues, list):
        raise ValueError("issues input must be a JSON list")
    results = process_issues(issues, args.summary_dir)
    if args.external_reports and args.external_reports.exists():
        external_payload = json.loads(args.external_reports.read_text(encoding="utf-8"))
        external_results = process_external_reports(normalize_external_reports(external_payload), args.summary_dir)
        results["processed"] += external_results["processed"]
        results["resolved"] += external_results["resolved"]
        results["results"].extend(external_results["results"])
    args.results.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Processed {results['processed']} open reports; resolved {results['resolved']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
