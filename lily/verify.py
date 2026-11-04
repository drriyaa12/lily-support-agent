"""Check that the published results and demo page are exactly what the code produces now.

`python3 -m lily verify` re-runs both offline evaluations in a temporary folder and compares them with
the committed `results/`, ignoring only when and how they were generated, and rebuilds the demo page to
compare it with `docs/index.html`. CI runs it on every change, so a published number can never quietly
drift away from the code.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import List

# Per-case fields that must match exactly.
CASE_FIELDS = ("action", "reason", "outcome", "cited_sources", "steps_offered", "missing_info")
SUITES = [("eval/cases.json", "results/heuristic-dev"), ("eval/heldout_cases.json", "results/heuristic-heldout")]


def compare(committed: dict, fresh: dict) -> List[str]:
    """Differences between two results.json documents (meta.generated and meta.command are ignored)."""
    problems = []
    if committed["meta"].get("cases_sha256") != fresh["meta"].get("cases_sha256"):
        problems.append("the labelled cases changed after these results were generated")
    for system in sorted(set(committed["metrics"]) | set(fresh["metrics"])):
        old, new = committed["metrics"].get(system, {}), fresh["metrics"].get(system, {})
        for key in sorted(set(old) | set(new)):
            if old.get(key) != new.get(key):
                problems.append(f"{system} metric {key}: published {old.get(key)!r}, now {new.get(key)!r}")
    old_cases = {c["case_id"]: c for c in committed["cases"]}
    new_cases = {c["case_id"]: c for c in fresh["cases"]}
    for case_id in sorted(set(old_cases) | set(new_cases)):
        if case_id not in old_cases or case_id not in new_cases:
            problems.append(f"{case_id}: present in only one of the two result sets")
            continue
        for system in ("agent", "baseline"):
            for field in CASE_FIELDS:
                published = old_cases[case_id][system].get(field)
                now = new_cases[case_id][system].get(field)
                if published != now:
                    problems.append(f"{case_id} {system} {field}: published {published!r}, now {now!r}")
    return problems


def verify(root: Path) -> List[str]:
    """Re-run the offline evaluations and list every difference from the committed results."""
    from lily.agent import build_agent, build_baseline
    from lily.evaluate import build_meta, load_cases, run_evaluation
    from lily.heuristic import HeuristicAnalyzer

    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        for cases_file, results_dir in SUITES:
            published_path = root / results_dir / "results.json"
            if not published_path.exists():
                problems.append(f"{results_dir}/results.json is missing")
                continue
            out = Path(tmp) / Path(results_dir).name
            meta = build_meta(root / cases_file, "heuristic", "offline heuristic analyzer (no API calls)", "verify")
            run_evaluation(load_cases(root / cases_file), build_agent(HeuristicAnalyzer()), build_baseline(), out, meta)
            fresh = json.loads((out / "results.json").read_text(encoding="utf-8"))
            published = json.loads(published_path.read_text(encoding="utf-8"))
            problems += [f"{results_dir}: {p}" for p in compare(published, fresh)]

    from lily.site import SITE_PATH, build_site_data, render_site

    page = root / SITE_PATH
    if not page.exists() or page.read_text(encoding="utf-8") != render_site(build_site_data(root)):
        problems.append(f"{SITE_PATH} is out of date: run python3 -m lily site")
    return problems
