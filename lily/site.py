"""Build the demo page: every ticket, Lily's decision and reasoning, next to the baseline.

`python3 -m lily site` runs Lily and the baseline on all labelled cases and writes one self-contained
page to docs/index.html (served by GitHub Pages). The page has no build step and no dependencies
besides an optional web font. Ticket text is embedded as escaped JSON and rendered with textContent,
never as HTML.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

SUITES = [("development", "eval/cases.json"), ("held-out", "eval/heldout_cases.json")]
SITE_PATH = Path("docs") / "index.html"


def _received(dt) -> str:
    return f"{dt.day} {dt:%b %Y, %H:%M} UTC"


def build_site_data(root: Path) -> dict:
    from lily.agent import build_agent, build_baseline, load_resources
    from lily.evaluate import GOOD, load_cases, score
    from lily.heuristic import HeuristicAnalyzer
    from lily.models import Ticket

    data_dir = Path(root) / "data"
    kb, _, incidents = load_resources(data_dir)
    agent, baseline = build_agent(HeuristicAnalyzer(), data_dir), build_baseline(data_dir)
    articles = {a.id: a.title for a in kb.values()}
    articles.update({i.id: i.title for i in incidents})

    sets, cases = {}, []
    for split, cases_file in SUITES:
        lily_correct = baseline_correct = 0
        labelled = load_cases(Path(root) / cases_file)
        for case in labelled:
            ticket = Ticket.from_dict(case["ticket"])
            lily, base = agent.handle(ticket), baseline.handle(ticket)
            lily_row, base_row = score(case["expected"], lily), score(case["expected"], base)
            lily_correct += lily_row["decision_match"]
            baseline_correct += base_row["decision_match"]
            inv = lily.investigation
            cases.append({
                "id": case["case_id"],
                "set": split,
                "category": case["category"],
                "subject": ticket.subject,
                "customer": ticket.customer_name,
                "plan": ticket.plan,
                "channel": ticket.channel,
                "received": _received(ticket.created_at),
                "messages": [{"role": m.role, "text": m.text} for m in ticket.messages],
                "expected": {k: case["expected"][k] for k in ("decision", "reason", "rationale")},
                "lily": {
                    "action": lily_row["predicted"],
                    "reason": lily.decision.reason,
                    "explanation": lily.decision.explanation,
                    "outcome": lily_row["outcome"],
                    "right_decision": lily_row["decision_match"],
                    "good": lily_row["outcome"] in GOOD,
                    "note": lily_row["note"],
                    "cited": lily.cited_sources,
                    "summary": inv.analysis.summary,
                    "core_issue": inv.analysis.core_issue,
                    "checked": inv.log,
                    "evidence": [{"source": e.source_id, "quote": e.quote} for e in inv.evidence],
                    "attempted": [{"article": a.article_id, "step": a.step, "how": a.how, "quote": a.quote}
                                  for a in inv.attempted],
                    "trace": lily.decision.trace,
                    "reply": lily.reply,
                    "handoff": asdict(lily.handoff) if lily.handoff else None,
                },
                "baseline": {
                    "action": base_row["predicted"],
                    "reason": base.decision.reason,
                    "explanation": base.decision.explanation,
                    "outcome": base_row["outcome"],
                    "right_decision": base_row["decision_match"],
                    "good": base_row["outcome"] in GOOD,
                    "note": base_row["note"],
                    "reply": base.reply,
                },
            })
        sets[split] = {"n": len(labelled), "lily_correct": lily_correct, "baseline_correct": baseline_correct}
    return {"sets": sets, "articles": articles, "cases": cases}


def render_site(data: dict) -> str:
    # "<" only ever appears inside JSON strings, so escaping it keeps ticket text from closing the tag.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return PAGE.replace("__DATA__", payload)


def build_site(root: Path) -> Path:
    out = Path(root) / SITE_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_site(build_site_data(root)), encoding="utf-8")
    (out.parent / ".nojekyll").write_text("", encoding="utf-8")  # serve files as they are
    return out


PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lily: support ticket decisions</title>
<meta name="description" content="How Lily, a support agent, decides to resolve, clarify or escalate 36 fictional tickets, next to a simple baseline.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Mono:wght@400;600&family=Atkinson+Hyperlegible+Next:wght@400;600;800&display=swap">
<style>
:root {
  --paper: #f3f6f4; --surface: #ffffff; --ink: #17241f; --muted: #55635d; --line: #cbd5d0;
  --resolve: #2a7049; --clarify: #8f5a00; --escalate: #b3263e; --focus: #1f5fbf;
  --resolve-tint: #e1f0e7; --clarify-tint: #f6ead3; --escalate-tint: #f5dfe3; --hover: #e8eeea;
  --sans: "Atkinson Hyperlegible Next", "Atkinson Hyperlegible", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: "Atkinson Hyperlegible Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #0f1714; --surface: #16211d; --ink: #e4ece8; --muted: #9eafa7; --line: #2d3c36;
    --resolve: #62c48c; --clarify: #e8a93c; --escalate: #f07386; --focus: #7fb0ff;
    --resolve-tint: #183526; --clarify-tint: #3a2c12; --escalate-tint: #3d1b22; --hover: #1d2b26;
    color-scheme: dark;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--paper); color: var(--ink); font: 400 17px/1.55 var(--sans); }
a { color: inherit; text-underline-offset: 3px; }
:focus-visible { outline: 3px solid var(--focus); outline-offset: 2px; }
.wrap { max-width: 1240px; margin: 0 auto; padding: 0 16px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

.masthead { padding: 40px 0 28px; }
.masthead .top { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 8px 16px; }
.masthead h1 { font-size: clamp(3rem, 9vw, 4.75rem); font-weight: 800; letter-spacing: -0.035em; line-height: 0.95; margin: 0; }
.masthead .top a { font-weight: 600; white-space: nowrap; }
.lede { font-size: 1.3rem; line-height: 1.45; max-width: 34rem; margin: 18px 0 0; }
.score { font-size: 1.05rem; max-width: 40rem; margin: 18px 0 0; color: var(--muted); }
.score b { color: var(--ink); font-weight: 800; font-variant-numeric: tabular-nums; }

.layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 36px; align-items: start; padding-bottom: 48px; }
h2 { font-size: 1.65rem; line-height: 1.2; letter-spacing: -0.01em; margin: 0 0 12px; }
h3 { font-size: 1.15rem; margin: 28px 0 8px; }

.controls { display: flex; flex-wrap: wrap; gap: 8px 16px; margin: 0 0 14px; }
.seg { display: inline-flex; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); padding: 3px; }
.seg button { font: inherit; font-size: 0.92rem; color: var(--muted); background: none; border: 0; border-radius: 999px; padding: 5px 12px; cursor: pointer; }
.seg button[aria-pressed="true"] { background: var(--ink); color: var(--paper); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 0.92rem; color: var(--muted); margin: 0 0 10px; }
.legend span { display: inline-flex; align-items: center; gap: 7px; }
.swatch { display: inline-flex; border: 1px solid var(--line); border-radius: 4px; overflow: hidden; }
.swatch b { width: 9px; height: 16px; }
.swatch .r { background: var(--resolve-tint); } .swatch .c { background: var(--clarify-tint); } .swatch .e { background: var(--escalate-tint); }
.back { display: none; font: inherit; font-weight: 600; margin-top: 22px; background: none; border: 1px solid var(--line); border-radius: 999px; padding: 6px 14px; color: var(--ink); cursor: pointer; }

table.lanes { width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.lanes th, .lanes td { padding: 0; border-bottom: 1px solid var(--line); }
.lanes thead th { font-size: 0.85rem; font-weight: 600; color: var(--muted); text-align: left; padding: 9px 12px; background: var(--surface); }
.lanes thead th.lane-h { text-align: center; width: 4.2rem; padding: 9px 4px; }
.lanes thead th.resolve { color: var(--resolve); } .lanes thead th.clarify { color: var(--clarify); } .lanes thead th.escalate { color: var(--escalate); }
.lanes tbody tr:last-child th, .lanes tbody tr:last-child td { border-bottom: 0; }
.lanes tbody th { font-weight: 400; text-align: left; }
.ticket { all: unset; box-sizing: border-box; display: grid; grid-template-columns: 3.1rem minmax(0, 1fr) 1.4rem; align-items: center; gap: 8px; width: 100%; padding: 9px 12px; cursor: pointer; }
.ticket:focus-visible { outline: 3px solid var(--focus); outline-offset: -3px; }
tr.row:hover { background: var(--hover); }
tr.row.selected { background: var(--hover); box-shadow: inset 4px 0 0 var(--ink); }
.cid { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--muted); font-size: 0.9rem; }
.subj { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mark { font-weight: 800; text-align: center; }
.mark.ok { color: var(--resolve); } .mark.warn { color: var(--clarify); } .mark.bad { color: var(--escalate); }
td.lane { text-align: center; vertical-align: middle; cursor: pointer; }
td.lane.resolve { --lane: var(--resolve); --tint: var(--resolve-tint); }
td.lane.clarify { --lane: var(--clarify); --tint: var(--clarify-tint); }
td.lane.escalate { --lane: var(--escalate); --tint: var(--escalate-tint); }
td.lane.expected { background: var(--tint); }
.dots { display: inline-flex; align-items: center; gap: 6px; height: 100%; }
.m-lily { width: 14px; height: 14px; border-radius: 50%; background: var(--lane); }
.m-base { width: 11px; height: 11px; border: 2px solid var(--ink); border-radius: 2px; opacity: 0.75; }
.legend .m-lily { --lane: var(--resolve); } .legend .m-base { display: inline-block; }

.story { background: var(--surface); border: 1px solid var(--line); border-radius: 10px; padding: 24px 26px 30px; position: sticky; top: 16px; max-height: calc(100vh - 32px); overflow: auto; }
.story h2 { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.badge { font-size: 0.95rem; font-weight: 600; color: var(--muted); border: 1px solid var(--line); border-radius: 6px; padding: 1px 7px; font-variant-numeric: tabular-nums; }
.answer { margin: 0 0 14px; max-width: 38rem; }
.verdicts { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 6px 12px; margin: 0; }
.verdicts dt { font-weight: 600; }
.verdicts dd { margin: 0; }
.pill { display: inline-block; font-weight: 600; border-radius: 999px; padding: 0 9px; color: var(--paper); }
.pill.resolve { background: var(--resolve); } .pill.clarify { background: var(--clarify); } .pill.escalate { background: var(--escalate); } .pill.error { background: var(--muted); }
.meta { color: var(--muted); font-size: 0.92rem; margin: 0 0 10px; }
.msg { border-left: 3px solid var(--line); padding: 2px 0 2px 14px; margin: 0 0 12px; max-width: 40rem; }
.msg.agent { border-left-color: var(--muted); }
.msg .who { font-size: 0.85rem; font-weight: 600; color: var(--muted); display: block; }
.msg p { margin: 2px 0 0; }
ul.plain { margin: 6px 0 0; padding-left: 20px; max-width: 42rem; }
ul.plain li { margin: 3px 0; }
blockquote { margin: 8px 0; padding: 6px 14px; border-left: 3px solid var(--resolve); max-width: 40rem; }
blockquote cite { display: block; font-style: normal; font-size: 0.85rem; color: var(--muted); }
ol.trace { list-style: none; margin: 8px 0 0; padding: 0; font: 400 0.9rem/1.5 var(--mono); }
ol.trace li { padding: 4px 10px; border-radius: 6px; }
ol.trace li.fired { background: var(--tint); color: var(--ink); font-weight: 600; box-shadow: inset 3px 0 0 var(--lane); }
ol.trace li.result { color: var(--lane); font-weight: 600; }
.story.resolve { --lane: var(--resolve); --tint: var(--resolve-tint); }
.story.clarify { --lane: var(--clarify); --tint: var(--clarify-tint); }
.story.escalate, .story.error { --lane: var(--escalate); --tint: var(--escalate-tint); }
.reply { white-space: pre-wrap; background: var(--paper); border-radius: 8px; padding: 14px 16px; max-width: 42rem; }
.handoff dt { font-weight: 600; margin-top: 10px; }
.handoff dd { margin: 2px 0 0; max-width: 42rem; }
details { margin-top: 10px; }
summary { cursor: pointer; font-weight: 600; }
.foot { color: var(--muted); font-size: 0.92rem; padding-bottom: 40px; }
.foot p { margin: 4px 0; max-width: 48rem; }
.empty { padding: 18px 12px; color: var(--muted); }

@media (prefers-reduced-motion: no-preference) {
  ol.trace.play li { animation: step 180ms ease-out backwards; }
  @keyframes step { from { opacity: 0; transform: translateX(-4px); } to { opacity: 1; transform: none; } }
}
@media (max-width: 960px) {
  .layout { grid-template-columns: minmax(0, 1fr); gap: 28px; }
  .story { position: static; max-height: none; overflow: visible; padding: 20px 18px 24px; }
  .back { display: inline-block; }
}
@media (max-width: 520px) {
  body { font-size: 16px; }
  .lanes thead th.lane-h { width: 2.9rem; font-size: 0.72rem; padding: 9px 2px; }
  .ticket { grid-template-columns: 2.6rem minmax(0, 1fr) 1.2rem; padding: 9px 8px; gap: 6px; }
  .subj { white-space: normal; line-height: 1.3; }
  .verdicts { grid-template-columns: minmax(0, 1fr); gap: 2px; }
  .verdicts dd { margin-bottom: 8px; }
}
</style>
</head>
<body>
<header class="masthead">
  <div class="wrap">
    <div class="top">
      <h1>Lily</h1>
      <a href="https://github.com/drriyaa12/lily-support-agent">Code and write-up on GitHub</a>
    </div>
    <p class="lede">A support agent that reads a ticket, checks the evidence, and decides: send a fix, ask the customer a question, or hand the ticket to a person with everything they need.</p>
    <p class="score" id="score"></p>
  </div>
</header>

<main class="wrap layout">
  <section aria-labelledby="board-title">
    <h2 id="board-title">Every ticket, and who got it right</h2>
    <div class="controls">
      <div class="seg" role="group" aria-label="Which tickets" id="set-filter"></div>
      <div class="seg" role="group" aria-label="Show" id="miss-filter"></div>
    </div>
    <p class="legend" aria-hidden="true">
      <span><i class="m-lily"></i>Lily's decision</span>
      <span><i class="m-base"></i>Baseline's decision</span>
      <span><i class="swatch"><b class="r"></b><b class="c"></b><b class="e"></b></i>The correct decision (its lane is tinted)</span>
      <span><b class="mark warn">✓</b>Right decision, flawed reply</span>
    </p>
    <table class="lanes">
      <caption class="sr">Each row is a ticket. The tinted lane is the correct decision; the dot is Lily's decision and the square is the baseline's.</caption>
      <thead><tr><th scope="col">Ticket</th><th scope="col" class="lane-h resolve">Resolve</th><th scope="col" class="lane-h clarify">Clarify</th><th scope="col" class="lane-h escalate">Escalate</th></tr></thead>
      <tbody id="rows"></tbody>
    </table>
  </section>
  <section class="story" id="story" tabindex="-1"></section>
  <p class="sr" id="status" aria-live="polite"></p>
</main>

<footer class="wrap foot">
  <p>Quillstack, its help articles, its customers and their tickets are fictional, written for this project.</p>
  <p>Lily runs here with its offline rules; nothing on this page calls an AI model. Development tickets were used to tune those rules, so their score is optimistic; the held-out tickets were written separately and never used for tuning. The README covers the method and the limitations.</p>
</footer>

<script type="application/json" id="lily-data">__DATA__</script>
<script>
(function () {
  "use strict";
  var data = JSON.parse(document.getElementById("lily-data").textContent);
  var LANES = ["resolve", "clarify", "escalate"];
  var NAMES = { resolve: "resolve", clarify: "clarify", escalate: "escalate", error: "analysis error" };
  var REASONS = {
    supported_fix: "a KB article supports a fix", known_incident: "a known incident explains it",
    missing_info: "details are missing", low_information: "the ticket is too vague",
    policy_escalation: "policy says a person must handle it", no_kb_coverage: "no article covers it",
    conflicting_guidance: "the articles disagree in a way that matters", fixes_exhausted: "every documented fix has been tried",
    ungrounded_evidence: "the evidence could not be verified", analysis_error: "the analysis failed"
  };
  var CATEGORIES = {
    routine: "Routine", missing_info: "Missing information", conflicting_guidance: "Conflicting guidance",
    failed_fix: "Failed fix", policy_escalation: "Policy escalation", no_kb_coverage: "No KB coverage",
    known_incident: "Known incident"
  };
  var HOW = { customer_reported: "the customer says they tried it", suggested_earlier: "suggested earlier, and it did not help", not_possible: "the customer can't do it" };
  var state = { set: "all", show: "all", selected: null };

  function el(tag, attrs) {
    var node = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else if (k === "class") node.className = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    for (var i = 2; i < arguments.length; i++) {
      var child = arguments[i];
      if (child == null || child === false) continue;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }
  function verdict(sys) {
    if (!sys.right_decision) return { mark: "✗", cls: "bad", words: "wrong decision" };
    if (!sys.good) return { mark: "✓", cls: "warn", words: "right decision, flawed reply" };
    return { mark: "✓", cls: "ok", words: "right decision" };
  }
  function articleLabel(id) { return data.articles[id] ? id + " (" + data.articles[id] + ")" : id; }

  // Headline sentence, from the same numbers as the published results.
  var dev = data.sets["development"], held = data.sets["held-out"];
  var score = document.getElementById("score");
  score.append("On the " + dev.n + " tickets its rules were tuned on, Lily made the right call on ",
    el("b", { text: String(dev.lily_correct) }), " (the baseline: ", el("b", { text: String(dev.baseline_correct) }),
    "). On " + held.n + " tickets it had never seen, it got ", el("b", { text: String(held.lily_correct) }),
    " right (the baseline: ", el("b", { text: String(held.baseline_correct) }), ").");

  function segmented(container, key, options) {
    options.forEach(function (opt) {
      var b = el("button", { type: "button", "aria-pressed": String(state[key] === opt[0]), text: opt[1] });
      b.addEventListener("click", function () {
        state[key] = opt[0];
        Array.prototype.forEach.call(container.children, function (c) { c.setAttribute("aria-pressed", String(c === b)); });
        renderRows();
      });
      container.appendChild(b);
    });
  }
  segmented(document.getElementById("set-filter"), "set", [["all", "All " + data.cases.length], ["development", "Development " + dev.n], ["held-out", "Held-out " + held.n]]);
  segmented(document.getElementById("miss-filter"), "show", [["all", "All"], ["lily", "Lily's wrong decisions"], ["baseline", "Baseline's wrong decisions"]]);

  function visible() {
    return data.cases.filter(function (c) {
      if (state.set !== "all" && c.set !== state.set) return false;
      if (state.show === "lily") return !c.lily.right_decision;
      if (state.show === "baseline") return !c.baseline.right_decision;
      return true;
    });
  }

  function renderRows() {
    var body = document.getElementById("rows");
    body.textContent = "";
    var list = visible();
    if (!list.length) {
      body.appendChild(el("tr", null, el("td", { colspan: "4", class: "empty", text: "No tickets match these filters." })));
      return;
    }
    list.forEach(function (c) {
      var lv = verdict(c.lily);
      var button = el("button", { type: "button", class: "ticket", "aria-controls": "story", "aria-pressed": String(c.id === state.selected) },
        el("span", { class: "cid", text: c.id }),
        el("span", { class: "subj", text: c.subject }),
        el("span", { class: "mark " + lv.cls, "aria-hidden": "true", text: lv.mark }),
        el("span", { class: "sr", text: ". Correct: " + c.expected.decision + ". Lily: " + NAMES[c.lily.action] + ", " + lv.words +
          ". Baseline: " + NAMES[c.baseline.action] + ", " + verdict(c.baseline).words + "." }));
      button.addEventListener("click", function () { select(c.id, "user"); });
      var row = el("tr", { class: "row" + (c.id === state.selected ? " selected" : ""), "data-id": c.id }, el("th", { scope: "row" }, button));
      LANES.forEach(function (lane) {
        var dots = el("span", { class: "dots", "aria-hidden": "true" },
          c.lily.action === lane ? el("i", { class: "m-lily" }) : null,
          c.baseline.action === lane ? el("i", { class: "m-base" }) : null);
        var cell = el("td", { class: "lane " + lane + (c.expected.decision === lane ? " expected" : "") }, dots);
        cell.addEventListener("click", function () { select(c.id, "user"); });
        row.appendChild(cell);
      });
      body.appendChild(row);
    });
  }

  function section(title) { var s = el("section"); s.appendChild(el("h3", { text: title })); return s; }

  function renderStory(c) {
    var story = document.getElementById("story");
    story.className = "story " + c.lily.action;
    story.textContent = "";
    story.appendChild(el("h2", null, el("span", { class: "badge", text: c.id }), c.subject));
    story.appendChild(el("p", { class: "meta", text: (c.set === "held-out" ? "Held-out ticket" : "Development ticket") + ", " + CATEGORIES[c.category].toLowerCase() }));
    story.appendChild(el("p", { class: "answer" }, el("strong", { text: "Correct answer: " + c.expected.decision + ". " }), c.expected.rationale));

    var lv = verdict(c.lily), bv = verdict(c.baseline);
    var verdicts = el("dl", { class: "verdicts" },
      el("dt", { text: "Lily" }),
      el("dd", null, el("span", { class: "pill " + c.lily.action, text: NAMES[c.lily.action] }), " because " + REASONS[c.lily.reason] + ". ",
        el("strong", { class: "mark " + lv.cls, text: lv.mark + " " + lv.words }), c.lily.note ? " (" + c.lily.note + ")" : ""),
      el("dt", { text: "Baseline" }),
      el("dd", null, el("span", { class: "pill " + c.baseline.action, text: NAMES[c.baseline.action] }), " ",
        el("strong", { class: "mark " + bv.cls, text: bv.mark + " " + bv.words }), c.baseline.note ? " (" + c.baseline.note + ")" : ""));
    story.appendChild(verdicts);

    var t = section("The ticket");
    t.appendChild(el("p", { class: "meta", text: c.customer + ", " + c.plan + " plan, via " + c.channel + ", " + c.received }));
    c.messages.forEach(function (m) {
      t.appendChild(el("div", { class: "msg " + m.role }, el("span", { class: "who", text: m.role === "agent" ? "Earlier reply from support" : "Customer" }), el("p", { text: m.text })));
    });
    story.appendChild(t);

    var k = section("What Lily checked");
    k.appendChild(el("p", { text: c.lily.summary }));
    var checks = el("ul", { class: "plain" });
    c.lily.checked.forEach(function (line) { checks.appendChild(el("li", { text: line })); });
    k.appendChild(checks);
    c.lily.evidence.forEach(function (e) {
      k.appendChild(el("blockquote", null, e.quote, el("cite", { text: articleLabel(e.source) })));
    });
    if (c.lily.attempted.length) {
      var tried = el("ul", { class: "plain" });
      c.lily.attempted.forEach(function (a) { tried.appendChild(el("li", { text: a.article + " step " + a.step + ": " + HOW[a.how] + "." })); });
      k.appendChild(el("p", { text: "Steps already tried or not possible:" }));
      k.appendChild(tried);
    }
    story.appendChild(k);

    var d = section("How Lily decided");
    var trace = el("ol", { class: "trace" });
    var lines = c.lily.trace, fired = lines.length - 2;
    lines.forEach(function (line, i) {
      var li = el("li", { text: line.replace(/^=> /, "Decision: ") });
      if (i === fired) li.className = "fired";
      if (i === lines.length - 1) li.className = "result";
      li.style.animationDelay = (i * 70) + "ms";
      trace.appendChild(li);
    });
    d.appendChild(trace);
    d.appendChild(el("p", { text: c.lily.explanation }));
    story.appendChild(d);
    requestAnimationFrame(function () { trace.classList.add("play"); });

    var r = section("Lily's reply to the customer");
    r.appendChild(el("div", { class: "reply", text: c.lily.reply }));
    story.appendChild(r);

    if (c.lily.handoff) {
      var h = c.lily.handoff, hs = section("Handoff to a person (" + h.queue + ")");
      var dl = el("dl", { class: "handoff" });
      function item(term, value) {
        if (!value || (Array.isArray(value) && !value.length)) return;
        dl.appendChild(el("dt", { text: term }));
        if (Array.isArray(value)) {
          var ul = el("ul", { class: "plain" });
          value.forEach(function (v) { ul.appendChild(el("li", { text: v })); });
          dl.appendChild(el("dd", null, ul));
        } else dl.appendChild(el("dd", { text: value }));
      }
      item("Why it was escalated", h.explanation);
      item("Core issue", h.core_issue);
      item("Fixes already attempted", h.attempted_fixes);
      item("Open questions", h.unresolved_questions);
      item("Suggested next step", h.suggested_next_step);
      item("Evidence checked", h.evidence_checked);
      hs.appendChild(dl);
      story.appendChild(hs);
    }

    var b = section("What the baseline did");
    b.appendChild(el("p", { text: c.baseline.explanation }));
    var more = el("details", null, el("summary", { text: "Show the baseline's reply" }), el("div", { class: "reply", text: c.baseline.reply }));
    b.appendChild(more);
    story.appendChild(b);

    var back = el("button", { type: "button", class: "back", text: "Back to the list" });
    back.addEventListener("click", function () {
      var row = document.querySelector('tr.row[data-id="' + c.id + '"] button');
      if (row) { row.scrollIntoView({ block: "center" }); row.focus(); }
      else document.getElementById("board-title").scrollIntoView();
    });
    story.appendChild(back);
  }

  // how: "user" (a click or key press), "link" (a #ticket link), or "start" (the default ticket on load)
  function select(id, how) {
    var c = data.cases.filter(function (x) { return x.id === id; })[0];
    if (!c) return;
    state.selected = id;
    Array.prototype.forEach.call(document.querySelectorAll("tr.row"), function (row) {
      var on = row.getAttribute("data-id") === id;
      row.classList.toggle("selected", on);
      row.querySelector("button").setAttribute("aria-pressed", String(on));
    });
    renderStory(c);
    if (how === "start") return;
    document.getElementById("status").textContent = "Showing " + c.id + ": " + c.subject;
    if (how === "user" && history.replaceState) history.replaceState(null, "", "#" + id);
    if (window.matchMedia("(max-width: 960px)").matches) {
      var story = document.getElementById("story");
      story.scrollIntoView({ block: "start" });
      if (how === "user") story.focus({ preventScroll: true });
    }
  }

  window.addEventListener("hashchange", function () {
    var id = (location.hash || "").slice(1);
    if (id && id !== state.selected) select(id, "link");
  });

  var initial = (location.hash || "").slice(1);
  var linked = data.cases.some(function (c) { return c.id === initial; });
  state.selected = linked ? initial : "C18";
  renderRows();
  select(state.selected, linked ? "link" : "start");
})();
</script>
</body>
</html>
"""
