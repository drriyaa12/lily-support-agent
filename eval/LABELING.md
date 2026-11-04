# Labelling guide

Each case in `cases.json` holds a fictional ticket and the decision a careful
human agent would make, using only the fictional knowledge base in `data/kb/`
and the fictional status page in `data/status.json`.

## Decisions

| Decision   | When it is correct |
|------------|--------------------|
| `resolve`  | The KB or the status page fully supports a reply, any information the matching article requires is present, no relevant guidance conflicts, and at least one documented step has not been tried yet (or the article needs no steps). |
| `clarify`  | A supported path exists but the matching article requires information the ticket does not contain, or the ticket is too vague to tell which article applies. |
| `escalate` | The matching article says to always escalate, no article covers the request, two articles disagree in a way that changes the answer for this customer, or every documented step has been tried or is impossible. |

## Reason codes

`supported_fix`, `known_incident`, `missing_info`, `low_information`,
`policy_escalation`, `no_kb_coverage`, `conflicting_guidance`, `fixes_exhausted`.

## Precedence

When several apply, the first one wins:

1. The best-matching article says **always escalate** → `escalate` (`policy_escalation`).
2. The ticket is too vague to pick an article → `clarify` (`low_information`).
3. No article covers the request → `escalate` (`no_kb_coverage`).
4. An **active incident** on the status page affects the same component → `resolve` (`known_incident`). The customer is told about the incident instead of being sent troubleshooting steps.
5. Two relevant articles **conflict in a way that matters** for this customer → `escalate` (`conflicting_guidance`). A disagreement that does not change the answer (for example, two refund windows that both cover a 3-day-old charge) does not count.
6. Required information is missing → `clarify` (`missing_info`).
7. Every documented step was tried, suggested earlier and reported as failing, or is impossible for this customer → `escalate` (`fixes_exhausted`).
8. Otherwise → `resolve` (`supported_fix`) with the steps that have not been tried yet.

## Fields

- `evidence_any`: for `resolve` cases, the reply must cite at least one of these sources. For other decisions it records which sources a reviewer would expect in the handoff.
- `missing_info`: for `clarify` cases, the fields the agent must ask for.
- `attempted_steps`: steps the customer already tried, or that are impossible for them, by article ID and step number. A `resolve` reply must not repeat these steps. Giving a detail an article asks for (such as an invoice number) is not an attempted step.

## How these labels were made

The cases and labels were written by Claude Code (an AI coding assistant) from
this guide **before** any agent code existed. That is our account: the git
history can't show it, because the first commit contains both the cases and the
code. They were not changed afterwards to fit the agent, with one exception. The pre-publish review found that C22's
label left out a step the ticket states ("I've already changed my password"),
so C22 now lists KB-103 step 1 as attempted. Its decision did not change. The
same assistant then wrote the agent, so these cases are a development set, not
an independent test. The 10 held-out cases in `heldout_cases.json` were written
separately (see `docs/claude-code-assistance.md`).
