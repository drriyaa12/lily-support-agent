# Lily evaluation results: held-out set, heuristic analyzer

- Generated 2026-11-04 21:13 UTC with `python3 -m lily eval --cases eval/heldout_cases.json`
- 10 cases from `eval/heldout_cases.json` (sha256 `3eedb5e35ab9`)
- **Lily**: investigator + decision policy, offline heuristic analyzer (no API calls)
- **baseline**: same KB search and threshold; sends every step of the top article, otherwise escalates
- These are measured results on **held-out** cases that were written separately, with no access to the code, and never used for tuning.

## Headline

| Metric | Lily | Baseline |
|---|---|---|
| Correct decision (resolve / clarify / escalate) | 6/10 (60%) | 3/10 (30%) |
| Correct decision for the right reason | 6/10 (60%) | 2/10 (20%) |
| Correct resolutions | 2 of 3 | 1 of 3 |
| Incorrect resolutions (any case) | 3 | 8 |
| Appropriate escalations | 2 of 5 | 0 of 5 |
| Unnecessary escalations | 1 | 1 |
| Missed escalations (asked a question instead) | 1 | 0 |
| Correct clarifying questions | 1 of 2 | 0 of 2 |
| Clarifying questions asking for the wrong details | 0 | 0 |
| Unnecessary clarifying questions | 0 | 0 |
| Analysis errors | 0 | 0 |
| Resolutions that repeated a step already tried | 2 | 6 |
| Attempted steps claimed that the labels don't support | 1 | 0 |
| Escalations citing an expected source | 2/2 (100%) | n/a |
| Complete handoffs (issue, every attempted fix and no invented ones, open questions) | 3/3 (100%) | 1/1 (100%) |

## By category

| Category | Cases | Lily correct | Baseline correct |
|---|---|---|---|
| routine | 2 | 1 | 1 |
| known_incident | 1 | 1 | 0 |
| missing_info | 2 | 1 | 0 |
| conflicting_guidance | 1 | 0 | 0 |
| failed_fix | 2 | 1 | 0 |
| policy_escalation | 1 | 1 | 0 |
| no_kb_coverage | 1 | 0 | 0 |

## Decisions, Lily (rows: expected, columns: predicted)

| expected \ predicted | resolve | clarify | escalate | error |
|---|---|---|---|---|
| resolve | 3 | 0 | 0 | 0 |
| clarify | 0 | 1 | 1 | 0 |
| escalate | 2 | 1 | 2 | 0 |

## Decisions, baseline (rows: expected, columns: predicted)

| expected \ predicted | resolve | clarify | escalate | error |
|---|---|---|---|---|
| resolve | 3 | 0 | 0 | 0 |
| clarify | 1 | 0 | 1 | 0 |
| escalate | 5 | 0 | 0 | 0 |

## Per case

| Case | Category | Expected | Lily | Baseline |
|---|---|---|---|---|
| [H01](transcripts/H01.md) | routine | resolve (supported_fix) | ❌ resolve (supported_fix): incorrect_resolution, repeated a step the customer already tried | ❌ resolve (supported_fix): incorrect_resolution, repeated a step the customer already tried |
| [H02](transcripts/H02.md) | routine | resolve (supported_fix) | ✅ resolve (supported_fix) | ✅ resolve (supported_fix) |
| [H03](transcripts/H03.md) | known_incident | resolve (known_incident) | ✅ resolve (known_incident) | ❌ resolve (supported_fix): incorrect_resolution, cited ['KB-104'], expected ['INC-2207'] |
| [H04](transcripts/H04.md) | missing_info | clarify (missing_info) | ✅ clarify (missing_info) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen clarify |
| [H05](transcripts/H05.md) | missing_info | clarify (low_information) | ❌ escalate (no_kb_coverage): unnecessary_escalation | ❌ escalate (no_kb_coverage): unnecessary_escalation |
| [H06](transcripts/H06.md) | conflicting_guidance | escalate (conflicting_guidance) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [H07](transcripts/H07.md) | failed_fix | escalate (fixes_exhausted) | ✅ escalate (fixes_exhausted) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [H08](transcripts/H08.md) | failed_fix | escalate (fixes_exhausted) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [H09](transcripts/H09.md) | policy_escalation | escalate (policy_escalation) | ✅ escalate (policy_escalation) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [H10](transcripts/H10.md) | no_kb_coverage | escalate (no_kb_coverage) | ❌ clarify (missing_info): missed_escalation | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |

## How to read this

- **Correct resolution**: the case should be resolved, the reply cites an expected source, it does not repeat a step the customer already tried, and it includes every step they have not tried.
- **Incorrect resolution**: the system sent a fix when it should have asked or escalated, cited the wrong source, repeated a failed step, or left out an untried one.
- **Appropriate escalation**: the case should be escalated and was. The "right reason" row also checks the reason code, and "citing an expected source" checks the article or incident it points to.
- **Unnecessary escalation**: escalated a case that should have been resolved or clarified.
- **Missed escalation**: asked the customer a question when the case needed a human. (Sending a fix instead counts as an incorrect resolution.)
- **Correct clarifying question**: asked for exactly the details the labels list. Asking for more or fewer counts as "wrong details". Asking when the case should be resolved is "unnecessary".
- **Analysis error**: the analyzer failed (API error, refusal or unreadable output). Lily escalates such tickets, but they never count as a correct decision. They get their own column above.
- **Attempted steps the labels don't support**: steps the system said the customer had tried that the labels do not list, on the articles the labels cover. Lower is better.
- **Complete handoff**: an escalation whose handoff has a summary, the core issue, at least one open question, every labelled attempted step and no unsupported ones.
