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


if __name__ == "__main__":
    unittest.main()
