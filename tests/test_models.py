import unittest
from datetime import datetime, timezone

from tests.helpers import make_ticket


class TicketTests(unittest.TestCase):
    def test_customer_text_excludes_agent_messages(self):
        # Retrieval and attempt detection must not treat our own replies as the customer's words.
        t = make_ticket("My sync is broken.", ("agent", "Try resetting the cache."), "Still broken.",
                        subject="Sync")
        self.assertIn("My sync is broken.", t.customer_text)
        self.assertIn("Still broken.", t.customer_text)
        self.assertNotIn("resetting", t.customer_text)

    def test_created_at_is_timezone_aware(self):
        t = make_ticket("x", created_at="2026-11-04T15:20:00Z")
        self.assertEqual(t.created_at, datetime(2026, 11, 4, 15, 20, tzinfo=timezone.utc))

    def test_first_name(self):
        self.assertEqual(make_ticket("x", name="Priya N.").first_name, "Priya")


if __name__ == "__main__":
    unittest.main()
