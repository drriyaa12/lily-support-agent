import unittest

from tests.helpers import make_ticket, real_kb
from lily.heuristic import HeuristicAnalyzer, find_attempts, is_low_information, reports_failure, summarize
from lily.retrieval import BM25Index
from lily.text import normalise_quote


def steps_of(attempts):
    return sorted(a.step for a in attempts)


class FindAttemptsTests(unittest.TestCase):
    def setUp(self):
        self.kb = real_kb()

    def test_customer_listing_every_step(self):
        t = make_ticket("I already updated to the latest version, signed out and back in, reset the local "
                        "cache and even reinstalled the app. Still nothing syncs.")
        attempts = find_attempts(t, self.kb["KB-104"])
        self.assertEqual(steps_of(attempts), [1, 2, 3, 4])
        self.assertEqual({a.how for a in attempts}, {"customer_reported"})

    def test_customer_listing_some_steps(self):
        t = make_ticket("I've updated the app and signed out and back in, but it didn't help.")
        self.assertEqual(steps_of(find_attempts(t, self.kb["KB-104"])), [1, 2])

    def test_symptoms_are_not_attempts(self):
        t = make_ticket("Since yesterday, edits I make in the desktop app aren't showing up for my "
                        "teammates. The app just says Syncing forever.")
        self.assertEqual(find_attempts(t, self.kb["KB-104"]), [])

    def test_original_invitation_is_not_a_resend(self):
        t = make_ticket("I invited our new designer two days ago, but she says the invitation never arrived.")
        self.assertEqual(find_attempts(t, self.kb["KB-301"]), [])

    def test_steps_we_suggested_count_once_customer_reports_failure(self):
        t = make_ticket(
            "The password reset email never arrives.",
            ("agent", "Please check your spam folder and mail filters, then request a new link. "
                      "Only the newest link works, and it expires after 30 minutes."),
            "Still nothing.",
        )
        attempts = find_attempts(t, self.kb["KB-101"])
        self.assertEqual(steps_of(attempts), [1, 2, 3])
        self.assertEqual({a.how for a in attempts}, {"suggested_earlier"})

    def test_steps_we_suggested_do_not_count_without_failure_report(self):
        t = make_ticket(
            "The password reset email never arrives.",
            ("agent", "Please check your spam folder and mail filters, then request a new link."),
            "Thanks, I will look tomorrow.",
        )
        self.assertEqual(find_attempts(t, self.kb["KB-101"]), [])

    def test_missing_prerequisites_make_steps_impossible(self):
        t = make_ticket("I lost my phone. I don't have my backup codes and I'm not signed in on any other device.")
        attempts = find_attempts(t, self.kb["KB-102"])
        self.assertEqual(steps_of(attempts), [1, 2])
        self.assertEqual({a.how for a in attempts}, {"not_possible"})


class SignalTests(unittest.TestCase):
    def test_reports_failure(self):
        for text, expected in [
            ("Still nothing.", True),
            ("I tried that but it didn't work", True),
            ("Deliveries still fail.", True),
            ("How do I export my workspace?", False),
        ]:
            with self.subTest(text=text):
                self.assertEqual(reports_failure(text), expected)

    def test_low_information(self):
        self.assertTrue(is_low_information(make_ticket("Nothing works since the update. Please fix this asap.",
                                                       subject="Urgent!!")))
        self.assertFalse(is_low_information(make_ticket(
            "Since yesterday, edits I make in the desktop app on my MacBook aren't showing up for my teammates.",
            subject="Changes not showing up")))


class HeuristicAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.kb = real_kb()
        self.index = BM25Index(self.kb.values())
        self.analyzer = HeuristicAnalyzer()

    def analyze(self, ticket):
        return self.analyzer.analyze(ticket, self.index.search(ticket.customer_text))

    def test_unrelated_request_has_no_relevant_articles(self):
        t = make_ticket("Our IT team wants to roll out to 300 people, but only if we can enforce SAML single "
                        "sign-on through our identity provider. Is that supported?", subject="SAML single sign-on?")
        analysis = self.analyze(t)
        self.assertEqual(analysis.relevant_ids, [])
        self.assertFalse(analysis.low_information)

    def test_vague_ticket_is_low_information(self):
        analysis = self.analyze(make_ticket("Nothing works since the update. Please fix this asap.",
                                            subject="Urgent!!"))
        self.assertTrue(analysis.low_information)

    def test_prefers_procedure_over_faq_when_scores_are_close(self):
        t = make_ticket("We were charged for another month even though we meant to cancel. "
                        "Could we get that charge refunded?", subject="Refund please")
        self.assertEqual(self.analyze(t).relevant_ids[0], "KB-202")

    def test_evidence_is_quoted_verbatim_from_the_best_article(self):
        t = make_ticket("Since yesterday, edits I make in the desktop app on my MacBook (macOS 15) aren't "
                        "showing up for my teammates.", subject="Changes not showing up for teammates")
        analysis = self.analyze(t)
        self.assertEqual(analysis.evidence[0].source_id, "KB-104")
        self.assertIn(normalise_quote(analysis.evidence[0].quote), normalise_quote(self.kb["KB-104"].text))
        self.assertEqual(analysis.provided_info.get("os"), "macOS 15")


class AttemptFalsePositiveTests(unittest.TestCase):
    """Review finding: statements of need, questions and incidental words were read as attempts."""

    def setUp(self):
        self.kb = real_kb()

    def test_statements_of_need_are_not_attempts(self):
        t = make_ticket("Our card payment failed and I need to update the payment method for our workspace "
                        "subscription. How do I replace the card?")
        self.assertEqual(find_attempts(t, self.kb["KB-201"]), [])

    def test_questions_about_steps_are_not_attempts(self):
        t = make_ticket("Do I need to update to the latest version, sign out and back in, reset the local cache "
                        "or reinstall the app?")
        self.assertEqual(find_attempts(t, self.kb["KB-104"]), [])

    def test_a_question_that_reports_an_attempt_still_counts(self):
        t = make_ticket("I've already reinstalled the app, what else can I do?")
        self.assertEqual(steps_of(find_attempts(t, self.kb["KB-104"])), [4])

    def test_plan_names_and_time_units_do_not_identify_a_step(self):
        t = make_ticket("We upgraded to the annual Business plan 20 days ago, but it turns out we don't need it.")
        self.assertEqual(find_attempts(t, self.kb["KB-202"]), [])

    def test_a_sync_log_is_not_signing_out(self):
        t = make_ticket("I already attached the sync log to my last email.")
        self.assertEqual(find_attempts(t, self.kb["KB-104"]), [])

    def test_summary_survives_an_empty_latest_message(self):
        self.assertNotIn("Latest message", summarize(make_ticket("My desktop app is not syncing.", "")))


if __name__ == "__main__":
    unittest.main()
