import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ROOT, make_article, make_investigation
from triage.evaluate import score, summarize
from triage.models import AttemptedStep
from triage.policy import Decision
from triage.result import Result


def result(action, reason, article_id="KB-1", steps=(), missing=(), attempted=()):
    article = make_article(article_id)
    decision = Decision(action, reason, "x", article=article, steps=[article.step(n) for n in steps],
                        missing_info=list(missing))
    inv = make_investigation([article], attempted=attempted)
    return Result("agent", inv.ticket, inv, decision, "reply", None)


def expected(decision, reason="supported_fix", evidence=("KB-1",), missing=(), attempted=None):
    return {"decision": decision, "reason": reason, "evidence_any": list(evidence), "missing_info": list(missing),
            "attempted_steps": attempted or {}}


class ScoreTests(unittest.TestCase):
    CASES = [
        # (description, expected, result, outcome)
        ("right source", expected("resolve"), result("resolve", "supported_fix", steps=[1, 2]),
         "correct_resolution"),
        ("wrong source", expected("resolve"), result("resolve", "supported_fix", "KB-2", steps=[1]),
         "incorrect_resolution"),
        ("repeats a failed step", expected("resolve", attempted={"KB-1": [1]}),
         result("resolve", "supported_fix", steps=[1, 2]), "incorrect_resolution"),
        ("resolves an escalation", expected("escalate", "fixes_exhausted"), result("resolve", "supported_fix"),
         "incorrect_resolution"),
        ("escalates an escalation", expected("escalate", "fixes_exhausted"), result("escalate", "no_kb_coverage"),
         "appropriate_escalation"),
        ("escalates a routine case", expected("resolve"), result("escalate", "fixes_exhausted"),
         "unnecessary_escalation"),
        ("escalates a question", expected("clarify", "missing_info", missing=["os"]),
         result("escalate", "fixes_exhausted"), "unnecessary_escalation"),
        ("asks instead of escalating", expected("escalate", "policy_escalation"),
         result("clarify", "missing_info", missing=["os"]), "missed_escalation"),
        ("asks on a routine case", expected("resolve"), result("clarify", "missing_info", missing=["os"]),
         "unnecessary_clarification"),
        ("asks for the right detail", expected("clarify", "missing_info", missing=["os"]),
         result("clarify", "missing_info", missing=["os", "app_version"]), "correct_clarification"),
        ("asks for the wrong detail", expected("clarify", "missing_info", missing=["os"]),
         result("clarify", "missing_info", missing=["webhook_id"]), "incorrect_clarification"),
        ("analysis failed", expected("escalate", "fixes_exhausted"), result("escalate", "analysis_error"),
         "analysis_error"),
    ]

    def test_outcomes(self):
        for description, exp, res, outcome in self.CASES:
            with self.subTest(description):
                self.assertEqual(score(exp, res)["outcome"], outcome)

    def test_reason_match_needs_the_same_action_and_reason(self):
        self.assertTrue(score(expected("escalate", "fixes_exhausted"),
                              result("escalate", "fixes_exhausted"))["reason_match"])
        self.assertFalse(score(expected("escalate", "fixes_exhausted"),
                               result("escalate", "no_kb_coverage"))["reason_match"])

    def test_attempt_recall_counts_expected_steps_found(self):
        attempted = [AttemptedStep("KB-1", 1, "customer_reported", "q")]
        row = score(expected("escalate", "fixes_exhausted", attempted={"KB-1": [1, 2]}),
                    result("escalate", "fixes_exhausted", attempted=attempted))
        self.assertEqual(row["attempts_found"], [1, 2])  # found, expected


class SummarizeTests(unittest.TestCase):
    def test_counts_and_accuracy(self):
        rows = [
            {"category": "routine", "expected": "resolve", "predicted": "resolve", "outcome": "correct_resolution",
             "decision_match": True, "reason_match": True, "repeated_failed_fix": False, "handoff_complete": None},
            {"category": "routine", "expected": "resolve", "predicted": "escalate",
             "outcome": "unnecessary_escalation", "decision_match": False, "reason_match": False,
             "repeated_failed_fix": False, "handoff_complete": True},
            {"category": "failed_fix", "expected": "escalate", "predicted": "escalate",
             "outcome": "appropriate_escalation", "decision_match": True, "reason_match": False,
             "repeated_failed_fix": False, "handoff_complete": True},
        ]
        m = summarize(rows)
        self.assertEqual((m["n"], m["decision_correct"], m["reason_correct"]), (3, 2, 1))
        self.assertEqual(m["outcomes"]["unnecessary_escalation"], 1)
        self.assertEqual(m["by_category"]["routine"], (1, 2))
        self.assertEqual(m["handoffs"], (2, 2))
        self.assertEqual(m["confusion"][("resolve", "escalate")], 1)


class CommandLineTests(unittest.TestCase):
    def test_eval_writes_summary_results_and_transcripts(self):
        with tempfile.TemporaryDirectory() as out:
            subprocess.run([sys.executable, "-m", "triage", "eval", "--out", out], cwd=ROOT, check=True,
                           capture_output=True)
            rows = json.loads((Path(out) / "results.json").read_text())["cases"]
            cases = json.loads((ROOT / "eval" / "cases.json").read_text())
            self.assertEqual(len(rows), len(cases))
            self.assertTrue((Path(out) / "summary.md").exists())
            self.assertEqual(len(list((Path(out) / "transcripts").glob("*.md"))), len(cases))

    def test_run_prints_a_single_case(self):
        done = subprocess.run([sys.executable, "-m", "triage", "run", "C17"], cwd=ROOT, check=True,
                              capture_output=True, text=True)
        self.assertIn("fixes_exhausted", done.stdout)


if __name__ == "__main__":
    unittest.main()
