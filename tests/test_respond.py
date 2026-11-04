import unittest
from datetime import datetime, timezone

from tests.helpers import make_article, make_investigation
from lily.fields import FIELDS
from lily.models import AttemptedStep, Conflict
from lily.policy import decide
from lily.respond import SIGNATURE, build_handoff, compose_reply
from lily.status import Incident


def tried(article_id, *steps, how="customer_reported"):
    return [AttemptedStep(article_id, n, how, f"I did step {n}") for n in steps]


class ReplyTests(unittest.TestCase):
    def reply(self, inv):
        return compose_reply(decide(inv), inv)

    def test_resolution_lists_only_untried_steps_and_cites_the_article(self):
        text = self.reply(make_investigation([make_article()], attempted=tried("KB-1", 1, 2)))
        self.assertIn("Step 3", text)
        self.assertIn("Step 4", text)
        self.assertNotIn("Detail 1", text)
        self.assertIn("KB-1", text)

    def test_clarification_asks_for_each_missing_detail(self):
        text = self.reply(make_investigation([make_article(required=["os", "app_version"])]))
        self.assertIn(FIELDS["os"].question, text)
        self.assertIn(FIELDS["app_version"].question, text)
        self.assertNotIn("Detail 1", text)

    def test_incident_reply_shares_the_status_message_instead_of_steps(self):
        incident = Incident("INC-7", "sync", "Slow sync", "investigating",
                            datetime(2026, 1, 1, tzinfo=timezone.utc), None, "Sync is delayed by up to two hours.")
        text = self.reply(make_investigation([make_article()], incidents=[incident]))
        self.assertIn("Sync is delayed by up to two hours.", text)
        self.assertNotIn("Detail 1", text)

    def test_conflict_reply_does_not_pick_a_side(self):
        conflict = Conflict("max_upload_mb_paid", "KB-1", "100", "KB-2", "250", True, "180 MB falls between")
        text = self.reply(make_investigation([make_article("KB-1"), make_article("KB-2")], conflicts=[conflict]))
        self.assertNotIn("100", text)
        self.assertNotIn("250", text)

    def test_policy_escalation_offers_untried_interim_steps(self):
        inv = make_investigation([make_article(steps=2, escalate="always")], attempted=tried("KB-1", 1))
        text = self.reply(inv)
        self.assertIn("Detail 2", text)
        self.assertNotIn("Detail 1", text)


class HandoffTests(unittest.TestCase):
    def test_exhausted_fixes_handoff_carries_issue_attempts_and_questions(self):
        article = make_article()
        inv = make_investigation([article], attempted=tried("KB-1", 1, 2) + tried("KB-1", 3, 4, how="not_possible"))
        handoff = build_handoff(decide(inv), inv)
        self.assertEqual(handoff.queue, "Technical Support")
        self.assertEqual(handoff.summary, inv.analysis.summary)
        self.assertEqual(len(handoff.attempted_fixes), 4)
        self.assertIn("Step 3", handoff.attempted_fixes[2])
        self.assertTrue(handoff.unresolved_questions)
        self.assertEqual(handoff.suggested_next_step, "Escalate with logs.")

    def test_conflict_handoff_asks_which_value_is_right(self):
        conflict = Conflict("max_upload_mb_paid", "KB-1", "100", "KB-2", "250", True, "180 MB falls between")
        inv = make_investigation([make_article("KB-1"), make_article("KB-2")], conflicts=[conflict])
        questions = " ".join(build_handoff(decide(inv), inv).unresolved_questions)
        self.assertIn("100", questions)
        self.assertIn("250", questions)

    def test_markdown_keeps_every_attempt_and_question(self):
        inv = make_investigation([make_article()], attempted=tried("KB-1", 1, 2, 3, 4))
        handoff = build_handoff(decide(inv), inv)
        markdown = handoff.to_markdown()
        for line in handoff.attempted_fixes + handoff.unresolved_questions:
            self.assertIn(line, markdown)


class ImpossibleStepWordingTests(unittest.TestCase):
    def test_impossible_steps_are_not_called_tried(self):
        inv = make_investigation([make_article()],
                                 attempted=tried("KB-1", 1, how="not_possible") + tried("KB-1", 2))
        text = compose_reply(decide(inv), inv)
        self.assertIn("Thanks for already trying these: step 2.", text)
        self.assertIn("isn't possible for you: step 1.", text)
        self.assertNotIn("step 1, step 2", text)



class SignatureTests(unittest.TestCase):
    def test_every_reply_is_signed_by_lily_as_an_ai_assistant(self):
        self.assertIn("Lily", SIGNATURE)
        self.assertIn("AI", SIGNATURE)
        for inv in (make_investigation([make_article()]),                 # resolve
                    make_investigation([make_article(required=["os"])]),  # clarify
                    make_investigation([])):                              # escalate
            with self.subTest(action=decide(inv).action):
                self.assertTrue(compose_reply(decide(inv), inv).endswith(SIGNATURE))

    def test_handoff_says_who_prepared_it(self):
        inv = make_investigation([make_article()], attempted=tried("KB-1", 1, 2, 3, 4))
        self.assertIn("Prepared by Lily", build_handoff(decide(inv), inv).to_markdown())

if __name__ == "__main__":
    unittest.main()
