import json
import unittest
from pathlib import Path


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.payload = json.loads((self.root / "data" / "conferences.json").read_text(encoding="utf-8"))

    def test_dashboard_markup_and_monthly_count_logic_are_present(self):
        html = (self.root / "index.html").read_text(encoding="utf-8")
        script = (self.root / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn('id="dashboardYear"', html)
        self.assertIn('id="dashboardScope"', html)
        self.assertIn('id="monthlyChart"', html)
        self.assertIn('id="dashboardCompleteness"', html)
        self.assertIn("function monthlyConferenceCounts", script)
        self.assertIn("function dashboardCompletenessLabel", script)
        self.assertIn("年度資料仍在回填中", script)
        self.assertIn("submission_deadline", script)
        self.assertIn("event_start", script)
        self.assertIn("function acceptanceCalendarLink", script)
        self.assertIn("calendar.google.com/calendar/render", script)
        self.assertIn("審查結果通知", script)
        self.assertIn("function renderDateTimeline", script)
        self.assertIn("function nextImportantMilestone", script)
        self.assertIn("function toggleTracked", script)
        self.assertIn("twconferences.trackedIds", script)
        self.assertIn('id="trackedOnlyFilter"', html)
        self.assertIn('els.dashboardScope?.value === "all" ? verified : state.filtered', script)
        self.assertIn('els.dashboardScope?.addEventListener("change", renderMonthlyDashboard)', script)
        self.assertIn("function locationCityLabel", script)
        self.assertIn("locationCityLabel(item.location) === location", script)
        self.assertIn("state.activeConferences.map((item) => locationCityLabel(item.location))", script)

    def test_verified_data_can_populate_both_dashboard_series(self):
        verified = [item for item in self.payload["conferences"] if item.get("review_status") != "candidate"]
        event_dates = [item["event_start"] for item in verified if item.get("event_start")]
        deadlines = [item["submission_deadline"] for item in verified if item.get("submission_deadline")]
        self.assertTrue(event_dates)
        self.assertTrue(deadlines)
        self.assertTrue(all(len(value) >= 7 for value in event_dates + deadlines))

    def test_acceptance_notification_date_can_drive_calendar_reminder(self):
        stust = next(
            item for item in self.payload["conferences"]
            if item.get("id") == "stust-2026-knowledge-global-management"
        )
        self.assertEqual(stust["acceptance_notification_date"], "2026-09-11")

    def test_2026_backfill_leads_are_tracked_outside_formal_statistics(self):
        leads_payload = json.loads((self.root / "data" / "backfill_2026_leads.json").read_text(encoding="utf-8"))
        lead_ids = {item["id"] for item in leads_payload["leads"]}
        formal_ids = {
            item["id"]
            for item in self.payload["conferences"]
            if item.get("review_status") != "candidate"
        }
        self.assertTrue(leads_payload["leads"])
        self.assertTrue(all(item["review_status"].startswith("needs_") for item in leads_payload["leads"]))
        self.assertFalse(lead_ids & formal_ids)
        self.assertTrue(all(item.get("official_url") or item.get("discovery_url") for item in leads_payload["leads"]))


if __name__ == "__main__":
    unittest.main()
