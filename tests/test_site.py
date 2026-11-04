import json
import re
import unittest

from tests.helpers import ROOT
from lily.site import build_site_data, render_site


def embedded_data(html):
    block = re.search(r'<script type="application/json" id="lily-data">(.*?)</script>', html, re.S).group(1)
    return json.loads(block)


class SiteDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = build_site_data(ROOT)

    def test_every_case_from_both_sets_is_on_the_page(self):
        dev = json.loads((ROOT / "eval" / "cases.json").read_text())
        held = json.loads((ROOT / "eval" / "heldout_cases.json").read_text())
        self.assertEqual([c["id"] for c in self.data["cases"]], [c["case_id"] for c in dev + held])

    def test_headline_numbers_match_the_published_results(self):
        for split, folder in (("development", "heuristic-dev"), ("held-out", "heuristic-heldout")):
            published = json.loads((ROOT / "results" / folder / "results.json").read_text())["metrics"]
            with self.subTest(split=split):
                self.assertEqual(self.data["sets"][split]["lily_correct"], published["agent"]["decision_correct"])
                self.assertEqual(self.data["sets"][split]["baseline_correct"], published["baseline"]["decision_correct"])

    def test_each_case_carries_what_the_page_shows(self):
        case = next(c for c in self.data["cases"] if c["id"] == "C17")
        self.assertEqual((case["expected"]["decision"], case["lily"]["action"], case["baseline"]["action"]),
                         ("escalate", "escalate", "resolve"))
        self.assertTrue(case["lily"]["trace"] and case["lily"]["checked"] and case["lily"]["handoff"])
        self.assertTrue(case["messages"])


class RenderTests(unittest.TestCase):
    def test_ticket_text_cannot_break_out_of_the_data_block(self):
        data = {"sets": {}, "articles": {}, "cases": [{"id": "X1", "subject": "</script><script>alert(1)</script>"}]}
        html = render_site(data)
        self.assertNotIn("</script><script>alert(1)", html)
        self.assertEqual(embedded_data(html), data)

    def test_published_page_is_up_to_date(self):
        published = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(published, render_site(build_site_data(ROOT)), "run: python3 -m lily site")


class VerdictTests(unittest.TestCase):
    """Review finding: the page counted decisions in its headline but judged replies in its rows."""

    @classmethod
    def setUpClass(cls):
        cls.data = build_site_data(ROOT)

    def case(self, case_id):
        return next(c for c in self.data["cases"] if c["id"] == case_id)

    def test_a_right_decision_with_a_flawed_reply_is_marked_as_such(self):
        baseline = self.case("C18")["baseline"]
        self.assertEqual((baseline["right_decision"], baseline["good"]), (True, False))
        self.assertFalse(self.case("C25")["lily"]["right_decision"])

    def test_headline_counts_the_same_verdicts_the_rows_show(self):
        for split in ("development", "held-out"):
            cases = [c for c in self.data["cases"] if c["set"] == split]
            with self.subTest(split=split):
                self.assertEqual(self.data["sets"][split]["lily_correct"], sum(c["lily"]["right_decision"] for c in cases))
                self.assertEqual(self.data["sets"][split]["baseline_correct"],
                                 sum(c["baseline"]["right_decision"] for c in cases))


if __name__ == "__main__":
    unittest.main()
