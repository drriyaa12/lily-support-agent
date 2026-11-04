import unittest
from datetime import datetime, timezone

from tests.helpers import make_ticket, real_kb
from triage.investigator import Investigator, fact_conflicts
from triage.kb import parse_article
from triage.models import Analysis, AttemptedStep, Evidence
from triage.retrieval import BM25Index
from triage.status import Incident


class FactConflictTests(unittest.TestCase):
    def setUp(self):
        self.kb = real_kb()

    def conflicts(self, ids, text):
        return fact_conflicts([self.kb[i] for i in ids], text)

    def test_numeric_conflict_matters_when_value_falls_between_limits(self):
        found = self.conflicts(["KB-105", "KB-106"], "Uploading a 180 MB video fails every time.")
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].matters)

    def test_numeric_conflict_ignored_when_both_limits_agree(self):
        found = self.conflicts(["KB-105", "KB-106"], "Uploading a 40 MB file fails every time.")
        self.assertFalse(found[0].matters)

    def test_refund_window_boundaries(self):
        for text, expected in [
            ("We were charged 20 days ago, can we get a refund?", True),
            ("We were charged 3 days ago, can we get a refund?", False),
            ("We were charged 45 days ago, can we get a refund?", False),
        ]:
            with self.subTest(text=text):
                self.assertEqual(self.conflicts(["KB-202", "KB-203"], text)[0].matters, expected)

    def test_conflict_ignored_when_ticket_is_not_about_the_fact(self):
        found = self.conflicts(["KB-202", "KB-203"], "Could we get that charge refunded?")
        self.assertFalse(found[0].matters)

    def test_non_numeric_conflict_matters_when_ticket_raises_it(self):
        found = self.conflicts(["KB-302", "KB-303"], "I'm an admin. Are admins allowed to remove members?")
        self.assertTrue(found[0].matters)

    def test_agreeing_articles_do_not_conflict(self):
        a = parse_article("---\nid: X-1\ntitle: A\ncomponent: c\nfact: limit_mb = 5\n---\nBody.\n")
        b = parse_article("---\nid: X-2\ntitle: B\ncomponent: c\nfact: limit_mb = 5\n---\nBody.\n")
        self.assertEqual(fact_conflicts([a, b], "a 10 MB limit"), [])


class FixedAnalyzer:
    """Returns a prepared Analysis, standing in for a model whose output we want to police."""

    name = "fixed"

    def __init__(self, analysis):
        self.analysis = analysis

    def analyze(self, ticket, candidates):
        return self.analysis


class InvestigatorGuardrailTests(unittest.TestCase):
    def setUp(self):
        self.kb = real_kb()
        self.index = BM25Index(self.kb.values())
        self.ticket = make_ticket("My desktop app on Windows 11 is stuck syncing and edits don't reach the team.",
                                  subject="Desktop sync stuck", created_at="2026-10-29T09:30:00Z")
        self.incident = Incident("INC-9", "sync", "Slow sync", "investigating",
                                 datetime(2026, 10, 29, 8, 0, tzinfo=timezone.utc), None, "We are on it.")

    def investigate(self, **analysis_fields):
        fields = dict(source="fixed", summary="s", core_issue="c", relevant_ids=["KB-104"])
        fields.update(analysis_fields)
        investigator = Investigator(self.kb, self.index, [self.incident], FixedAnalyzer(Analysis(**fields)))
        return investigator.investigate(self.ticket)

    def test_drops_quotes_not_found_in_the_article(self):
        inv = self.investigate(evidence=[
            Evidence("KB-104", "Choose Settings → Advanced → Reset local cache.", "real"),
            Evidence("KB-104", "Sync problems are always caused by antivirus software.", "invented"),
        ])
        self.assertEqual([e.supports for e in inv.evidence], ["real"])

    def test_drops_relevant_ids_that_were_not_retrieved(self):
        inv = self.investigate(relevant_ids=["KB-104", "KB-999", "KB-402"])
        self.assertEqual([a.id for a in inv.relevant], ["KB-104"])

    def test_drops_provided_info_that_is_not_in_the_ticket(self):
        inv = self.investigate(provided_info={"app_version": "4.9.1"})
        self.assertNotIn("app_version", inv.provided_info)

    def test_merges_pattern_matched_info(self):
        inv = self.investigate(provided_info={})
        self.assertEqual(inv.provided_info.get("os"), "Windows 11")

    def test_drops_attempted_steps_that_do_not_exist(self):
        inv = self.investigate(attempted=[
            AttemptedStep("KB-104", 2, "customer_reported", "signed out"),
            AttemptedStep("KB-104", 9, "customer_reported", "made up"),
        ])
        self.assertEqual([a.step for a in inv.attempted], [2])

    def test_attaches_active_incident_for_best_article_component(self):
        self.assertEqual([i.id for i in self.investigate().incidents], ["INC-9"])


if __name__ == "__main__":
    unittest.main()
