# How Claude Code was used

Lily was built with [Claude Code](https://claude.com/claude-code), Anthropic's
coding assistant, working from a written brief. This page records who did what,
how the evaluation data was produced and checked, and what has and has not been
verified. Its purpose is to keep the measured results separate from the
intended behaviour.

## Division of work

| Work | Done by |
|---|---|
| Project brief: requirements, scope, fictional data, evaluation categories; the name "Lily" | Repository owner |
| Architecture and design choices (`docs/design.md`) | Claude Code, for the owner to review |
| All code in `lily/` and all tests in `tests/` | Claude Code |
| Fictional knowledge base (`data/kb/`) and status page (`data/status.json`) | Claude Code |
| Development cases and labels (`eval/cases.json`, `eval/LABELING.md`) | Claude Code |
| Held-out cases (`eval/heldout_cases.json`) | A separate Claude Code agent |
| Blind audit of the held-out labels | Three more Claude Code agents |
| Pre-publish review (50 agents) and the fixes that followed | Claude Code |
| Decisions to publish, final review of claims | Repository owner |

## How the evaluation data was produced

**Development cases (26).** Claude Code wrote these from the labelling guide
before any agent code existed. The repository can't prove that order: the first
commit contains both the cases and the code, so treat it as a statement, not
evidence. The labels were not edited to fit Lily, with one exception. The
pre-publish review found that C22's label left out a step the ticket states
("I've already changed my password"), so C22 now lists KB-103 step 1 as
attempted. Its decision did not change. Lily's thresholds were then tuned by
looking at retrieval scores on these cases, so they are a **development set**,
and scores on them are optimistic.

**Held-out cases (10).** These came from a separate agent that was allowed to
read only the knowledge base, the status page and the labelling guide. It was
told not to open the code, the tests, the results or the development cases, and
to use realistic, paraphrased, typo-prone customer wording. Before Lily ran on
them:

1. Three further agents independently re-derived every label from the guide,
   again without seeing code or results. They agreed with all 10 labels. No case
   was disputed or ambiguous.
2. Lily ran once on the code exactly as it stood (commit `90af606`) and scored
   6/10. That run is kept in `results/heldout-first-run/`.
3. The review fixes below came from reviewers who were told not to open the
   held-out cases, and none was designed around a held-out ticket. Afterwards
   Lily still scored 6/10. A case-by-case comparison showed that no held-out
   decision changed, for Lily or the baseline.

Limits of this independence: every agent was the same model family, and the
held-out cases follow the same labelling guide that Lily's rules implement.
Tickets written by real customers or by other people would be a stronger test.
The held-out cases have since been read to explain the four misses in the
README, so any future change should be checked against a fresh set.

## Pre-publish review

A Claude Code workflow ran 50 agents in parallel, in two parts:

- **Label audit:** the three held-out label auditors described above.
- **Review:** four reviewers each covered one area (correctness, evaluation
  integrity, Claude API usage, confidentiality and publication hygiene). Each
  finding then went to skeptic agents told to refute it by reading the code and
  reproducing the problem: three skeptics for high severity, one otherwise. A
  finding counted only if the skeptics failed to refute it.

Of 41 findings, **27 were confirmed and 14 refuted**. Every confirmed finding
was addressed, each code fix with a regression test written first and watched
failing:

| Area | Confirmed | Examples |
|---|---|---|
| Correctness | 12 | "I need to…" and other questions or intentions read as attempted steps (high severity); a "sync log" matched "sign out"; plan names and time units ("Business plan 20 days ago") matched "Allow 5–10 business days"; blank fields and some timestamp formats crashed; "browser windows" read as an operating system; a quoted policy limit treated as the customer's own value |
| Evaluation integrity | 9 | analysis errors counted as correct decisions; a resolution that dropped an untried step still scored as correct; handoffs never checked for invented attempts; extra clarifying questions accepted; held-out reports labelled as the development set; one missing development label (C22) |
| Claude API usage | 3 | one transient API error stopped a whole evaluation; tests depended on exported environment variables; the docs misstated how the SDK finds credentials |
| Confidentiality and hygiene | 3 | credential wording; a held-out report would have called itself the tuned set; a leftover placeholder in the README |

Two findings were only partly fixed:

- **Conflict scope.** A plan-specific fact no longer matters for a Free-plan
  customer. Role-specific facts are not handled: an owner asking about removing
  members still escalates, even though both articles allow owners to do it.
- **Incident status.** An incident marked resolved without an end time no longer
  counts as active. Replies don't change their wording for incidents resolved
  after the ticket arrived.

## What was verified

- **Tests.** `python3 -m unittest discover -s tests -t .` runs 123 tests on
  Python 3.9 with no third-party packages, and all pass.
- **Offline evaluation.** The numbers in the README and in `results/` come from
  the commands shown there and can be regenerated exactly. Only the timestamp
  changes between runs.
- **Claude request shape.** The `anthropic` 2.4.0 package source was checked to
  confirm that `client.beta.messages.create` accepts `betas`,
  `fallbacks="default"`, `output_config` and `system`. The analyzer is
  unit-tested against a fake client that mirrors the SDK's response objects. The
  tests cover request contents, parsing, refusals, truncation, transient versus
  configuration errors, replay, and the guardrails that drop invented quotes and
  unretrieved articles.

## What was not verified

- **No real Claude API call has been made.** The build environment had no API
  key. Claude-mode accuracy, cost and latency are **unmeasured**, and the README
  reports no Claude numbers.
- Claude mode needs Python 3.10+ and the `anthropic` package. The build machine
  had only Python 3.9, so the real SDK was never imported or run here.
- Prompt-injection resistance is a design property (templated replies, verified
  claims). It has not been tested with attack tickets.

## How to check the claims yourself

```bash
python3 -m unittest discover -s tests -t .
python3 -m lily eval                                   # development set → results/heuristic-dev/
python3 -m lily eval --cases eval/heldout_cases.json   # held-out set → results/heuristic-heldout/
```
