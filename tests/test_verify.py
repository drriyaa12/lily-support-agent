import copy
import json
import subprocess
import sys
import unittest

from tests.helpers import ROOT
from lily.verify import compare


def committed():
    return json.loads((ROOT / "results" / "heuristic-dev" / "results.json").read_text())


class CompareTests(unittest.TestCase):
    def test_identical_results_match_even_if_generated_at_another_time(self):
        a, b = committed(), committed()
        b["meta"]["generated"] = "2030-01-01 00:00 UTC"
        b["meta"]["command"] = "something else"
        self.assertEqual(compare(a, b), [])

    def test_a_changed_metric_is_reported(self):
        a, b = committed(), committed()
        b["metrics"]["agent"]["decision_correct"] += 1
        self.assertTrue(any("decision_correct" in p for p in compare(a, b)))

    def test_a_changed_decision_is_reported_with_its_case(self):
        a, b = committed(), committed()
        b["cases"][0]["agent"]["action"] = "escalate"
        self.assertTrue(any(a["cases"][0]["case_id"] in p for p in compare(a, b)))

    def test_edited_labels_are_reported(self):
        a, b = committed(), copy.deepcopy(committed())
        b["meta"]["cases_sha256"] = "0" * 64
        self.assertTrue(any("cases" in p.lower() for p in compare(a, b)))


class VerifyCommandTests(unittest.TestCase):
    def test_committed_results_are_reproducible(self):
        done = subprocess.run([sys.executable, "-m", "lily", "verify"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
