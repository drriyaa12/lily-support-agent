import unittest
from datetime import datetime, timezone

from tests.helpers import make_article as article, make_investigation as investigation
from triage.models import AttemptedStep, Conflict
from triage.policy import decide
from triage.status import Incident


def attempts(article_id, *steps):
    return [AttemptedStep(article_id, n, "customer_reported", "tried it") for n in steps]


INCIDENT = Incident("INC-1", "sync", "Slow sync", "investigating", datetime(2026, 1, 1, tzinfo=timezone.utc), None,
                    "Sync is delayed.")
CONFLICT = Conflict("limit_mb", "KB-1", "100", "KB-2", "250", True, "180 MB falls between")


class PolicyRuleTests(unittest.TestCase):
    def test_analysis_error_escalates(self):
        d = decide(investigation([article()], error="model refused"))
        self.assertEqual((d.action, d.reason), ("escalate", "analysis_error"))

    def test_always_escalate_article(self):
        d = decide(investigation([article(escalate="always", required=["os"])], incidents=[INCIDENT]))
        self.assertEqual((d.action, d.reason), ("escalate", "policy_escalation"))

    def test_vague_ticket_asks_for_details(self):
        d = decide(investigation([], low_information=True))
        self.assertEqual((d.action, d.reason, d.missing_info), ("clarify", "low_information", ["issue_details"]))

    def test_no_relevant_article_escalates(self):
        d = decide(investigation([]))
        self.assertEqual((d.action, d.reason), ("escalate", "no_kb_coverage"))

    def test_active_incident_comes_before_missing_info(self):
        d = decide(investigation([article(required=["os"])], incidents=[INCIDENT]))
        self.assertEqual((d.action, d.reason, d.incident.id), ("resolve", "known_incident", "INC-1"))

    def test_conflict_that_matters_escalates(self):
        d = decide(investigation([article("KB-1"), article("KB-2")], conflicts=[CONFLICT]))
        self.assertEqual((d.action, d.reason), ("escalate", "conflicting_guidance"))

    def test_conflict_that_does_not_matter_is_ignored(self):
        harmless = Conflict("limit_mb", "KB-1", "100", "KB-2", "250", False, "40 MB is under both")
        d = decide(investigation([article("KB-1"), article("KB-2")], conflicts=[harmless]))
        self.assertEqual((d.action, d.reason), ("resolve", "supported_fix"))

    def test_asks_only_for_missing_required_info(self):
        d = decide(investigation([article(required=["os", "app_version"])], provided={"app_version": "4.6.2"}))
        self.assertEqual((d.action, d.reason, d.missing_info), ("clarify", "missing_info", ["os"]))

    def test_all_steps_tried_escalates(self):
        d = decide(investigation([article()], attempted=attempts("KB-1", 1, 2, 3, 4)))
        self.assertEqual((d.action, d.reason), ("escalate", "fixes_exhausted"))

    def test_offers_only_untried_steps(self):
        d = decide(investigation([article()], attempted=attempts("KB-1", 1, 2)))
        self.assertEqual((d.action, d.reason), ("resolve", "supported_fix"))
        self.assertEqual([s.number for s in d.steps], [3, 4])

    def test_attempts_on_another_article_do_not_count(self):
        d = decide(investigation([article("KB-1"), article("KB-2")], attempted=attempts("KB-2", 1, 2, 3, 4)))
        self.assertEqual([s.number for s in d.steps], [1, 2, 3, 4])

    def test_resolution_needs_verified_evidence(self):
        d = decide(investigation([article()], evidence=[]))
        self.assertEqual((d.action, d.reason), ("escalate", "ungrounded_evidence"))

    def test_article_without_steps_resolves_with_its_text(self):
        d = decide(investigation([article(steps=0)]))
        self.assertEqual((d.action, d.reason, d.steps), ("resolve", "supported_fix", []))


if __name__ == "__main__":
    unittest.main()
