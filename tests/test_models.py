import unittest
from datetime import datetime, timedelta, timezone

from tests.helpers import make_ticket
from lily.models import Ticket, parse_time


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


class RobustnessTests(unittest.TestCase):
    """Review findings: blank fields crashed, and some timestamp forms failed or were not UTC."""

    def test_null_fields_get_safe_defaults(self):
        t = Ticket.from_dict({"id": "T-1", "created_at": "2026-11-04T15:20:00Z", "customer": None,
                              "subject": None, "messages": [{"role": "customer", "text": None}]})
        self.assertEqual((t.first_name, t.subject, t.customer_messages), ("there", "", [""]))

    def test_blank_name_falls_back_to_there(self):
        self.assertEqual(make_ticket("x", name="   ").first_name, "there")

    def test_timestamps_are_normalised_to_utc(self):
        for text, expected in [
            ("2026-11-04T15:20:00", datetime(2026, 11, 4, 15, 20, tzinfo=timezone.utc)),
            ("2026-11-04T17:20:00+0200", datetime(2026, 11, 4, 15, 20, tzinfo=timezone.utc)),
            ("2026-11-04T15:20:00.5Z", datetime(2026, 11, 4, 15, 20, 0, 500000, tzinfo=timezone.utc)),
        ]:
            with self.subTest(text=text):
                parsed = parse_time(text)
                self.assertEqual(parsed, expected)
                self.assertEqual(parsed.utcoffset(), timedelta(0))


if __name__ == "__main__":
    unittest.main()
