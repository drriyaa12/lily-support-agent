import unittest
from datetime import datetime

from tests.helpers import DATA
from triage.status import Incident, active_incidents, load_status


def at(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


class IncidentTests(unittest.TestCase):
    def setUp(self):
        self.open = Incident("INC-1", "sync", "Slow sync", "investigating",
                             at("2026-11-04T08:10:00Z"), None, "We are on it.")
        self.closed = Incident("INC-2", "integrations", "Webhooks", "resolved",
                               at("2026-10-20T09:00:00Z"), at("2026-10-20T13:30:00Z"), "Fixed.")

    def test_open_incident_is_active_after_start_only(self):
        self.assertTrue(self.open.active_at(at("2026-11-04T15:20:00Z")))
        self.assertFalse(self.open.active_at(at("2026-11-04T08:00:00Z")))

    def test_resolved_incident_is_inactive_afterwards(self):
        self.assertTrue(self.closed.active_at(at("2026-10-20T10:00:00Z")))
        self.assertFalse(self.closed.active_at(at("2026-10-27T13:45:00Z")))

    def test_active_incidents_filters_by_component_and_time(self):
        incidents = [self.open, self.closed]
        when = at("2026-11-04T15:20:00Z")
        self.assertEqual([i.id for i in active_incidents(incidents, "sync", when)], ["INC-1"])
        self.assertEqual(active_incidents(incidents, "integrations", when), [])

    def test_loads_repository_status_file(self):
        incidents = load_status(DATA / "status.json")
        self.assertIn("INC-2207", [i.id for i in incidents])


if __name__ == "__main__":
    unittest.main()
