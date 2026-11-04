"""The comparison baseline: a naive "top article" responder.

It uses the same KB search and the same relevance threshold as the agent, so
the comparison isolates the decision logic. If the best-matching article
clears the threshold it sends every step of that article; otherwise it
escalates. It never asks a question, ignores the ticket history, the status
page, conflicting articles and "always escalate" policies.
"""
from __future__ import annotations

from typing import Dict

from lily import settings
from lily.heuristic import pick_evidence
from lily.investigator import Investigation
from lily.kb import Article
from lily.models import Analysis, Ticket
from lily.policy import Decision
from lily.respond import build_handoff, compose_reply
from lily.result import Result
from lily.retrieval import BM25Index


# The baseline is a comparison system, so it does not sign as Lily.
SIGNATURE = "Baseline responder (for comparison only)"
PREPARED_BY = "the baseline responder (for comparison only)"


class BaselineAgent:
    name = "baseline"

    def __init__(self, kb: Dict[str, Article], index: BM25Index):
        self.kb, self.index = kb, index

    def handle(self, ticket: Ticket) -> Result:
        candidates = self.index.search(ticket.customer_text, k=1)
        top = candidates[0] if candidates and candidates[0].score >= settings.RELEVANCE_THRESHOLD else None
        analysis = Analysis(source=self.name, summary=f"{ticket.customer_name}: {ticket.subject}",
                            core_issue=ticket.subject, relevant_ids=[top.article.id] if top else [])
        inv = Investigation(ticket, candidates, analysis, [top.article] if top else [],
                            evidence=[pick_evidence(ticket, top.article)] if top else [],
                            log=[f"Top match: {top.article.id} ({top.score:.1f})" if top else "No match above threshold"])
        if top:
            decision = Decision("resolve", "supported_fix",
                                f"Top match {top.article.id} scored {top.score:.1f}, above the threshold.",
                                article=top.article, steps=list(top.article.steps),
                                trace=[f"Top match {top.article.id} ({top.score:.1f}) >= "
                                       f"{settings.RELEVANCE_THRESHOLD}", "=> resolve (supported_fix)"])
        else:
            decision = Decision("escalate", "no_kb_coverage", "No article scored above the threshold.",
                                trace=["No match above threshold", "=> escalate (no_kb_coverage)"])
        handoff = build_handoff(decision, inv, prepared_by=PREPARED_BY) if decision.action == "escalate" else None
        return Result(self.name, ticket, inv, decision, compose_reply(decision, inv, signature=SIGNATURE), handoff)
