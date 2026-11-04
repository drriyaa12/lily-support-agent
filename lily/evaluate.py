"""Score the agent and the baseline on the labelled cases and write a report.

Outcome buckets (one per case and system):
  resolve  : correct_resolution | incorrect_resolution (wrong decision, wrong source, a step the customer
             already tried was repeated, or an untried step was left out)
  escalate : appropriate_escalation | unnecessary_escalation
  clarify  : correct_clarification | incorrect_clarification (did not ask for exactly the missing details)
             | unnecessary_clarification (should have resolved) | missed_escalation (should have escalated)
  analysis_error: the analyzer failed (API error, refusal, unreadable output). Never counted as correct.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from lily.models import Ticket
from lily.result import Result

OUTCOMES = [
    "correct_resolution", "incorrect_resolution",
    "appropriate_escalation", "unnecessary_escalation", "missed_escalation",
    "correct_clarification", "incorrect_clarification", "unnecessary_clarification",
    "analysis_error",
]
GOOD = {"correct_resolution", "appropriate_escalation", "correct_clarification"}
ACTIONS = ["resolve", "clarify", "escalate"]
PREDICTED = ACTIONS + ["error"]


def score(expected: dict, result: Result) -> dict:
    d = result.decision
    want = expected["decision"]
    failed = d.reason == "analysis_error"
    article_id = d.article.id if d.article else None
    expected_tried = expected.get("attempted_steps", {})
    offered = set(result.offered_steps)
    repeated = bool(d.action == "resolve" and article_id and offered & set(expected_tried.get(article_id, [])))
    left_out = []
    if d.action == "resolve" and d.reason == "supported_fix" and d.article and d.article.steps:
        tried = set(expected_tried.get(article_id, []))
        left_out = [s.number for s in d.article.steps if s.number not in tried and s.number not in offered]

    note = ""
    if failed:
        outcome, note = "analysis_error", d.explanation
    elif d.action == "resolve":
        if want != "resolve":
            outcome, note = "incorrect_resolution", f"should have chosen {want}"
        elif not set(result.cited_sources) & set(expected["evidence_any"]):
            outcome, note = "incorrect_resolution", f"cited {result.cited_sources}, expected {expected['evidence_any']}"
        elif repeated:
            outcome, note = "incorrect_resolution", "repeated a step the customer already tried"
        elif left_out:
            outcome, note = "incorrect_resolution", f"left out untried step(s) {left_out}"
        else:
            outcome = "correct_resolution"
    elif d.action == "escalate":
        outcome = "appropriate_escalation" if want == "escalate" else "unnecessary_escalation"
    elif want == "clarify":
        if set(expected["missing_info"]) == set(d.missing_info):
            outcome = "correct_clarification"
        else:
            outcome, note = "incorrect_clarification", f"asked for {d.missing_info}, needed {expected['missing_info']}"
    else:
        outcome = "unnecessary_clarification" if want == "resolve" else "missed_escalation"

    found = {(a.article_id, a.step) for a in result.investigation.attempted}
    wanted = {(aid, n) for aid, steps in expected_tried.items() for n in steps}
    # Attempts claimed on articles the labels speak about (the decision's article and every labelled one)
    # that the labels do not support.
    scope = set(expected_tried) | ({article_id} if article_id else set())
    unlabelled = sorted(p for p in found if p[0] in scope and p not in wanted)

    handoff_complete = None
    escalation_source_match = None
    if d.action == "escalate" and not failed:
        h = result.handoff
        handoff_complete = bool(h and h.summary and h.core_issue and h.unresolved_questions
                                and wanted <= found and not unlabelled)
        if expected["evidence_any"]:
            escalation_source_match = bool(set(result.cited_sources) & set(expected["evidence_any"]))
    return {
        "expected": want,
        "expected_reason": expected["reason"],
        "predicted": "error" if failed else d.action,
        "predicted_reason": d.reason,
        "outcome": outcome,
        "note": note,
        "decision_match": not failed and d.action == want,
        "reason_match": not failed and d.action == want and d.reason == expected["reason"],
        "repeated_failed_fix": repeated,
        "attempts_found": [len(wanted & found), len(wanted)] if wanted else None,
        "unlabelled_attempts": len(unlabelled),
        "handoff_complete": handoff_complete,
        "escalation_source_match": escalation_source_match,
    }


def summarize(rows: List[dict]) -> dict:
    outcomes = Counter(r["outcome"] for r in rows)
    by_category: Dict[str, tuple] = {}
    for r in rows:
        good, n = by_category.get(r["category"], (0, 0))
        by_category[r["category"]] = (good + (r["outcome"] in GOOD), n + 1)
    handoffs = [r["handoff_complete"] for r in rows if r.get("handoff_complete") is not None]
    sources = [r["escalation_source_match"] for r in rows if r.get("escalation_source_match") is not None]
    return {
        "n": len(rows),
        "decision_correct": sum(r["decision_match"] for r in rows),
        "reason_correct": sum(r["reason_match"] for r in rows),
        "outcomes": {k: outcomes.get(k, 0) for k in OUTCOMES},
        "by_category": by_category,
        "repeated_failed_fix": sum(r["repeated_failed_fix"] for r in rows),
        "unlabelled_attempts": sum(r.get("unlabelled_attempts", 0) for r in rows),
        "handoffs": (sum(handoffs), len(handoffs)),
        "escalation_sources": (sum(sources), len(sources)),
        "confusion": Counter((r["expected"], r["predicted"]) for r in rows),
    }


def load_cases(path) -> List[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _pct(part: int, whole: int) -> str:
    return f"{part}/{whole} ({100 * part / whole:.0f}%)" if whole else "n/a"


SPLIT_NOTES = {
    "development": "These are measured results on the **development** cases the thresholds were tuned on, so "
                   "they are optimistic. See README, \"Limitations\".",
    "held-out": "These are measured results on **held-out** cases that were written separately, with no access "
                "to the code, and never used for tuning.",
}


def render_summary(meta: dict, metrics: Dict[str, dict], cases: List[dict], rows: Dict[str, List[dict]]) -> str:
    a, b = metrics["agent"], metrics["baseline"]
    expected_counts = Counter(c["expected"]["decision"] for c in cases)

    def line(label, key, of=None):
        whole = expected_counts[of] if of else None
        fmt = (lambda m: f"{m['outcomes'][key]} of {whole}") if whole else (lambda m: str(m["outcomes"][key]))
        return f"| {label} | {fmt(a)} | {fmt(b)} |"

    out = [
        f"# Lily evaluation results: {meta['split']} set, {meta['analyzer']} analyzer",
        "",
        f"- Generated {meta['generated']} with `{meta['command']}`",
        f"- {meta['n_cases']} cases from `{meta['cases_file']}` (sha256 `{meta['cases_sha256'][:12]}`)",
        f"- **Lily**: investigator + decision policy, {meta['analyzer_description']}",
        "- **baseline**: same KB search and threshold; sends every step of the top article, otherwise escalates",
        f"- {SPLIT_NOTES[meta['split']]}",
        "",
        "## Headline",
        "",
        "| Metric | Lily | Baseline |",
        "|---|---|---|",
        f"| Correct decision (resolve / clarify / escalate) | {_pct(a['decision_correct'], a['n'])} | "
        f"{_pct(b['decision_correct'], b['n'])} |",
        f"| Correct decision for the right reason | {_pct(a['reason_correct'], a['n'])} | "
        f"{_pct(b['reason_correct'], b['n'])} |",
        line("Correct resolutions", "correct_resolution", "resolve"),
        line("Incorrect resolutions (any case)", "incorrect_resolution"),
        line("Appropriate escalations", "appropriate_escalation", "escalate"),
        line("Unnecessary escalations", "unnecessary_escalation"),
        line("Missed escalations (asked a question instead)", "missed_escalation"),
        line("Correct clarifying questions", "correct_clarification", "clarify"),
        line("Clarifying questions asking for the wrong details", "incorrect_clarification"),
        line("Unnecessary clarifying questions", "unnecessary_clarification"),
        line("Analysis errors", "analysis_error"),
        f"| Resolutions that repeated a step already tried | {a['repeated_failed_fix']} | {b['repeated_failed_fix']} |",
        f"| Attempted steps claimed that the labels don't support | {a['unlabelled_attempts']} | "
        f"{b['unlabelled_attempts']} |",
        f"| Escalations citing an expected source | {_pct(*a['escalation_sources'])} | "
        f"{_pct(*b['escalation_sources'])} |",
        f"| Complete handoffs (issue, every attempted fix and no invented ones, open questions) | "
        f"{_pct(*a['handoffs'])} | {_pct(*b['handoffs'])} |",
        "",
        "## By category",
        "",
        "| Category | Cases | Lily correct | Baseline correct |",
        "|---|---|---|---|",
    ]
    for category, (good, n) in a["by_category"].items():
        out.append(f"| {category} | {n} | {good} | {b['by_category'][category][0]} |")

    for system, name in (("agent", "Lily"), ("baseline", "baseline")):
        conf = metrics[system]["confusion"]
        out += ["", f"## Decisions, {name} (rows: expected, columns: predicted)", "",
                "| expected \\ predicted | " + " | ".join(PREDICTED) + " |", "|---|---|---|---|---|"]
        for want in ACTIONS:
            out.append(f"| {want} | " + " | ".join(str(conf.get((want, got), 0)) for got in PREDICTED) + " |")

    out += ["", "## Per case", "", "| Case | Category | Expected | Lily | Baseline |", "|---|---|---|---|---|"]
    for case, ra, rb in zip(cases, rows["agent"], rows["baseline"]):
        def cell(r):
            mark = "✅" if r["outcome"] in GOOD else "❌"
            text = f"{mark} {r['predicted']} ({r['predicted_reason']})"
            return text if r["outcome"] in GOOD else f"{text}: {r['outcome']}" + (f", {r['note']}" if r["note"] else "")
        out.append(f"| [{case['case_id']}](transcripts/{case['case_id']}.md) | {case['category']} | "
                   f"{ra['expected']} ({ra['expected_reason']}) | {cell(ra)} | {cell(rb)} |")

    out += [
        "",
        "## How to read this",
        "",
        "- **Correct resolution**: the case should be resolved, the reply cites an expected source, it does not "
        "repeat a step the customer already tried, and it includes every step they have not tried.",
        "- **Incorrect resolution**: the system sent a fix when it should have asked or escalated, cited the "
        "wrong source, repeated a failed step, or left out an untried one.",
        "- **Appropriate escalation**: the case should be escalated and was. The \"right reason\" row also checks "
        "the reason code, and \"citing an expected source\" checks the article or incident it points to.",
        "- **Unnecessary escalation**: escalated a case that should have been resolved or clarified.",
        "- **Missed escalation**: asked the customer a question when the case needed a human. (Sending a fix "
        "instead counts as an incorrect resolution.)",
        "- **Correct clarifying question**: asked for exactly the details the labels list. Asking for more or "
        "fewer counts as \"wrong details\". Asking when the case should be resolved is \"unnecessary\".",
        "- **Analysis error**: the analyzer failed (API error, refusal or unreadable output). Lily escalates "
        "such tickets, but they never count as a correct decision. They get their own column above.",
        "- **Attempted steps the labels don't support**: steps the system said the customer had tried that the "
        "labels do not list, on the articles the labels cover. Lower is better.",
        "- **Complete handoff**: an escalation whose handoff has a summary, the core issue, at least one open "
        "question, every labelled attempted step and no unsupported ones.",
    ]
    return "\n".join(out) + "\n"


def run_evaluation(cases: List[dict], agent, baseline, out_dir: Path, meta: dict) -> Dict[str, dict]:
    out_dir = Path(out_dir)
    (out_dir / "transcripts").mkdir(parents=True, exist_ok=True)
    rows: Dict[str, List[dict]] = {"agent": [], "baseline": []}
    records = []
    for case in cases:
        ticket = Ticket.from_dict(case["ticket"])
        record = {"case_id": case["case_id"], "category": case["category"], "expected": case["expected"]}
        results = {}
        for name, system in (("agent", agent), ("baseline", baseline)):
            result = system.handle(ticket)
            row = {"case_id": case["case_id"], "category": case["category"], **score(case["expected"], result)}
            rows[name].append(row)
            record[name] = {**row, **result.to_dict()}
            results[name] = result
        records.append(record)
        exp = case["expected"]
        header = (f"> **Expected:** {exp['decision']} (`{exp['reason']}`). {exp['rationale']}\n>\n"
                  f"> **Lily outcome:** {rows['agent'][-1]['outcome']} · "
                  f"**Baseline outcome:** {rows['baseline'][-1]['outcome']}\n\n")
        base = results["baseline"]
        footer = (f"\n---\n\n## Baseline on the same ticket\n\n**Decision:** {base.decision.action} "
                  f"(`{base.decision.reason}`): {base.decision.explanation}\n\n"
                  + "\n".join(f"> {l}" if l else ">" for l in base.reply.splitlines()) + "\n")
        (out_dir / "transcripts" / f"{case['case_id']}.md").write_text(
            header + results["agent"].to_markdown() + footer, encoding="utf-8")

    metrics = {name: summarize(r) for name, r in rows.items()}
    (out_dir / "summary.md").write_text(render_summary(meta, metrics, cases, rows), encoding="utf-8")
    serialisable = {name: {**m, "confusion": {f"{k[0]}->{k[1]}": v for k, v in m["confusion"].items()},
                           "by_category": {k: list(v) for k, v in m["by_category"].items()},
                           "handoffs": list(m["handoffs"]),
                           "escalation_sources": list(m["escalation_sources"])} for name, m in metrics.items()}
    (out_dir / "results.json").write_text(
        json.dumps({"meta": meta, "metrics": serialisable, "cases": records}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    return metrics


def build_meta(cases_path: Path, analyzer_name: str, analyzer_description: str, command: str) -> dict:
    data = Path(cases_path).read_bytes()
    return {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "command": command,
        "split": "held-out" if "heldout" in Path(cases_path).name else "development",
        "analyzer": analyzer_name,
        "analyzer_description": analyzer_description,
        "cases_file": str(cases_path),
        "cases_sha256": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),  # same on any checkout
        "n_cases": len(json.loads(data)),
    }
