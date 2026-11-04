# How Claude Code was used

This repository was built in one working session with
[Claude Code](https://claude.com/claude-code), Anthropic's coding assistant,
working from a written brief. This page records who did what, how the
evaluation data was produced, and what has and has not been verified. Its
purpose is to keep the measured results separate from the intended behaviour.

## Division of work

| Work | Done by |
|---|---|
| Project brief: requirements, scope, fictional data, evaluation categories | Repository owner |
| Architecture and design choices (`docs/design.md`) | Claude Code, for the owner to review |
| All code in `triage/` and all tests in `tests/` | Claude Code |
| Fictional knowledge base (`data/kb/`) and status page (`data/status.json`) | Claude Code |
| Development cases and labels (`eval/cases.json`, `eval/LABELING.md`) | Claude Code |
| Held-out cases (`eval/heldout_cases.json`) | A separate Claude Code subagent (see below) |
| Running the tests and the offline evaluation, reviewing transcripts | Claude Code |
| Decision to publish, final review of claims | Repository owner |

## How the evaluation data was produced

1. **Development cases (26).** Written by Claude Code from the labelling guide
   *before* any agent code existed. A SHA-256 of the file was recorded at that
   point and matches the committed file (`64a116d84ccf…`, also printed in every
   results summary), so the labels were not edited to fit the agent. The
   agent's thresholds were then tuned by looking at retrieval scores on these
   cases, so they are a **development set**. Scores on them are optimistic.
2. **Held-out cases (10).** Written by a separate Claude Code subagent that was
   told to read only the KB, the status page and the labelling guide. It was told
   not to open the agent code, the tests, the results or the development cases,
   and to use paraphrased, typo-prone, realistic customer wording. The agent was
   run on them once, and nothing was tuned afterwards. Limits of this
   independence: the subagent is the same model family, and it worked from the
   same labelling guide the policy implements. Tickets written by real
   customers or by other people would be a stronger test.

## What was verified

- **Unit and integration tests:** `python3 -m unittest discover -s tests -t .`
  passes on Python 3.9 with no third-party packages.
- **Offline evaluation:** the numbers in the README and `results/heuristic*/`
  were produced by the commands shown there and can be regenerated exactly. The
  only difference between runs is the timestamp.
- **Claude request shape:** the `anthropic` 2.4.0 package source was inspected to
  confirm `client.beta.messages.create` accepts `betas`, `fallbacks="default"`,
  `output_config` and `system`. The analyzer is unit-tested against a fake
  client that mirrors the SDK's response objects: request contents, parsing,
  refusal and truncation handling, replay, and the guardrails that drop
  invented quotes and unretrieved articles.

## What was not verified

- **No real Claude API call has been made.** The build environment had no API
  key. Claude-mode accuracy, cost and latency are therefore **unmeasured**, and
  the README does not report any Claude-mode numbers.
- Claude mode needs Python 3.10+ and the `anthropic` package. The build machine
  only had Python 3.9, so the real SDK was never imported or executed here.
- The heuristic analyzer's phrase rules were developed on the development
  cases. Their behaviour on wording they have not seen is only measured by the
  10 held-out cases.

## How to check the claims yourself

```bash
python3 -m unittest discover -s tests -t .
python3 -m triage eval                                          # dev set, offline
python3 -m triage eval --cases eval/heldout_cases.json --out results/heuristic-heldout
shasum -a 256 eval/cases.json                                   # compare with results summaries
```
