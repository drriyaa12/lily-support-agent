"""The decision policy: resolve, clarify or escalate.

This is plain code on purpose. The analyzer (rules or a model) reports facts;
this function applies a fixed, ordered list of rules to the *verified*
facts. That keeps the part that decides what a customer is told auditable,
testable and identical across analyzers. Every rule checked is written to
`Decision.trace`, so any decision can be explained line by line.

Rule order (first match wins), mirroring eval/LABELING.md:
  0. analysis failed                         -> escalate  analysis_error
  1. best article says "always escalate"     -> escalate  policy_escalation
  2. ticket too vague to pick an article     -> clarify   low_information
  3. no relevant article                     -> escalate  no_kb_coverage
  4. active incident on that component       -> resolve   known_incident
  5. relevant articles conflict, and it matters -> escalate conflicting_guidance
  6. required details missing                -> clarify   missing_info
  7. every step tried or impossible          -> escalate  fixes_exhausted
  8. no verified quote from the article      -> escalate  ungrounded_evidence
  9. otherwise                               -> resolve   supported_fix (untried steps only)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from triage.fields import ISSUE_DETAILS
from triage.investigator import Investigation
from triage.kb import Article, Step
from triage.models import Conflict
from triage.status import Incident


@dataclass
class Decision:
    action: str  # resolve | clarify | escalate
    reason: str
    explanation: str
    article: Optional[Article] = None
    steps: List[Step] = field(default_factory=list)
    missing_info: List[str] = field(default_factory=list)
    incident: Optional[Incident] = None
    conflicts: List[Conflict] = field(default_factory=list)
    trace: List[str] = field(default_factory=list)


def decide(inv: Investigation) -> Decision:
    trace: List[str] = []

    def done(action: str, reason: str, explanation: str, **kwargs) -> Decision:
        trace.append(f"=> {action} ({reason})")
        return Decision(action, reason, explanation, trace=trace, **kwargs)

    best = inv.best

    trace.append(f"0. Analysis error? {inv.analysis.error or 'no'}")
    if inv.analysis.error:
        return done("escalate", "analysis_error",
                    f"The ticket could not be analysed automatically ({inv.analysis.error}).", article=best)

    trace.append(f"1. Best article requires escalation? {'yes, ' + best.id if best and best.escalate == 'always' else 'no'}")
    if best and best.escalate == "always":
        return done("escalate", "policy_escalation",
                    f"{best.id} says requests like this always go to {best.queue}.", article=best)

    trace.append(f"2. Too vague to triage? {'yes' if inv.analysis.low_information else 'no'}")
    if inv.analysis.low_information and not best:
        return done("clarify", "low_information",
                    "The ticket does not say which part of the product is affected.", missing_info=[ISSUE_DETAILS])

    trace.append(f"3. Relevant article found? {best.id if best else 'no'}")
    if not best:
        return done("escalate", "no_kb_coverage", "No knowledge-base article covers this request.")

    trace.append(f"4. Active incident for '{best.component}'? "
                 f"{', '.join(i.id for i in inv.incidents) or 'no'}")
    if inv.incidents:
        incident = inv.incidents[0]
        return done("resolve", "known_incident",
                    f"{incident.id} ({incident.title}) was active when the ticket arrived.",
                    article=best, incident=incident)

    mattering = [c for c in inv.conflicts if c.matters]
    trace.append(f"5. Conflicting guidance that matters? "
                 f"{'; '.join(f'{c.article_a} vs {c.article_b} on {c.fact}' for c in mattering) or 'no'}")
    if mattering:
        return done("escalate", "conflicting_guidance",
                    " ".join(c.why for c in mattering), article=best, conflicts=mattering)

    missing = [name for name in best.required_info if name not in inv.provided_info]
    trace.append(f"6. Required details missing for {best.id}? {', '.join(missing) or 'no'}")
    if missing:
        return done("clarify", "missing_info", f"{best.id} needs {', '.join(missing)} before troubleshooting.",
                    article=best, missing_info=missing)

    tried = {a.step for a in inv.attempted if a.article_id == best.id}
    remaining = [s for s in best.steps if s.number not in tried]
    trace.append(f"7. Steps already tried or impossible: {sorted(tried) or 'none'}; "
                 f"remaining: {[s.number for s in remaining] or 'none'}")
    if best.steps and not remaining:
        return done("escalate", "fixes_exhausted",
                    f"Every step in {best.id} has been tried or is not possible for this customer.", article=best)

    grounded = [e for e in inv.evidence if e.source_id == best.id]
    trace.append(f"8. Verified quote from {best.id}? {'yes' if grounded else 'no'}")
    if not grounded:
        return done("escalate", "ungrounded_evidence",
                    f"No quote from {best.id} could be verified, so the reply would not be grounded.", article=best)

    return done("resolve", "supported_fix",
                f"{best.id} covers this and {len(remaining)} step(s) have not been tried yet."
                if best.steps else f"{best.id} answers this directly.",
                article=best, steps=remaining)
