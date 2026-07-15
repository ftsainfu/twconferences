import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import date

from scripts.update_conferences import (
    assess_information_quality,
    canonical_url,
    check_conference_links,
    current_year_markers,
    duplicates_known_title,
    find_dates,
    government_organizer_sources,
    infer_acceptance_notification_date,
    infer_fee_information,
    is_relevant_conference_text,
    merge_candidate_store,
    merge_discovered_candidates,
    parse_ics_events,
    discover_from_organizers,
    discover_from_ics_reference,
    fetch_url,
    title_key,
    scholarly_organizer_sources,
    university_organizer_sources,
    valid_official_discovery_link,
    valid_external_reference_url,
    validate_payload,
)
from scripts import process_feedback
from scripts.process_feedback import (
    date_variants,
    discover_official_url_correction,
    infer_correction_field,
    parse_report,
    trusted_correction_url,
    validate_correction,
)


class DateTests(unittest.TestCase):
    def test_year_markers_include_gregorian_and_roc_years(self):
        self.assertEqual(current_year_markers(date(2027, 1, 1)), ("2027", "116", "2028", "117"))

    def test_find_dates_converts_roc_and_rejects_invalid_date(self):
        self.assertEqual(
            find_dates("民國115年6月19日、2026/06/20、September 11, 2026"),
            ["2026-06-19", "2026-06-20", "2026-09-11"],
        )
        self.assertEqual(find_dates("2026/13/40"), [])

    def test_fee_inference_keeps_relevant_sentence_only(self):
        text = "其他說明。論文審查通過後，每篇論文註冊費新台幣 2,000 元；學生優惠另見公告。"
        fee = infer_fee_information(text, "", ("註冊費", "報名費", "登記費"))
        self.assertIn("註冊費新台幣 2,000 元", fee)
        self.assertNotIn("其他說明", fee)

    def test_fee_inference_ignores_policy_without_amount(self):
        text = "審查結果公告後恕不退回報名費用，詳情另行通知。"
        self.assertEqual(infer_fee_information(text, "", ("註冊費", "報名費", "登記費")), "")

    def test_acceptance_notification_date_inference_uses_result_windows(self):
        self.assertEqual(
            infer_acceptance_notification_date("投稿截止日期為 2026-07-31，投稿錄取公告日期為 2026-08-31。", ""),
            "2026-08-31",
        )
        self.assertEqual(
            infer_acceptance_notification_date("Notice of Paper Acceptance: September 11, 2026", ""),
            "2026-09-11",
        )

    def test_acceptance_notification_date_inference_preserves_manual_value(self):
        self.assertEqual(
            infer_acceptance_notification_date("審查結果公告日期為 2026-09-11。", "2026-09-10"),
            "2026-09-10",
        )


