# Design notes

Why the code is shaped the way it is, in the order a reviewer meets it. Each
choice lists what it costs.

## 1. Facts and decisions are separated

The analyzer (offline rules or Claude) only reports facts: which articles
apply, what the customer already tried, what details they gave, whether
articles disagree. A fixed, ordered policy in `triage/policy.py` turns those
facts into resolve, clarify or escalate.

- **Why:** the part that decides what a customer is told stays auditable and
  unit-testable, and identical whichever analyzer runs. A model can make the
  agent *see* a situation wrongly, but it cannot invent a new kind of action.
- **Cost:** the policy only knows the situations it was written for. A case that
  needs judgment outside the rules (for example, a refund request 45 days
  after the charge) falls through to the closest rule.

## 2. A workflow, not an autonomous agent loop

The steps are known in advance (search, analyse, verify, decide, respond), so
the code runs them in order and Claude is called once per ticket for the
analysis step, with structured output.

- **Why:** cheaper, faster and much easier to evaluate than a model choosing
  its own tool calls. Every run takes the same path.
- **Cost:** the model cannot go and look for more evidence on its own (for
  example, search the KB again with better words). That is the natural next
  step if retrieval turns out to be the bottleneck (see C25).

## 3. The investigator checks everything the analyzer claims

`triage/investigator.py` gathers evidence from three sources (KB search, the
ticket thread through the analyzer, the status page) and drops any claim it
cannot verify:

| Claim | Check |
|---|---|
| "Article X is relevant" | X must be among the articles the search returned |
| "This sentence supports the fix" | the quote must appear verbatim in X |
| "The customer gave detail D" | D must appear in the customer's own messages |
| "The customer tried step N" | step N must exist in a relevant article |

Every dropped claim is written to the investigation log, which appears in each
transcript. A resolution also needs at least one verified quote from the
article it cites (rule 8), so an answer the KB does not support becomes an
escalation instead.

## 4. Ordered rules, with a trace

The rules in `policy.py` mirror the precedence in `eval/LABELING.md`
(policy escalation, then vagueness, coverage, incidents, conflicts, missing
details, exhausted fixes, grounding). Each rule writes one line to
`Decision.trace`, so every decision in `results/*/transcripts/` can be read
step by step.

## 5. Replies come from templates and KB text

The customer reply is assembled from the article's own steps (only the ones not
yet tried) or the status page's public message. Nothing the customer is told
is generated freely.

- **Why:** every instruction can be traced to a source. A ticket that contains
  instructions aimed at the model (prompt injection) cannot change what the
  customer receives, only how the facts are read, and those facts are checked.
- **Cost:** replies are correct but plain. A natural next step is letting Claude
  rewrite the template for tone, with the same steps and a check that no new
  instructions appear.

## 6. Keyword retrieval (BM25)

- **Why:** no dependencies, no API key, deterministic scores that are printed in
  every transcript, and easy to reason about with a KB of this size.
- **Cost:** it matches words, not meaning. C25 (a request to re-issue an invoice)
  matches the refund article on the word "invoice", and the offline agent sends
  refund steps. The relevance threshold (7.5) was chosen by looking at scores on
  the development cases (`triage/settings.py`).

## 7. Conflicts are checked for whether they matter

Articles can state structured facts (`fact: refund_window_days = 14`). When two
relevant articles disagree on a fact, the investigator asks whether the
disagreement changes the answer for *this* ticket:

- the ticket must be about the fact (at least two of its key words appear), and
- if the fact has a unit and the ticket mentions a value, the conflict only
  matters when the value falls between the two limits (20 days between 14 and
  30 matters; 3 days does not).

- **Why:** escalating every ticket that touches an inconsistent article
  would be safe but unhelpful (C16).
- **Cost:** real knowledge bases rarely have structured facts. In Claude mode
  the model also reports contradictions it finds in the prose.

## 8. The status page is an evidence source

If the best-matching article's product area has an incident that was open when
the ticket arrived, the agent tells the customer about the incident and does
not send troubleshooting steps (C26). Incidents are matched by component and
time only.

## 9. The baseline isolates the decision logic

The baseline uses the same search and threshold but always sends the top
article's steps (or escalates if nothing clears the threshold). Any difference
in the results therefore comes from the investigation and decision policy,
not from better retrieval.

## 10. How the evaluation counts

- A resolution only counts as correct if the case should be resolved, it cites
  an expected source, **and** it does not repeat a step the customer already
  tried.
- An analyzer failure (API refusal, unreadable output) is its own bucket. It is
  never counted as an appropriate escalation, even though the agent does
  escalate in that situation.
- "Right reason" is reported separately from "right decision", so an
  escalation for the wrong reason is visible.
- Each case gets a full transcript (ticket, investigation log, evidence, rule
  trace, reply, handoff, baseline reply), so any number in the summary can be
  traced back to the cases behind it.

## 11. Offline first, with replay for Claude runs

The default analyzer needs no key, so anyone can reproduce the offline results
exactly. A Claude run saves every raw model output (`results/claude/raw/`), and
`--analyzer replay` re-scores those saved outputs without calling the API, so a
published Claude result can be checked without spending money or depending on
sampling.

## 12. Claude configuration

- Model `claude-opus-5-5`, effort `medium` (both overridable with
  `SUPPORT_AGENT_MODEL` and `SUPPORT_AGENT_EFFORT`). Effort has not been tuned.
- Structured output (`output_config.format` with a JSON schema), so the response
  always parses into the expected fields.
- Server-side refusal fallbacks (`fallbacks: "default"`) on models that support
  them. A refusal or a truncated response becomes an `analysis_error`, which
  escalates the ticket.
- The credential is read by the SDK from `ANTHROPIC_API_KEY`. It is never
  written to disk or logs. `.env` is git-ignored.
