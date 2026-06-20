import json
import unittest
from pathlib import Path
from urllib.parse import urlparse


class GrantDataTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "data" / "grants.json"
        self.payload = json.loads(path.read_text(encoding="utf-8"))

    def test_grants_have_status_workflow_and_official_links(self):
        programs = self.payload["programs"]
        self.assertTrue(any(program["status"] == "active" for program in programs))
        self.assertTrue(any(program["status"] == "archived" for program in programs))
        for program in programs:
            self.assertTrue(program["steps"])
            self.assertTrue(program["documents"])
            for link in program["links"]:
                parsed = urlparse(link["url"])
                self.assertIn(parsed.scheme, {"http", "https"})
                self.assertTrue(parsed.netloc)

    def test_archived_nfu_programs_are_not_presented_as_current(self):
        archived = [program for program in self.payload["programs"] if program["status"] == "archived"]
        self.assertEqual(len(archived), 2)
        self.assertTrue(all("歷史資料" in program["status_label"] for program in archived))
        self.assertTrue(all("截止" in " ".join(program["deadline"]) for program in archived))

    def test_nstc_is_first_priority_and_has_english_student_guidance(self):
        programs = sorted(self.payload["programs"], key=lambda program: program["priority"])
        nstc = programs[0]
        self.assertEqual(nstc["id"], "nstc-graduate-international-conference")
        self.assertIn("第一順位", nstc["priority_note"])
        guide = nstc["international_student_guide"]
        self.assertIn("international graduate students", guide["title"])
        self.assertTrue(any("nationality restriction" in text for text in [guide["summary"], *guide["points"]]))

    def test_current_nfu_skill_award_covers_conference_awards_with_caveat(self):
        program = next(
            program
            for program in self.payload["programs"]
            if program["id"] == "nfu-2026-skill-competition-award"
        )
        self.assertEqual(program["status"], "current")
        self.assertIn("第一期已截止", program["status_label"])
        combined = " ".join(
            [program["summary"], *program["eligibility"], *program["cautions"]]
        )
        self.assertIn("最佳論文", combined)
        self.assertIn("不一定", combined)
        self.assertTrue(any("eCare" in step for step in program["steps"]))
        self.assertTrue(any("本人郵局" in document for document in program["documents"]))

    def test_grants_use_a_separate_accessible_page_tab(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "index.html").read_text(encoding="utf-8")
        script = (root / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn('role="tablist"', html)
        self.assertIn('aria-controls="grants"', html)
        self.assertIn('id="grants" class="grants-section" role="tabpanel"', html)
        self.assertIn("function setActiveTab", script)
        self.assertIn('window.location.hash === "#grants"', script)

    def test_every_program_has_complete_english_application_information(self):
        required = {
            "status_label",
            "provider",
            "title",
            "summary",
            "eligibility",
            "funding",
            "deadline",
            "documents",
            "steps",
            "cautions",
        }
        self.assertTrue(self.payload["notice_en"])
        for program in self.payload["programs"]:
            english = program["english"]
            self.assertTrue(required.issubset(english))
            for field in required - {"status_label", "provider", "title", "summary"}:
                self.assertTrue(english[field], f"{program['id']} has empty English {field}")
            self.assertTrue(all(link.get("label_en") for link in program["links"]))

    def test_grant_language_switch_is_wired(self):
        root = Path(__file__).resolve().parents[1]
        html = (root / "index.html").read_text(encoding="utf-8")
        script = (root / "assets" / "app.js").read_text(encoding="utf-8")
        self.assertIn('data-grant-language="en"', html)
        self.assertIn('aria-pressed="false">English', html)
        self.assertIn('state.grantLanguage === "en"', script)
        self.assertIn("program.english", script)

    def test_current_programs_expose_direct_application_portals(self):
        programs = {program["id"]: program for program in self.payload["programs"]}
        nstc_urls = {link["url"] for link in programs["nstc-graduate-international-conference"]["links"]}
        skill_urls = {link["url"] for link in programs["nfu-2026-skill-competition-award"]["links"]}
        self.assertIn("https://arspb.nstc.gov.tw/NSCWeb/slogin.jsp", nstc_urls)
        self.assertIn("https://ecare.nfu.edu.tw/", skill_urls)
        for program_id in ("nstc-graduate-international-conference", "nfu-2026-skill-competition-award"):
            application_links = [
                link for link in programs[program_id]["links"] if link["label_en"].startswith("Apply online:")
            ]
            self.assertEqual(len(application_links), 1)


if __name__ == "__main__":
    unittest.main()
