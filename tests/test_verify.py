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


class VerifyCoverageTests(unittest.TestCase):
    """Review findings: verify must notice stale transcripts and reports, and ignore line endings."""

    def test_a_stale_transcript_is_reported(self):
        import shutil
        import tempfile
        from pathlib import Path
        from lily.verify import verify

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for part in ("data", "eval", "results", "docs"):
                shutil.copytree(ROOT / part, root / part)
            transcript = root / "results" / "heuristic-dev" / "transcripts" / "C05.md"
            transcript.write_text(transcript.read_text() + "\nedited by hand\n")
            problems = verify(root)
        self.assertTrue(any("C05.md" in p for p in problems), problems)

    def test_line_endings_do_not_change_the_labels_hash(self):
        import tempfile
        from pathlib import Path
        from lily.evaluate import build_meta

        with tempfile.TemporaryDirectory() as tmp:
            lf, crlf = Path(tmp) / "lf.json", Path(tmp) / "crlf.json"
            lf.write_bytes(b'[\n  {"a": 1}\n]\n')
            crlf.write_bytes(b'[\r\n  {"a": 1}\r\n]\r\n')
            self.assertEqual(build_meta(lf, "h", "d", "c")["cases_sha256"], build_meta(crlf, "h", "d", "c")["cases_sha256"])


if __name__ == "__main__":
    unittest.main()
