import unittest

from tests.helpers import real_kb
from triage.kb import parse_article
from triage.retrieval import BM25Index


def article(aid, title, body):
    return parse_article(f"---\nid: {aid}\ntitle: {title}\ncomponent: test\n---\n{body}\n")


class BM25IndexTests(unittest.TestCase):
    def setUp(self):
        self.index = BM25Index([
            article("A1", "Resetting your password", "Request a reset link from the sign-in page."),
            article("A2", "Exporting data", "Create an export archive of documents."),
            article("A3", "Billing overview", "Invoices and payment methods. You can export invoices."),
        ])

    def test_ranks_the_matching_article_first(self):
        results = self.index.search("I forgot my password, how do I reset it?")
        self.assertEqual(results[0].article.id, "A1")

    def test_title_match_outranks_body_mention(self):
        results = self.index.search("export")
        self.assertEqual([r.article.id for r in results], ["A2", "A3"])

    def test_unrelated_query_returns_nothing(self):
        self.assertEqual(self.index.search("quarterly tax filing deadline"), [])

    def test_k_limits_results(self):
        self.assertEqual(len(self.index.search("export invoices password", k=2)), 2)


class RealKbRetrievalTests(unittest.TestCase):
    def test_password_question_finds_reset_article(self):
        index = BM25Index(real_kb().values())
        results = index.search("I forgot my password and can't log in")
        self.assertEqual(results[0].article.id, "KB-101")


if __name__ == "__main__":
    unittest.main()
