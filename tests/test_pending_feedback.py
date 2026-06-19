import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.process_pending_feedback import process_issues


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


if __name__ == "__main__":
    unittest.main()
