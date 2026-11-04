import unittest

from tests.helpers import make_ticket
from lily.agent import build_agent, build_baseline
from lily.heuristic import HeuristicAnalyzer


class SupportAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = build_agent(HeuristicAnalyzer())

    def test_routine_ticket_is_resolved_with_kb_steps(self):
        result = self.agent.handle(make_ticket(
            "Since yesterday, edits I make in the desktop app on my MacBook (macOS 15) aren't showing up for my "
            "teammates.", subject="Changes not showing up for teammates", created_at="2026-10-28T10:05:00Z"))
        self.assertEqual(result.decision.action, "resolve")
        self.assertEqual(result.cited_sources, ["KB-104"])
        self.assertIn("Reset the local cache", result.reply)
        self.assertIsNone(result.handoff)

    def test_exhausted_fixes_escalate_with_a_handoff(self):
        result = self.agent.handle(make_ticket(
            "Quillstack on my Windows 11 laptop hasn't synced for two days. I already updated to the latest "
            "version, signed out and back in, reset the local cache and even reinstalled the app. Still nothing "
            "syncs.", subject="Sync still broken", created_at="2026-10-30T13:00:00Z"))
        self.assertEqual((result.decision.action, result.decision.reason), ("escalate", "fixes_exhausted"))
        self.assertEqual(len(result.handoff.attempted_fixes), 4)

    def test_ticket_during_an_incident_points_to_the_incident(self):
        result = self.agent.handle(make_ticket(
            "Since this morning my changes in the desktop app take ages to show up for my colleagues. "
            "I'm on Windows 11.", subject="Changes not syncing today", created_at="2026-11-04T15:20:00Z"))
        self.assertEqual((result.decision.action, result.cited_sources), ("resolve", ["INC-2207"]))

    def test_conflict_escalation_cites_both_conflicting_articles(self):
        result = self.agent.handle(make_ticket(
            "We're on the Team plan. Uploading a 180 MB video fails every time in the browser. Is there a size "
            "limit?", subject="Large video won't upload", created_at="2026-10-25T10:15:00Z"))
        self.assertEqual(result.decision.reason, "conflicting_guidance")
        self.assertEqual(sorted(result.cited_sources), ["KB-105", "KB-106"])

    def test_transcript_includes_reply_and_decision_trace(self):
        result = self.agent.handle(make_ticket("How do I export the whole workspace for our audit?",
                                               subject="Export everything"))
        transcript = result.to_markdown()
        self.assertIn(result.reply.splitlines()[0], transcript)
        for line in result.decision.trace:
            self.assertIn(line, transcript)


class BaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = build_baseline()

    def test_resolves_with_every_step_of_the_top_match(self):
        result = self.baseline.handle(make_ticket(
            "Files I edit on my Mac (macOS 14) aren't syncing. I've updated the app and signed out and back in, "
            "but it didn't help.", subject="Desktop not syncing"))
        self.assertEqual(result.decision.action, "resolve")
        self.assertEqual([s.number for s in result.decision.steps], [1, 2, 3, 4])

    def test_baseline_replies_and_handoffs_are_not_signed_by_lily(self):
        resolved = self.baseline.handle(make_ticket("How do I export the whole workspace?", subject="Export"))
        escalated = self.baseline.handle(make_ticket(
            "Our IT team needs SAML single sign-on through our identity provider before rollout.", subject="SSO"))
        self.assertNotIn("Lily", resolved.reply)
        self.assertNotIn("Lily", escalated.handoff.to_markdown())

    def test_escalates_when_nothing_matches(self):
        result = self.baseline.handle(make_ticket(
            "Our IT team needs SAML single sign-on through our identity provider before rollout.",
            subject="SAML single sign-on?"))
        self.assertEqual(result.decision.action, "escalate")
        self.assertIsNotNone(result.handoff)


if __name__ == "__main__":
    unittest.main()
