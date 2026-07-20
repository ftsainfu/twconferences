import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.process_pending_feedback import normalize_external_reports, process_external_reports, process_issues


class PendingFeedbackTests(unittest.TestCase):
    @patch("scripts.process_pending_feedback.process_event")
    def test_processes_only_open_report_titles_and_writes_summaries(self, process_event):
        process_event.return_value = (True, True, "verified correction")
        issues = [
            {
                "number": 9,
                "title": "[資料回報] conf-9",
                "body": "conference_id: conf-9",
                "url": "https://github.com/example/issues/9",
                "createdAt": "2026-06-19T00:00:00Z",
            },
            {"number": 10, "title": "General question", "body": ""},
        ]
        with tempfile.TemporaryDirectory() as directory:
            results = process_issues(issues, Path(directory))
            summary = Path(results["results"][0]["summary_path"])
            self.assertTrue(summary.exists())
            self.assertIn("每日排程", summary.read_text(encoding="utf-8"))
        self.assertEqual(results["processed"], 1)
        self.assertEqual(results["resolved"], 1)
        event = process_event.call_args.args[0]
        self.assertEqual(event["issue"]["created_at"], "2026-06-19T00:00:00Z")

    @patch("scripts.process_pending_feedback.process_event")
    def test_processes_external_reports_without_issue_number(self, process_event):
        process_event.return_value = (True, False, "record only")
        reports = [{
            "created_at": "2026-07-15T00:00:00Z",
            "conference_id": "conf-1",
            "conference_title": "Conference",
            "report_type": "wrong_submission_url",
            "reporter_id": "browser-1",
            "details": "投稿連結可能有誤",
        }]
        with tempfile.TemporaryDirectory() as directory:
            results = process_external_reports(reports, Path(directory))
            summary = Path(results["results"][0]["summary_path"])
            self.assertTrue(summary.exists())
            self.assertEqual(results["results"][0]["source"], "external")
            self.assertIsNone(results["results"][0]["issue_number"])
        event = process_event.call_args.args[0]
        self.assertEqual(event["issue"]["title"], "[資料回報] conf-1")
        self.assertIn("report_type: wrong_submission_url", event["issue"]["body"])

    def test_normalizes_external_report_payload_wrappers(self):
        self.assertEqual(normalize_external_reports({"reports": [{"conference_id": "conf-1"}]}), [{"conference_id": "conf-1"}])


if __name__ == "__main__":
    unittest.main()
