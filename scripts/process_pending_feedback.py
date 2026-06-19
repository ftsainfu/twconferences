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
                "issue_number": issue_number,
                "applied": applied,
                "summary_path": str(summary_path),
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
    parser.add_argument("--summary-dir", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    args = parser.parse_args()

    issues = json.loads(args.issues.read_text(encoding="utf-8"))
    if not isinstance(issues, list):
        raise ValueError("issues input must be a JSON list")
    results = process_issues(issues, args.summary_dir)
    args.results.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Processed {results['processed']} open reports; resolved {results['resolved']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
