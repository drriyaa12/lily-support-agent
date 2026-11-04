# Evaluation results (heuristic analyzer)

- Generated 2026-11-04 20:25 UTC with `python3 -m triage eval`
- 26 cases from `eval/cases.json` (sha256 `64a116d84ccf`)
- **agent**: investigator + decision policy, offline heuristic analyzer (no API calls)
- **baseline**: same KB search and threshold; sends every step of the top article, otherwise escalates
- These are measured results on the development cases the thresholds were tuned on. See README, "Limitations".

## Headline

| Metric | Agent | Baseline |
|---|---|---|
| Correct decision (resolve / clarify / escalate) | 25/26 (96%) | 11/26 (42%) |
| Correct decision for the right reason | 25/26 (96%) | 10/26 (38%) |
| Correct resolutions | 10 of 10 | 8 of 10 |
| Incorrect resolutions (any case) | 1 | 16 |
| Appropriate escalations | 10 of 11 | 1 of 11 |
| Unnecessary escalations | 0 | 1 |
| Missed escalations (asked a question instead) | 0 | 0 |
| Correct clarifying questions | 5 of 5 | 0 of 5 |
| Clarifying questions asking for the wrong detail | 0 | 0 |
| Unnecessary clarifying questions | 0 | 0 |
| Analysis errors | 0 | 0 |
| Resolutions that repeated a step already tried | 0 | 5 |
| Complete handoffs (issue, attempted fixes, open questions) | 10/10 (100%) | 2/2 (100%) |

## By category

| Category | Cases | Agent correct | Baseline correct |
|---|---|---|---|
| routine | 7 | 7 | 7 |
| missing_info | 5 | 5 | 0 |
| conflicting_guidance | 4 | 4 | 1 |
| failed_fix | 5 | 5 | 0 |
| policy_escalation | 2 | 2 | 0 |
| no_kb_coverage | 2 | 1 | 1 |
| known_incident | 1 | 1 | 0 |

## Decisions, agent (rows: expected, columns: predicted)

| expected \ predicted | resolve | clarify | escalate |
|---|---|---|---|
| resolve | 10 | 0 | 0 |
| clarify | 0 | 5 | 0 |
| escalate | 1 | 0 | 10 |

## Decisions, baseline (rows: expected, columns: predicted)

| expected \ predicted | resolve | clarify | escalate |
|---|---|---|---|
| resolve | 10 | 0 | 0 |
| clarify | 4 | 0 | 1 |
| escalate | 10 | 0 | 1 |

## Per case

| Case | Category | Expected | Agent | Baseline |
|---|---|---|---|---|
| [C01](transcripts/C01.md) | routine | resolve (supported_fix) | ✅ resolve (supported_fix) | ✅ resolve (supported_fix) |
| [C02](transcripts/C02.md) | routine | resolve (supported_fix) | ✅ resolve (supported_fix) | ✅ resolve (supported_fix) |
| [C03](transcripts/C03.md) | routine | resolve (supported_fix) | ✅ resolve (supported_fix) | ✅ resolve (supported_fix) |
| [C04](transcripts/C04.md) | routine | resolve (supported_fix) | ✅ resolve (supported_fix) | ✅ resolve (supported_fix) |
| [C05](transcripts/C05.md) | routine | resolve (supported_fix) | ✅ resolve (supported_fix) | ✅ resolve (supported_fix) |
| [C06](transcripts/C06.md) | routine | resolve (supported_fix) | ✅ resolve (supported_fix) | ✅ resolve (supported_fix) |
| [C07](transcripts/C07.md) | routine | resolve (supported_fix) | ✅ resolve (supported_fix) | ✅ resolve (supported_fix) |
| [C08](transcripts/C08.md) | missing_info | clarify (missing_info) | ✅ clarify (missing_info) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen clarify |
| [C09](transcripts/C09.md) | missing_info | clarify (missing_info) | ✅ clarify (missing_info) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen clarify |
| [C10](transcripts/C10.md) | missing_info | clarify (missing_info) | ✅ clarify (missing_info) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen clarify |
| [C11](transcripts/C11.md) | missing_info | clarify (missing_info) | ✅ clarify (missing_info) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen clarify |
| [C12](transcripts/C12.md) | missing_info | clarify (low_information) | ✅ clarify (low_information) | ❌ escalate (no_kb_coverage): unnecessary_escalation |
| [C13](transcripts/C13.md) | conflicting_guidance | escalate (conflicting_guidance) | ✅ escalate (conflicting_guidance) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [C14](transcripts/C14.md) | conflicting_guidance | escalate (conflicting_guidance) | ✅ escalate (conflicting_guidance) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [C15](transcripts/C15.md) | conflicting_guidance | escalate (conflicting_guidance) | ✅ escalate (conflicting_guidance) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [C16](transcripts/C16.md) | conflicting_guidance | resolve (supported_fix) | ✅ resolve (supported_fix) | ✅ resolve (supported_fix) |
| [C17](transcripts/C17.md) | failed_fix | escalate (fixes_exhausted) | ✅ escalate (fixes_exhausted) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [C18](transcripts/C18.md) | failed_fix | resolve (supported_fix) | ✅ resolve (supported_fix) | ❌ resolve (supported_fix): incorrect_resolution, repeated a step the customer already tried |
| [C19](transcripts/C19.md) | failed_fix | escalate (fixes_exhausted) | ✅ escalate (fixes_exhausted) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [C20](transcripts/C20.md) | failed_fix | escalate (fixes_exhausted) | ✅ escalate (fixes_exhausted) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [C21](transcripts/C21.md) | failed_fix | escalate (fixes_exhausted) | ✅ escalate (fixes_exhausted) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [C22](transcripts/C22.md) | policy_escalation | escalate (policy_escalation) | ✅ escalate (policy_escalation) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [C23](transcripts/C23.md) | policy_escalation | escalate (policy_escalation) | ✅ escalate (policy_escalation) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [C24](transcripts/C24.md) | no_kb_coverage | escalate (no_kb_coverage) | ✅ escalate (no_kb_coverage) | ✅ escalate (no_kb_coverage) |
| [C25](transcripts/C25.md) | no_kb_coverage | escalate (no_kb_coverage) | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate | ❌ resolve (supported_fix): incorrect_resolution, should have chosen escalate |
| [C26](transcripts/C26.md) | known_incident | resolve (known_incident) | ✅ resolve (known_incident) | ❌ resolve (supported_fix): incorrect_resolution, cited ['KB-104'], expected ['INC-2207'] |

## How to read this

- **Correct resolution**: the case should be resolved, the reply cites an expected source, and it does not repeat a step the customer already tried.
- **Incorrect resolution**: the system sent a fix when it should have asked or escalated, cited the wrong source, or repeated a failed step.
- **Appropriate escalation**: the case should be escalated and was. The "right reason" row also checks the reason code.
- **Unnecessary escalation**: escalated a case that should have been resolved or clarified.
- **Missed escalation**: asked the customer a question when the case needed a human.
- **Complete handoff**: an escalation whose handoff has a summary, the core issue, at least one open question, and every attempted step listed in the labels.
