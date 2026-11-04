"""Check that the published results and demo page are exactly what the code produces now.

`python3 -m lily verify` re-runs both offline evaluations in a temporary folder and compares every file it
writes (results.json, summary.md and each transcript) with the committed `results/`, and rebuilds the demo
page to compare it with `docs/index.html`. Only the "generated at" stamp and the recorded command are
carried over from the committed files. CI runs it on every push to main and every pull request. The
README's tables are written by hand and are not checked here.
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


def _file_differences(published_dir: Path, fresh_dir: Path):
    """(relative path, reason) for every generated file that is missing, extra or different."""
    def files(folder):
        return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file() and p.name != ".DS_Store"}

    published, fresh = files(published_dir), files(fresh_dir)
    for name in sorted(fresh - published):
        yield name, " is missing from the published results"
    for name in sorted(published - fresh):
        yield name, " is published but no longer generated"
    for name in sorted(published & fresh):
        if (published_dir / name).read_bytes().replace(b"\r\n", b"\n") != (fresh_dir / name).read_bytes():
            yield name, " differs from what the code produces now"


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
            published = json.loads(published_path.read_text(encoding="utf-8"))
            meta = build_meta(root / cases_file, "heuristic", "offline heuristic analyzer (no API calls)", "verify")
            for key in ("generated", "command", "cases_file"):  # how and when, not what
                meta[key] = published["meta"].get(key, meta[key])
            data_dir = root / "data"
            run_evaluation(load_cases(root / cases_file), build_agent(HeuristicAnalyzer(), data_dir),
                           build_baseline(data_dir), out, meta)
            fresh = json.loads((out / "results.json").read_text(encoding="utf-8"))
            problems += [f"{results_dir}: {p}" for p in compare(published, fresh)]
            problems += [f"{results_dir}/{name}" + why for name, why in _file_differences(root / results_dir, out)]

    from lily.site import SITE_PATH, build_site_data, render_site

    page = root / SITE_PATH
    if not page.exists() or page.read_text(encoding="utf-8") != render_site(build_site_data(root)):
        problems.append(f"{SITE_PATH} is out of date: run python3 -m lily site")
    return problems
