"""Offline analyzer: extracts the facts the decision policy needs, using rules.

It lets the whole pipeline run and be evaluated with no API key and fully
reproducible output. It is brittle by design: it matches words and a few
phrasings, so paraphrases it has not seen are missed. `ClaudeAnalyzer` fills
the same `Analysis` using a model instead.
"""
from __future__ import annotations

import re
from typing import List

from triage import settings
from triage.fields import extract_info
from triage.kb import Article
from triage.models import Analysis, AttemptedStep, Evidence, Ticket
from triage.retrieval import ScoredArticle
from triage.text import sentences, tokenize

# "I tried…", "already…", "I've updated…", "we rotated…"
ATTEMPT = re.compile(
    r"\b(?:tried|already|followed)\b"
    r"|\b(?:i|we)(?:'ve| have)?\s+(?:also\s+|already\s+|then\s+|even\s+)?\w+ed\b",
    re.IGNORECASE,
)
# "I don't have my backup codes", "lost", "not signed in on any other device"
UNAVAILABLE = re.compile(
    r"\b(?:don't|do not|no longer) have\b|\blost\b|\bnot\b[^.!?]*\bany (?:other|more)\b|\bno other\b|\bwithout\b",
    re.IGNORECASE,
)
# "still", "didn't work", "no luck"…
FAILURE = re.compile(
    r"\b(?:still|didn't (?:work|help)|did not (?:work|help)|doesn't work|does not work|no luck"
    r"|not working|same (?:error|problem|issue)|nothing (?:arrives|happens|changed|works))\b",
    re.IGNORECASE,
)
# Step verbs specific enough that the verb alone shows the step was done ("I reinstalled").
SPECIFIC_ACTIONS = {"updat", "upgrad", "sign", "reset", "reinstall", "uninstall", "restart", "resend", "enabl",
                    "rotat", "clear"}


def _plain(text: str) -> str:
    return text.replace("’", "'")


def _step_matches(step_tokens: List[str], text_tokens: set, loose: bool = False) -> bool:
    if not step_tokens:
        return False
    shared = set(step_tokens) & text_tokens
    if loose:  # the customer says they lack something: naming the thing is enough
        return bool(shared)
    needed = min(2, len(set(step_tokens)))
    return len(shared) >= needed or (step_tokens[0] in SPECIFIC_ACTIONS and step_tokens[0] in text_tokens)


def find_attempts(ticket: Ticket, article: Article) -> List[AttemptedStep]:
    """Steps of `article` the customer already tried, cannot do, or that we suggested and they said failed."""
    found = {}
    messages = ticket.messages
    for i, message in enumerate(messages):
        text = _plain(message.text)
        if message.role == "customer":
            for sentence in sentences(text):
                unavailable = bool(UNAVAILABLE.search(sentence))
                if not unavailable and not ATTEMPT.search(sentence):
                    continue
                tokens = set(tokenize(sentence))
                for step in article.steps:
                    if step.number not in found and _step_matches(tokenize(step.title), tokens, loose=unavailable):
                        how = "not_possible" if unavailable else "customer_reported"
                        found[step.number] = AttemptedStep(article.id, step.number, how, sentence)
        elif message.role == "agent":
            later = [_plain(m.text) for m in messages[i + 1:] if m.role == "customer"]
            failure = next((t for t in later if FAILURE.search(t)), None)
            if not failure:
                continue
            tokens = set(tokenize(text))
            for step in article.steps:
                if step.number not in found and _step_matches(tokenize(step.title), tokens):
                    found[step.number] = AttemptedStep(article.id, step.number, "suggested_earlier",
                                                       sentences(failure)[0])
    return [found[n] for n in sorted(found)]


def reports_failure(text: str) -> bool:
    return bool(FAILURE.search(_plain(text)))


def is_low_information(ticket: Ticket) -> bool:
    return len(tokenize(ticket.customer_text)) <= settings.LOW_INFO_MAX_TOKENS


def pick_evidence(ticket: Ticket, article: Article) -> Evidence:
    """The intro sentence sharing the most words with the ticket, quoted verbatim."""
    ticket_tokens = set(tokenize(ticket.customer_text))
    options = sentences(article.intro) or [article.steps[0].text if article.steps else article.title]
    best = max(options, key=lambda s: len(set(tokenize(s)) & ticket_tokens))
    shared = sorted(set(tokenize(best)) & ticket_tokens)
    supports = f"Shares the terms {', '.join(shared[:6])} with the ticket." if shared else "Top keyword match."
    return Evidence(article.id, best.replace("**", ""), supports)


def prefer_procedures(relevant: List[ScoredArticle]) -> List[ScoredArticle]:
    """If an FAQ narrowly outranks a step-by-step article in the same area, put the steps first."""
    if len(relevant) < 2 or relevant[0].article.steps:
        return relevant
    top = relevant[0]
    for i, candidate in enumerate(relevant[1:], start=1):
        if (candidate.article.steps and candidate.article.component == top.article.component
                and candidate.score >= settings.SIMILAR_SCORE_RATIO * top.score):
            return [candidate] + relevant[:i] + relevant[i + 1:]
    return relevant


def summarize(ticket: Ticket) -> str:
    customer = ticket.customer_messages
    first = " ".join(sentences(customer[0])[:2]) if customer else ""
    summary = f"{ticket.customer_name} ({ticket.plan} plan) wrote: \"{first}\""
    if len(customer) > 1:
        summary += f" Latest message: \"{sentences(customer[-1])[0]}\""
    return summary


class HeuristicAnalyzer:
    name = "heuristic"

    def analyze(self, ticket: Ticket, candidates: List[ScoredArticle]) -> Analysis:
        relevant = [c for c in candidates if c.score >= settings.RELEVANCE_THRESHOLD][: settings.MAX_RELEVANT]
        relevant = prefer_procedures(relevant)
        best = relevant[0].article if relevant else None
        latest = ticket.customer_messages[-1] if ticket.customer_messages else ""
        return Analysis(
            source=self.name,
            summary=summarize(ticket),
            core_issue=f"{ticket.subject} (closest article: {best.title})" if best else ticket.subject,
            relevant_ids=[c.article.id for c in relevant],
            evidence=[pick_evidence(ticket, c.article) for c in relevant],
            provided_info=extract_info(ticket.customer_text),
            attempted=find_attempts(ticket, best) if best else [],
            reports_failure=reports_failure(latest),
            conflicts=[],  # structured conflicts are checked by the investigator for every analyzer
            low_information=not relevant and is_low_information(ticket),
        )