class FetchTests(unittest.TestCase):
    @patch("scripts.update_conferences.subprocess.run")
    def test_fetch_url_uses_curl_and_detects_charset(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = '<meta charset="big5">測試'.encode("big5")
        run.return_value.stderr = b""

        body, charset = fetch_url("https://example.edu.tw/event")

        self.assertEqual(body, '<meta charset="big5">測試')
        self.assertEqual(charset.lower(), "big5")
        self.assertIn("--fail", run.call_args.args[0])

    @patch("scripts.update_conferences.subprocess.run")
    def test_invalid_tls_exception_is_explicit_and_scoped(self, run):
        run.return_value.returncode = 0
        run.return_value.stdout = b"conference"
        run.return_value.stderr = b""

        fetch_url("https://official.example.edu.tw/event", allow_invalid_tls=True)

        self.assertIn("--insecure", run.call_args.args[0])

    @patch("scripts.update_conferences.subprocess.run", side_effect=FileNotFoundError)
    @patch("scripts.update_conferences.urllib.request.urlopen")
    def test_fetch_url_falls_back_to_urllib_when_curl_is_unavailable(self, urlopen, _run):
        response = urlopen.return_value.__enter__.return_value
        response.headers.get_content_charset.return_value = "utf-8"
        response.read.return_value = "成功".encode()

        body, charset = fetch_url("https://example.edu.tw/event", attempts=1)

        self.assertEqual((body, charset), ("成功", "utf-8"))


class LinkHealthTests(unittest.TestCase):
    @patch("scripts.update_conferences.today_iso", return_value="2026-07-04")
    @patch("scripts.update_conferences.fetch_url", side_effect=TimeoutError("timeout"))
    def test_link_health_marks_warning_before_consecutive_failure_threshold(self, _fetch, _today):
        conferences = [{
            "id": "conf-1",
            "review_status": "verified",
            "homepage_url": "https://example.edu.tw/event",
            "submission_url": "https://example.edu.tw/submit",
            "registration_url": "",
            "check_status": "ok",
        }]
        history = {"links": {}}

        errors = check_conference_links(conferences, history)

        self.assertEqual(errors, [])
        self.assertEqual(conferences[0]["link_health"]["submission_url"]["status"], "warning")
        self.assertEqual(conferences[0]["link_health"]["submission_url"]["consecutive_failures"], 1)

    @patch("scripts.update_conferences.today_iso", return_value="2026-07-04")
    @patch("scripts.update_conferences.fetch_url", side_effect=TimeoutError("timeout"))
    def test_link_health_marks_broken_after_repeated_failures(self, _fetch, _today):
        history = {"links": {
            "conf-1:submission_url:https://example.edu.tw/submit": {
                "url": "https://example.edu.tw/submit",
                "status": "warning",
                "last_attempted_at": "2026-07-03",
                "last_successful_at": "",
                "consecutive_failures": 1,
                "last_error": "timeout",
            },
        }}
        conferences = [{
            "id": "conf-1",
            "review_status": "verified",
            "homepage_url": "https://example.edu.tw/event",
            "submission_url": "https://example.edu.tw/submit",
            "registration_url": "",
            "check_status": "ok",
        }]

        errors = check_conference_links(conferences, history)

        self.assertEqual(conferences[0]["link_health"]["submission_url"]["status"], "broken")
        self.assertEqual(conferences[0]["link_health"]["submission_url"]["consecutive_failures"], 2)
        self.assertEqual(errors, ["conf-1.submission_url: timeout"])
        self.assertIn("投稿連結", conferences[0]["link_health_summary"])

    @patch("scripts.update_conferences.today_iso", return_value="2026-07-04")
    @patch("scripts.update_conferences.fetch_url", return_value=("ok", "utf-8"))
    def test_link_health_success_resets_failure_count(self, _fetch, _today):
        history = {"links": {
            "conf-1:registration_url:https://example.edu.tw/register": {
                "url": "https://example.edu.tw/register",
                "status": "broken",
                "last_attempted_at": "2026-07-03",
                "last_successful_at": "",
                "consecutive_failures": 3,
                "last_error": "timeout",
            },
        }}
        conferences = [{
            "id": "conf-1",
            "review_status": "verified",
            "homepage_url": "https://example.edu.tw/event",
            "submission_url": "",
            "registration_url": "https://example.edu.tw/register",
            "check_status": "ok",
        }]

        errors = check_conference_links(conferences, history)

        self.assertEqual(errors, [])
        self.assertEqual(conferences[0]["link_health"]["registration_url"]["status"], "ok")
        self.assertEqual(conferences[0]["link_health"]["registration_url"]["consecutive_failures"], 0)


class CandidateTests(unittest.TestCase):
    @patch("scripts.update_conferences.current_year_markers", return_value=("2026", "115"))
    def test_english_business_keyword_matching_is_case_insensitive(self, _markers):
        self.assertTrue(is_relevant_conference_text("2026 International Symposium on Management Innovation"))

    def test_university_sources_receive_safe_scan_defaults(self):
        sources = university_organizer_sources({"university_sources": [{
            "name": "Example College of Management",
            "url": "https://management.example.edu.tw/",
        }]})
        self.assertEqual(sources[0]["source_type"], "university_college")
        self.assertEqual(sources[0]["attempts"], 1)

    def test_university_source_can_nominate_external_conference_site(self):
        source = {
            "url": "https://management.example.edu.tw/",
            "source_type": "university_college",
        }
        self.assertTrue(valid_official_discovery_link(source, "https://conference.example.org/2027"))
        self.assertFalse(valid_official_discovery_link(source, "https://forms.gle/example"))
        self.assertFalse(valid_official_discovery_link(source, "https://www.facebook.com/example"))

    def test_regular_organizer_cannot_nominate_unrelated_external_site(self):
        source = {"url": "https://association.example.org/"}
        self.assertFalse(valid_official_discovery_link(source, "https://conference.example.net/2027"))

    def test_scholarly_sources_receive_safe_scan_defaults(self):
        sources = scholarly_organizer_sources({"scholarly_sources": [{
            "name": "Example Management Journal",
            "url": "https://journal.example.edu.tw/",
        }]})
        self.assertEqual(sources[0]["source_type"], "scholarly")
        self.assertEqual(sources[0]["attempts"], 1)

    def test_government_source_expands_all_configured_pages(self):
        sources = government_organizer_sources({"government_sources": [{
            "name": "NSTC",
            "urls": ["https://www.nstc.gov.tw/list?page=1", "https://www.nstc.gov.tw/list?page=2"],
        }]})
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[1]["source_type"], "government")
        self.assertEqual(sources[1]["attempts"], 1)

    def test_government_source_can_nominate_external_official_conference(self):
        source = {"url": "https://www.nstc.gov.tw/list", "source_type": "government"}
        self.assertTrue(valid_official_discovery_link(source, "https://conference.example.org/2027"))
        self.assertFalse(valid_official_discovery_link(source, "https://forms.gle/example"))

    @patch("scripts.update_conferences.fetch_url")
    @patch("scripts.update_conferences.current_year_markers", return_value=("2027", "116"))
    def test_scholarly_source_rejects_internal_overseas_conference_without_taiwan_marker(self, _markers, fetch):
        fetch.return_value = (
            '<a href="/news/1">2027 Management Conference, Kyoto University, Japan</a>',
            "utf-8",
        )
        candidates, errors = discover_from_organizers(
            [{
                "name": "Example Journal",
                "url": "https://journal.example.edu.tw/",
                "source_type": "scholarly",
                "require_taiwan_marker": True,
                "attempts": 1,
            }],
            set(),
            set(),
            set(),
        )
        self.assertEqual(errors, [])
        self.assertEqual(candidates, [])

    def test_duplicate_candidates_merge_independent_evidence(self):
        candidates = merge_discovered_candidates([
            {
                "id": "official-1",
                "title": "2027 國際財務管理研討會",
                "homepage_url": "https://conference.example.edu.tw/2027",
                "attention_notes": [],
                "evidence_sources": [{"name": "大學管理學院", "url": "https://management.example.edu.tw/"}],
            },
            {
                "id": "journal-1",
                "title": "2027國際財務管理研討會",
                "homepage_url": "https://journal.example.org.tw/news/1",
                "attention_notes": [],
                "evidence_sources": [{"name": "管理期刊", "url": "https://journal.example.org.tw/"}],
            },
        ])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["independent_source_count"], 2)
        self.assertTrue(candidates[0]["is_corroborated"])

    def test_similar_titles_from_different_years_do_not_merge(self):
        candidates = merge_discovered_candidates([
            {"id": "a", "title": "2026 財務管理研討會", "homepage_url": "https://example.org/2026"},
            {"id": "b", "title": "2027 財務管理研討會", "homepage_url": "https://example.org/2027"},
        ])
        self.assertEqual(len(candidates), 2)

    def test_call_for_papers_prefix_does_not_create_duplicate_candidate(self):
        candidates = merge_discovered_candidates([
            {
                "id": "a",
                "title": "Call for Papers: 2026 Three Asian Countries Finance Conference(2026/9/4)",
                "homepage_url": "https://finance.example.org/meeting/1",
            },
            {
                "id": "b",
                "title": "2026 Three Asian Countries Finance Conference(2026/9/4)",
                "homepage_url": "https://finance.example.org/news/1",
                "event_start": "2026-09-04",
            },
        ])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["title"], "2026 Three Asian Countries Finance Conference(2026/9/4)")
        self.assertEqual(candidates[0]["event_start"], "2026-09-04")

    @patch("scripts.update_conferences.fetch_url")
    @patch("scripts.update_conferences.current_year_markers", return_value=("2026", "115"))
    def test_university_external_candidate_keeps_discovery_source(self, _markers, fetch):
        fetch.return_value = (
            '<a href="https://conference.example.org/2026">2026 國際管理學術研討會</a>',
            "utf-8",
        )
        source_url = "https://management.example.edu.tw/"
        candidates, errors = discover_from_organizers(
            [{
                "name": "Example College of Management",
                "url": source_url,
                "source_type": "university_college",
                "attempts": 1,
            }],
            set(),
            set(),
            set(),
        )
        self.assertEqual(errors, [])
        self.assertEqual(candidates[0]["discovered_from_url"], source_url)

    @patch("scripts.update_conferences.fetch_url")
    @patch("scripts.update_conferences.current_year_markers", return_value=("2026", "115"))
    def test_government_candidate_strips_list_date_and_infers_single_event_date(self, _markers, fetch):
        fetch.return_value = (
            '<a href="/detail/1"><div>2026-06-08</div>'
            '<h3>管理創新國際研討會（115年7月24日、台北）</h3></a>',
            "utf-8",
        )
        candidates, errors = discover_from_organizers(
            [{
                "name": "NSTC",
                "url": "https://www.nstc.gov.tw/list",
                "source_type": "government",
                "attempts": 1,
            }],
            set(),
            set(),
            set(),
        )
        self.assertEqual(errors, [])
        self.assertEqual(candidates[0]["title"], "管理創新國際研討會（115年7月24日、台北）")
        self.assertEqual(candidates[0]["event_start"], "2026-07-24")
        self.assertEqual(candidates[0]["last_changed"], "2026-06-08")

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

    def test_afa_ics_keeps_future_taiwan_finance_conference(self):
        raw = """BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Taiwan Finance Conference 2027\nLOCATION:Taipei, Taiwan\nDTSTART;VALUE=DATE:20270710\nDTEND;VALUE=DATE:20270712\nURL:https://finance.example.org/2027\nDESCRIPTION:Annual conference in financial economics\nEND:VEVENT\nEND:VCALENDAR"""
        self.assertEqual(parse_ics_events(raw)[0]["summary"], "Taiwan Finance Conference 2027")
        with patch("scripts.update_conferences.today_iso", return_value="2026-06-19"):
            candidates = discover_from_ics_reference(
                {"name": "AFA Conference Calendar", "url": "https://afajof.org/conference-calendar/"},
                raw,
                set(),
                set(),
                set(),
            )
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["location"], "Taipei, Taiwan")
        self.assertEqual(candidates[0]["event_end"], "2027-07-11")


