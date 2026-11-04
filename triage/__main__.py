"""Command line: `python3 -m triage run C17` or `python3 -m triage eval`."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from triage.agent import build_agent, build_baseline
from triage.evaluate import build_meta, load_cases, run_evaluation
from triage.heuristic import HeuristicAnalyzer
from triage.models import Ticket

ROOT = Path(__file__).resolve().parent.parent
CASES = Path("eval") / "cases.json"


def make_analyzer(args, raw_dir=None):
    if args.analyzer == "heuristic":
        return HeuristicAnalyzer(), "offline heuristic analyzer (no API calls)"
    from triage.claude_analyzer import ClaudeAnalyzer, ReplayAnalyzer

    if args.analyzer == "replay":
        if not args.replay_dir:
            sys.exit("--analyzer replay needs --replay-dir (for example results/claude/raw)")
        return ReplayAnalyzer(args.replay_dir), f"saved Claude outputs replayed from {args.replay_dir}"
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        print("Note: ANTHROPIC_API_KEY is not set. The SDK will try its other credential sources "
              "(for example an `ant auth login` profile).", file=sys.stderr)
    analyzer = ClaudeAnalyzer(model=args.model, effort=args.effort, raw_dir=raw_dir)
    return analyzer, f"Claude analyzer ({analyzer.model}, effort {analyzer.effort})"


def load_ticket(ref: str) -> Ticket:
    path = Path(ref)
    if path.suffix == ".json" and path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return Ticket.from_dict(data.get("ticket", data))
    for case in load_cases(ROOT / CASES):
        if case["case_id"].lower() == ref.lower() or case["ticket"]["id"].lower() == ref.lower():
            return Ticket.from_dict(case["ticket"])
    sys.exit(f"No case or ticket file called {ref!r}")


def cmd_run(args) -> None:
    analyzer, _ = make_analyzer(args, raw_dir=args.save_raw)
    system = build_baseline() if args.baseline else build_agent(analyzer)
    result = system.handle(load_ticket(args.ticket))
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False) if args.json else result.to_markdown())


def cmd_eval(args) -> None:
    out = Path(args.out or Path("results") / args.analyzer)
    raw_dir = args.save_raw or (out / "raw" if args.analyzer == "claude" else None)
    analyzer, description = make_analyzer(args, raw_dir=raw_dir)
    cases = load_cases(args.cases)
    command = "python3 -m triage " + " ".join(sys.argv[1:])
    meta = build_meta(Path(args.cases), args.analyzer, description, command)
    metrics = run_evaluation(cases, build_agent(analyzer), build_baseline(), out, meta)
    for name, m in metrics.items():
        o = m["outcomes"]
        print(f"{name:8} correct decisions {m['decision_correct']}/{m['n']} | "
              f"resolutions correct {o['correct_resolution']} incorrect {o['incorrect_resolution']} | "
              f"escalations appropriate {o['appropriate_escalation']} unnecessary {o['unnecessary_escalation']} | "
              f"errors {o['analysis_error']}")
    print(f"Report: {out / 'summary.md'}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="python3 -m triage",
                                     description="Support triage agent: resolve, clarify or escalate tickets.")
    sub = parser.add_subparsers(dest="command", required=True)

    def analyzer_options(p):
        p.add_argument("--analyzer", choices=["heuristic", "claude", "replay"], default="heuristic",
                       help="heuristic: offline rules (default); claude: Claude API; replay: saved Claude outputs")
        p.add_argument("--replay-dir", help="folder of saved Claude outputs, for --analyzer replay")
        p.add_argument("--save-raw", help="folder to save raw Claude outputs in (eval default: OUT/raw)")
        p.add_argument("--model", help="Claude model (default: $SUPPORT_AGENT_MODEL or claude-opus-5-5)")
        p.add_argument("--effort", help="Claude effort (default: $SUPPORT_AGENT_EFFORT or medium)")

    run = sub.add_parser("run", help="handle one ticket and print the transcript")
    run.add_argument("ticket", help="a case ID from eval/cases.json (e.g. C17), or a path to a ticket .json file")
    run.add_argument("--baseline", action="store_true", help="use the baseline instead of the agent")
    run.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    analyzer_options(run)
    run.set_defaults(func=cmd_run)

    ev = sub.add_parser("eval", help="run the agent and the baseline on every labelled case")
    ev.add_argument("--cases", default=str(CASES), help="labelled cases (default: eval/cases.json)")
    ev.add_argument("--out", help="output folder (default: results/<analyzer>)")
    analyzer_options(ev)
    ev.set_defaults(func=cmd_eval)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
