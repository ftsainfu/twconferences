import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import date

from scripts.update_conferences import (
    canonical_url,
    current_year_markers,
    duplicates_known_title,
    find_dates,
    merge_candidate_store,
    title_key,
    valid_external_reference_url,
    validate_payload,
)
from scripts import process_feedback
from scripts.process_feedback import date_variants, parse_report, trusted_correction_url, validate_correction


class DateTests(unittest.TestCase):
    def test_year_markers_include_gregorian_and_roc_years(self):
        self.assertEqual(current_year_markers(date(2027, 1, 1)), ("2027", "116", "2028", "117"))

    def test_find_dates_converts_roc_and_rejects_invalid_date(self):
        self.assertEqual(find_dates("民國115年6月19日、2026/06/20"), ["2026-06-19", "2026-06-20"])
        self.assertEqual(find_dates("2026/13/40"), [])


class CandidateTests(unittest.TestCase):
    def test_title_deduplication_ignores_year_and_ordinal(self):
        known = {title_key("2026 第十六屆財務金融研討會")}
        self.assertTrue(duplicates_known_title("2027 第十七屆財務金融研討會", known))

    def test_merge_preserves_review_state(self):
        stored = [{"id": "c1", "candidate_status": "rejected", "first_seen": "2026-01-01"}]
        discovered = [{"id": "c1", "title": "Example", "last_changed": "2026-06-01"}]
        merged = merge_candidate_store(discovered, stored)
        self.assertEqual(merged[0]["candidate_status"], "rejected")
        self.assertEqual(merged[0]["first_seen"], "2026-01-01")
        self.assertFalse(merged[0]["is_stale"])


class ValidationTests(unittest.TestCase):
    def test_canonical_url_removes_tracking_variants(self):
        self.assertEqual(
            canonical_url("HTTPS://Example.COM/a/?authuser=1&lang=zh"),
            "https://example.com/a",
        )

    def test_payload_rejects_duplicates_and_invalid_dates(self):
        item = {
            "id": "same",
            "title": "Conference",
            "organizer": "Organizer",
            "homepage_url": "https://example.com/event",
            "review_status": "verified",
            "event_start": "2026-19-40",
        }
        errors = validate_payload({"conferences": [item, dict(item)]})
        self.assertTrue(any("duplicate id" in error for error in errors))
        self.assertTrue(any("duplicate homepage_url" in error for error in errors))
        self.assertTrue(any("not ISO date" in error for error in errors))

    def test_external_reference_requires_official_domain(self):
        source = "https://aggregator.example/api"
        self.assertTrue(valid_external_reference_url(source, "https://finance.nfu.edu.tw/event"))
        self.assertTrue(valid_external_reference_url(source, "https://finance.org.tw/event"))
        self.assertFalse(valid_external_reference_url(source, "https://news.example.com/event"))


class FeedbackTests(unittest.TestCase):
    def test_parse_report_keeps_structured_fields_and_details(self):
        report = parse_report("conference_id: abc\nreport_type: wrong_date\ndetails:\n日期應更新")
        self.assertEqual(report["conference_id"], "abc")
        self.assertEqual(report["details"], "日期應更新")

    def test_date_variants_include_roc_date(self):
        self.assertIn("115年6月19日", date_variants("2026-06-19"))

    def test_correction_url_must_be_official_or_related(self):
        self.assertTrue(trusted_correction_url("https://finance.nfu.edu.tw/news", "", "https://nfu.edu.tw/old"))
        self.assertFalse(trusted_correction_url("https://example.net/news", "", "https://nfu.edu.tw/old"))

    @patch("scripts.process_feedback.fetch_url", return_value=("會議日期：2026年6月19日", "utf-8"))
    def test_date_correction_requires_value_on_evidence_page(self, _fetch):
        valid, message = validate_correction(
            {"homepage_url": "https://nfu.edu.tw/event"},
            "event_start",
            "2026-06-19",
            "https://nfu.edu.tw/notice",
        )
        self.assertTrue(valid)
        self.assertIn("佐證頁面", message)

    def test_process_event_writes_isolated_report_and_safe_correction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources.json"
            candidates = root / "candidates.json"
            generated = root / "conferences.json"
            reports = root / "reports"
            sources.write_text(json.dumps({"conferences": [{
                "id": "conf-1",
                "title": "Conference",
                "homepage_url": "https://example.edu.tw/old",
                "attention_notes": [],
            }]}), encoding="utf-8")
            candidates.write_text('{"candidates": []}', encoding="utf-8")
            generated.write_text(json.dumps({"conferences": [{
                "id": "conf-1",
                "homepage_url": "https://example.edu.tw/old",
                "review_status": "verified",
            }]}), encoding="utf-8")
            event = {"issue": {
                "number": 12,
                "title": "[資料回報] conf-1",
                "html_url": "https://github.com/example/issues/12",
                "body": "conference_id: conf-1\nconference_title: Conference\nreport_type: broken_link\ncorrection_field: homepage_url\ncorrection_value: https://example.edu.tw/new\nevidence_url:\ndetails:\n舊連結失效",
            }}
            with (
                patch.object(process_feedback, "SOURCES_FILE", sources),
                patch.object(process_feedback, "CANDIDATES_FILE", candidates),
                patch.object(process_feedback, "OUTPUT_FILE", generated),
                patch.object(process_feedback, "REPORTS_DIR", reports),
                patch.object(process_feedback, "validate_correction", return_value=(True, "verified")),
            ):
                handled, applied, _ = process_feedback.process_event(event)
            self.assertTrue(handled)
            self.assertTrue(applied)
            self.assertTrue((reports / "issue-12.json").exists())
            updated = json.loads(sources.read_text(encoding="utf-8"))
            self.assertEqual(updated["conferences"][0]["homepage_url"], "https://example.edu.tw/new")
            rendered = json.loads(generated.read_text(encoding="utf-8"))
            self.assertEqual(rendered["conferences"][0]["homepage_url"], "https://example.edu.tw/new")


if __name__ == "__main__":
    unittest.main()
