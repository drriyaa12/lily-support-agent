"""Turn a decision into the customer reply and, for escalations, a human handoff.

Replies are built from templates and KB text, not generated freely, so every
instruction a customer receives can be traced to a quoted article step or
status-page message. That is a deliberate trade of tone for grounding.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from lily.fields import question_for
from lily.investigator import Investigation
from lily.kb import fact_label
from lily.policy import Decision

DEFAULT_QUEUE = "Tier 2 Support"

# Every reply is signed, and says plainly that it comes from an AI assistant.
SIGNATURE = "Lily\nQuillstack's AI support assistant"

HOW_LABELS = {
    "customer_reported": "customer says they tried it",
    "suggested_earlier": "suggested earlier; customer says it did not help",
    "not_possible": "customer cannot do this",
}


@dataclass
class Handoff:
    ticket_id: str
    queue: str
    reason: str
    explanation: str
    summary: str
    core_issue: str
    customer: str
    details_provided: Dict[str, str] = field(default_factory=dict)
    attempted_fixes: List[str] = field(default_factory=list)
    evidence_checked: List[str] = field(default_factory=list)
    unresolved_questions: List[str] = field(default_factory=list)
    suggested_next_step: str = ""

    def to_markdown(self) -> str:
        def bullets(items, empty="None."):
            return "\n".join(f"- {item}" for item in items) if items else f"- {empty}"

        details = [f"{k}: {v}" for k, v in self.details_provided.items()]
        return "\n".join([
            f"### Handoff for {self.ticket_id} → {self.queue}",
            "*Prepared by Lily, the AI support assistant, for a human colleague.*",
            f"**Why escalated:** `{self.reason}`: {self.explanation}",
            f"**Customer:** {self.customer}",
            f"**Summary:** {self.summary}",
            f"**Core issue:** {self.core_issue}",
            "**Details provided:**", bullets(details),
            "**Attempted fixes:**", bullets(self.attempted_fixes, "None recorded in the ticket."),
            "**Evidence checked:**", bullets(self.evidence_checked),
            "**Unresolved questions:**", bullets(self.unresolved_questions),
            f"**Suggested next step:** {self.suggested_next_step}",
        ])


def _titles(article, numbers) -> str:
    return ", ".join(article.step(n).title.lower() for n in numbers)


def _numbered(steps) -> str:
    return "\n".join(f"{i}. {s.title}. {s.detail}" for i, s in enumerate(steps, start=1))


def compose_reply(decision: Decision, inv: Investigation) -> str:
    return _body(decision, inv) + "\n\n" + SIGNATURE


def _body(decision: Decision, inv: Investigation) -> str:
    name = inv.ticket.first_name
    article = decision.article
    greeting = f"Hi {name},\n\n"

    if decision.reason == "known_incident":
        incident = decision.incident
        return (greeting + "Thanks for letting us know. We're currently investigating an issue that matches what "
                f"you describe: {incident.title} ({incident.id}).\n\n{incident.public_message}\n\n"
                "There's no need to troubleshoot on your side. I've linked your ticket to the incident, and we'll "
                "update you here when it's resolved.")

    if decision.action == "resolve":
        if not decision.steps:
            quote = next(e.quote for e in inv.evidence if e.source_id == article.id)
            return (greeting + f"Thanks for getting in touch. From our guide \"{article.title}\" ({article.id}):\n\n"
                    f"> {quote}\n\nIf that doesn't answer your question, reply here and we'll help.")
        mine = [a for a in inv.attempted if a.article_id == article.id]
        tried = sorted({a.step for a in mine if a.how != "not_possible"})
        impossible = sorted({a.step for a in mine if a.how == "not_possible"} - set(tried))
        parts = []
        if tried:
            parts.append(f"Thanks for already trying these: {_titles(article, tried)}.")
        if impossible:
            these = "this isn't" if len(impossible) == 1 else "these aren't"
            parts.append(f"I understand {these} possible for you: {_titles(article, impossible)}.")
        intro = (" ".join(parts) + " The next steps are:") if parts else "Thanks for getting in touch. Here's what to do:"
        return (greeting + f"{intro}\n\n{_numbered(decision.steps)}\n\n"
                f"These steps come from our guide \"{article.title}\" ({article.id}). If they don't solve the "
                "problem, reply here and tell us what you see.")

    if decision.action == "clarify":
        asks = "\n".join(f"- {question_for(n)}" for n in decision.missing_info)
        return (greeting + "Thanks for getting in touch. So I can point you to the right fix, could you tell me:\n\n"
                f"{asks}\n\nAs soon as I have that, I'll take it from there.")

    queue = article.queue if article else DEFAULT_QUEUE
    if decision.reason == "conflicting_guidance":
        topic = fact_label(decision.conflicts[0].fact)
        body = (f"I want to make sure you get an accurate answer about {topic}, so I've asked our {queue} team to "
                "confirm it. They have a summary of everything you've told us and will reply here.")
    else:
        body = (f"I've passed your request to our {queue} team with a summary of what you've told us and tried, "
                "so you won't need to repeat yourself. They'll reply here.")
    reply = greeting + "Thanks for the details. " + body
    if decision.reason == "policy_escalation" and article.steps:
        tried = {a.step for a in inv.attempted if a.article_id == article.id}
        interim = [s for s in article.steps if s.number not in tried]
        if interim:
            reply += f"\n\nWhile you wait, we recommend:\n\n{_numbered(interim)}"
    return reply


def _questions(decision: Decision, inv: Investigation) -> List[str]:
    article = decision.article
    reason = decision.reason
    if reason == "fixes_exhausted":
        questions = [f"Every step in {article.id} ({article.title}) has failed or cannot be done by this "
                     "customer. What is causing the problem, and what should happen next?"]
    elif reason == "conflicting_guidance":
        questions = [f"Which is right for this customer? On {fact_label(c.fact)}, {c.article_a} says "
                     f"{c.value_a} but {c.article_b} says {c.value_b}. ({c.why})" for c in decision.conflicts]
        questions.append("Which article should be corrected so this does not happen again?")
    elif reason == "no_kb_coverage":
        questions = [f"Is this supported, and which team owns it? No KB article covers: {inv.analysis.core_issue}.",
                     "Should a KB article be written for this kind of request?"]
    elif reason == "policy_escalation":
        note = article.escalation_note.split(". ")[0].rstrip(".") if article.escalation_note else "Handle per policy"
        questions = [f"What does {article.queue} need to verify or do? {article.id} says: \"{note}.\""]
    else:
        questions = [f"Automated analysis was not reliable ({decision.explanation}). What does the customer need?"]
    if article:
        for name in article.required_info:
            if name not in inv.provided_info:
                questions.append(f"Not yet provided by the customer: {question_for(name)}.")
    return questions


def _next_step(decision: Decision) -> str:
    article = decision.article
    if decision.reason in ("fixes_exhausted", "policy_escalation") and article and article.escalation_note:
        return article.escalation_note
    if decision.reason == "conflicting_guidance":
        return "Confirm the correct policy with the article owners, reply to the customer, then fix the outdated article."
    if decision.reason == "no_kb_coverage":
        return "Answer from product knowledge or route to the owning team, and consider adding a KB article."
    return "Review the ticket manually and reply to the customer."


def build_handoff(decision: Decision, inv: Investigation) -> Handoff:
    ticket = inv.ticket
    attempted = []
    for a in inv.attempted:
        article = next((r for r in inv.relevant if r.id == a.article_id), None)
        title = article.step(a.step).title if article else f"step {a.step}"
        attempted.append(f"{a.article_id} step {a.step} \"{title}\": {HOW_LABELS.get(a.how, a.how)} "
                         f"(\"{a.quote}\")")

    relevant_ids = {a.id for a in inv.relevant}
    checked = [f"{c.article.id} \"{c.article.title}\" (keyword score {c.score:.1f})"
               + (" (judged relevant)" if c.article.id in relevant_ids else "") for c in inv.candidates]
    checked += [f"Quote from {e.source_id}: \"{e.quote}\"" for e in inv.evidence]
    if inv.best:
        checked.append(f"Status page, component '{inv.best.component}': "
                       + (", ".join(f"{i.id} ({i.title})" for i in inv.incidents) or "no active incident"))

    return Handoff(
        ticket_id=ticket.id,
        queue=decision.article.queue if decision.article else DEFAULT_QUEUE,
        reason=decision.reason,
        explanation=decision.explanation,
        summary=inv.analysis.summary,
        core_issue=inv.analysis.core_issue,
        customer=f"{ticket.customer_name} ({ticket.plan} plan, via {ticket.channel})",
        details_provided=dict(inv.provided_info),
        attempted_fixes=attempted,
        evidence_checked=checked,
        unresolved_questions=_questions(decision, inv),
        suggested_next_step=_next_step(decision),
    )
