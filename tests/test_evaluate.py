import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import ROOT, make_article, make_investigation
from lily.evaluate import build_meta, score, summarize
from lily.models import AttemptedStep
from lily.policy import Decision
from lily.respond import build_handoff
from lily.result import Result


def result(action, reason, article_id="KB-1", steps=(), missing=(), attempted=()):
    article = make_article(article_id)
    decision = Decision(action, reason, "x", article=article, steps=[article.step(n) for n in steps],
                        missing_info=list(missing))
    inv = make_investigation([article], attempted=attempted)
    handoff = build_handoff(decision, inv) if action == "escalate" else None
    return Result("agent", inv.ticket, inv, decision, "reply", handoff)


def tried(*steps):
    return [AttemptedStep("KB-1", n, "customer_reported", "q") for n in steps]


def expected(decision, reason="supported_fix", evidence=("KB-1",), missing=(), attempted=None):
    return {"decision": decision, "reason": reason, "evidence_any": list(evidence), "missing_info": list(missing),
            "attempted_steps": attempted or {}}


class ScoreTests(unittest.TestCase):
    CASES = [
        # (description, expected, result, outcome)
        ("right source, every untried step", expected("resolve"),
         result("resolve", "supported_fix", steps=[1, 2, 3, 4]), "correct_resolution"),
        ("leaves out an untried step", expected("resolve"), result("resolve", "supported_fix", steps=[1, 2]),
         "incorrect_resolution"),
        ("wrong source", expected("resolve"), result("resolve", "supported_fix", "KB-2", steps=[1, 2, 3, 4]),
         "incorrect_resolution"),
        ("repeats a failed step", expected("resolve", attempted={"KB-1": [1]}),
         result("resolve", "supported_fix", steps=[1, 2, 3, 4]), "incorrect_resolution"),
        ("offers exactly the untried steps", expected("resolve", attempted={"KB-1": [1]}),
         result("resolve", "supported_fix", steps=[2, 3, 4], attempted=tried(1)), "correct_resolution"),
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
         result("clarify", "missing_info", missing=["os"]), "correct_clarification"),
        ("asks for an extra detail", expected("clarify", "missing_info", missing=["os"]),
         result("clarify", "missing_info", missing=["os", "app_version"]), "incorrect_clarification"),
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

    def test_analysis_error_is_never_a_correct_decision(self):
        row = score(expected("escalate", "fixes_exhausted"), result("escalate", "analysis_error"))
        self.assertEqual((row["decision_match"], row["predicted"]), (False, "error"))

    def test_handoff_listing_an_unlabelled_attempt_is_incomplete(self):
        row = score(expected("escalate", "fixes_exhausted", attempted={"KB-1": [1]}),
                    result("escalate", "fixes_exhausted", attempted=tried(1, 3)))
        self.assertFalse(row["handoff_complete"])
        self.assertEqual(row["unlabelled_attempts"], 1)

    def test_escalation_records_whether_it_cites_an_expected_source(self):
        self.assertTrue(score(expected("escalate", "fixes_exhausted"),
                              result("escalate", "fixes_exhausted"))["escalation_source_match"])
        self.assertFalse(score(expected("escalate", "fixes_exhausted"),
                               result("escalate", "fixes_exhausted", "KB-2"))["escalation_source_match"])

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
        rows.append({"category": "failed_fix", "expected": "escalate", "predicted": "error",
                     "outcome": "analysis_error", "decision_match": False, "reason_match": False,
                     "repeated_failed_fix": False, "handoff_complete": None})
        m = summarize(rows)
        self.assertEqual((m["n"], m["decision_correct"], m["reason_correct"]), (4, 2, 1))
        self.assertEqual(m["confusion"][("escalate", "error")], 1)
        self.assertEqual(m["outcomes"]["unnecessary_escalation"], 1)
        self.assertEqual(m["by_category"]["routine"], (1, 2))
        self.assertEqual(m["handoffs"], (2, 2))
        self.assertEqual(m["confusion"][("resolve", "escalate")], 1)


class SplitTests(unittest.TestCase):
    """Review finding: every report claimed to cover the tuned development set."""

    def test_meta_names_the_split_being_evaluated(self):
        self.assertEqual(build_meta(ROOT / "eval" / "cases.json", "heuristic", "x", "cmd")["split"], "development")
        self.assertEqual(build_meta(ROOT / "eval" / "heldout_cases.json", "heuristic", "x", "cmd")["split"],
                         "held-out")


class CommandLineTests(unittest.TestCase):
    def test_eval_writes_summary_results_and_transcripts(self):
        with tempfile.TemporaryDirectory() as out:
            subprocess.run([sys.executable, "-m", "lily", "eval", "--out", out], cwd=ROOT, check=True,
                           capture_output=True)
            rows = json.loads((Path(out) / "results.json").read_text())["cases"]
            cases = json.loads((ROOT / "eval" / "cases.json").read_text())
            self.assertEqual(len(rows), len(cases))
            self.assertTrue((Path(out) / "summary.md").exists())
            self.assertEqual(len(list((Path(out) / "transcripts").glob("*.md"))), len(cases))

    def test_missing_claude_sdk_gives_a_clear_message_not_a_traceback(self):
        from lily.__main__ import main
        with mock.patch("lily.claude_analyzer.ClaudeAnalyzer.client",
                        side_effect=RuntimeError("Claude mode needs the Anthropic SDK")):
            with self.assertRaises(SystemExit) as stop:
                main(["run", "C25", "--analyzer", "claude"])
        self.assertIn("needs the Anthropic SDK", str(stop.exception.code))

    def test_a_ticket_file_without_messages_is_rejected_clearly(self):
        from lily.__main__ import load_ticket
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ticket.json"
            path.write_text(json.dumps({"id": "T-1", "created_at": "2026-11-04T10:00:00Z", "subject": "Help"}))
            with self.assertRaises(SystemExit) as stop:
                load_ticket(str(path))
        self.assertIn("messages", str(stop.exception.code))

    def test_run_finds_held_out_cases_too(self):
        done = subprocess.run([sys.executable, "-m", "lily", "run", "H03"], cwd=ROOT, check=True,
                              capture_output=True, text=True)
        self.assertIn("# T-", done.stdout)

    def test_run_prints_a_single_case(self):
        done = subprocess.run([sys.executable, "-m", "lily", "run", "C17"], cwd=ROOT, check=True,
                              capture_output=True, text=True)
        self.assertIn("fixes_exhausted", done.stdout)


if __name__ == "__main__":
    unittest.main()