class ValidationTests(unittest.TestCase):
    def test_information_quality_uses_objective_completeness_criteria(self):
        item = {
            "review_status": "verified",
            "homepage_url": "https://conference.example.edu.tw/",
            "event_start": "2026-08-01",
            "location": "台北",
            "submission_url": "https://conference.example.edu.tw/submit",
            "submission_deadline": "2026-06-01",
            "fields": ["財金"],
            "presentation_formats": ["oral"],
            "presentation_languages": ["zh"],
            "registration_url": "https://conference.example.edu.tw/register",
            "registration_fee": "一般 NT$2,000",
        }
        quality = assess_information_quality(item)
        self.assertEqual(quality["score"], 5)
        self.assertEqual(quality["label"], "資訊很完整")

    def test_candidate_cannot_receive_verified_source_star(self):
        quality = assess_information_quality({
            "review_status": "candidate",
            "homepage_url": "https://example.edu.tw/event",
        })
        self.assertEqual(quality["score"], 0)

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
            "submission_deadline_previous": "2026/08/21",
            "acceptance_notification_date": "2026/09/11",
        }
        errors = validate_payload({"conferences": [item, dict(item)]})
        self.assertTrue(any("duplicate id" in error for error in errors))
        self.assertTrue(any("duplicate homepage_url" in error for error in errors))
        self.assertTrue(any("event_start is not ISO date" in error for error in errors))
        self.assertTrue(any("submission_deadline_previous is not ISO date" in error for error in errors))
        self.assertTrue(any("acceptance_notification_date is not ISO date" in error for error in errors))

    def test_publication_opportunity_requires_name_and_valid_urls(self):
        item = {
            "id": "publication",
            "title": "Conference",
            "organizer": "Organizer",
            "homepage_url": "https://example.com/event",
            "review_status": "verified",
            "publication_opportunities": [{"journal_name": "", "journal_url": "not-a-url"}],
        }
        errors = validate_payload({"conferences": [item]})
        self.assertTrue(any("journal_name is required" in error for error in errors))

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

    def test_infer_url_field_from_report_details(self):
        self.assertEqual(
            infer_correction_field({"details": "目前報名連結連到過去發表的論文"}),
            "registration_url",
        )

    @patch("scripts.process_feedback.fetch_url")
    def test_discovers_registration_link_on_same_official_domain(self, fetch):
        fetch.return_value = ("Registration for the conference is open", "utf-8")
        value, message = discover_official_url_correction(
            {
                "homepage_url": "https://iclt.info/paper/2023-024",
                "registration_url": "https://iclt.info/paper/2023-024",
            },
            "registration_url",
        )
        self.assertEqual(value, "https://iclt.info/registration")
        self.assertIn("官方網域", message)

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

    @patch("scripts.process_feedback.fetch_url", return_value=("註冊費：新台幣 2,000 元", "utf-8"))
    def test_fee_correction_requires_text_on_evidence_page(self, _fetch):
        valid, message = validate_correction(
            {"homepage_url": "https://nfu.edu.tw/event"},
            "registration_fee",
            "新台幣 2,000 元",
            "https://nfu.edu.tw/notice",
        )
        self.assertTrue(valid)
        self.assertIn("建議費用", message)

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
            self.assertIn("generated_at", rendered)
            self.assertEqual(rendered["conferences"][0]["last_changed"], process_feedback.today_iso())


if __name__ == "__main__":
    unittest.main()
