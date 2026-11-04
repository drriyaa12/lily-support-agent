"""Investigation: gather the evidence a decision needs, and keep only what checks out.

Like a support engineer before replying, the investigator looks in three
places: the knowledge base (keyword search), the ticket thread (via the
analyzer), and the status page. Whatever the analyzer claims is verified
against the sources: quotes must appear verbatim in the cited article,
details must appear in the customer's own words, and step numbers must exist.
Anything that fails a check is dropped and noted in the investigation log.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from lily import settings
from lily.fields import FIELDS, extract_info
from lily.kb import Article, fact_label
from lily.models import Analysis, AttemptedStep, Conflict, Evidence, Ticket
from lily.retrieval import BM25Index, ScoredArticle
from lily.status import Incident, active_incidents
from lily.text import normalise_quote, tokenize

# Fact names carry their unit (refund_window_days, max_upload_mb_paid) so a
# number in the ticket can be compared with both conflicting values.
UNIT_PATTERNS = {
    "days": r"(\d+(?:\.\d+)?)\s*days?\b",
    "mb": r"(\d+(?:\.\d+)?)\s*(?:mb|megabytes?)\b",
    "gb": r"(\d+(?:\.\d+)?)\s*(?:gb|gigabytes?)\b",
}


@dataclass
class Investigation:
    ticket: Ticket
    candidates: List[ScoredArticle]
    analysis: Analysis
    relevant: List[Article]
    evidence: List[Evidence] = field(default_factory=list)
    provided_info: Dict[str, str] = field(default_factory=dict)
    attempted: List[AttemptedStep] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)
    incidents: List[Incident] = field(default_factory=list)
    log: List[str] = field(default_factory=list)

    @property
    def best(self) -> Optional[Article]:
        return self.relevant[0] if self.relevant else None


def _number(value: str) -> Optional[float]:
    try:
        return float(value)
    except ValueError:
        return None


def _conflict_matters(fact: str, value_a: str, value_b: str, text: str, plan: str = ""):
    label = fact_label(fact)
    key_tokens = set(tokenize(fact.replace("_", " ")))
    if len(key_tokens & set(tokenize(text))) < min(2, len(key_tokens)):
        return False, f"The ticket is not about {label}."
    asks_about_paid = bool({"upgrad", "paid", "team", "business"} & set(tokenize(text)))
    if fact.endswith("_paid") and plan.strip().lower() == "free" and not asks_about_paid:
        return False, "The customer is on the Free plan, and the conflicting values only apply to paid plans."
    unit = next((part for part in fact.split("_") if part in UNIT_PATTERNS), None)
    a, b = _number(value_a), _number(value_b)
    if unit and a is not None and b is not None:
        found = [float(x) for x in re.findall(UNIT_PATTERNS[unit], text, re.IGNORECASE)]
        # A number equal to one of the limits is usually the customer quoting a policy, so prefer the others.
        # If there are no others, it is the customer's own value.
        mentioned = [v for v in found if v not in (a, b)] or found
        unit_name = unit.upper() if unit in ("mb", "gb") else unit
        if mentioned:
            low, high = sorted([a, b])
            between = [v for v in mentioned if low < v <= high]
            if between:
                return True, (f"The ticket mentions {between[0]:g} {unit_name}, which one article allows "
                              "and the other does not.")
            return False, f"The ticket mentions {mentioned[0]:g} {unit_name}, which both articles treat the same way."
    return True, f"The articles disagree about {label}, and the ticket asks about it."


def fact_conflicts(articles: List[Article], text: str, plan: str = "") -> List[Conflict]:
    """Pairs of articles that state different values for the same fact, and whether that matters here."""
    conflicts = []
    for i, a in enumerate(articles):
        for b in articles[i + 1:]:
            for fact in sorted(set(a.facts) & set(b.facts)):
                if a.facts[fact] != b.facts[fact]:
                    matters, why = _conflict_matters(fact, a.facts[fact], b.facts[fact], text, plan)
                    conflicts.append(Conflict(fact, a.id, a.facts[fact], b.id, b.facts[fact], matters, why))
    return conflicts


class Investigator:
    def __init__(self, kb: Dict[str, Article], index: BM25Index, incidents: List[Incident], analyzer,
                 top_k: int = settings.TOP_K):
        self.kb, self.index, self.incidents, self.analyzer, self.top_k = kb, index, incidents, analyzer, top_k

    def investigate(self, ticket: Ticket) -> Investigation:
        log: List[str] = []
        text = ticket.customer_text
        candidates = self.index.search(text, k=self.top_k)
        log.append("KB search: " + (", ".join(f"{c.article.id} ({c.score:.1f})" for c in candidates) or "no matches"))

        analysis = self.analyzer.analyze(ticket, candidates)
        log.append(f"Analyzer: {analysis.source}")
        if analysis.error:
            log.append(f"Analyzer error: {analysis.error}")

        retrieved = {c.article.id for c in candidates}
        relevant: List[Article] = []
        for article_id in analysis.relevant_ids:
            if article_id in (a.id for a in relevant):
                log.append(f"Ignored a duplicate mention of {article_id}")
            elif article_id in retrieved and article_id in self.kb:
                relevant.append(self.kb[article_id])
            else:
                log.append(f"Dropped relevant article {article_id}: not among the retrieved articles")
        relevant_ids = {a.id for a in relevant}
        log.append("Relevant: " + (", ".join(a.id for a in relevant) or "none"))

        evidence = []
        for item in analysis.evidence:
            quote = normalise_quote(item.quote)
            source = self.kb.get(item.source_id)
            if source and item.source_id in relevant_ids and quote and quote in normalise_quote(source.text):
                evidence.append(item)
            else:
                log.append(f"Dropped a quote attributed to {item.source_id}: not found verbatim in a relevant article")

        # The analyzer's details win when they check out; pattern matching fills in the rest.
        provided: Dict[str, str] = {}
        for name, value in analysis.provided_info.items():
            if name in FIELDS and value and value.lower() in text.lower():
                provided[name] = value
            else:
                log.append(f"Dropped detail {name}={value!r}: not found in the customer's messages")
        for name, value in extract_info(text).items():
            provided.setdefault(name, value)

        attempted = []
        said = normalise_quote(text)
        for attempt in analysis.attempted:
            article = self.kb.get(attempt.article_id)
            if not (article and attempt.article_id in relevant_ids and any(s.number == attempt.step for s in article.steps)):
                log.append(f"Dropped attempted step {attempt.article_id} #{attempt.step}: no such step")
            elif normalise_quote(attempt.quote) not in said:
                log.append(f"Dropped attempted step {attempt.article_id} #{attempt.step}: its quote is not in the "
                           "customer's messages")
            else:
                attempted.append(attempt)

        conflicts = fact_conflicts(relevant, text, plan=ticket.plan) + [
            c for c in analysis.conflicts if c.article_a in relevant_ids and c.article_b in relevant_ids
        ]
        for c in conflicts:
            log.append(f"Conflict on {c.fact}: {c.article_a}={c.value_a} vs {c.article_b}={c.value_b} "
                       f"({'matters' if c.matters else 'does not matter'}: {c.why})")

        best = relevant[0] if relevant else None
        incidents = active_incidents(self.incidents, best.component, ticket.created_at) if best else []
        if best:
            log.append(f"Status page for '{best.component}': "
                       + (", ".join(f"{i.id} active" for i in incidents) or "no active incident"))

        return Investigation(ticket, candidates, analysis, relevant, evidence, provided, attempted, conflicts,
                             incidents, log)
