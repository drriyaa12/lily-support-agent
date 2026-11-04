"""BM25 keyword retrieval over KB articles.

Chosen over embeddings so the project runs with no dependencies, no API key
and fully deterministic scores that can be printed and inspected. The cost is
that it matches words, not meaning (see README, "Limitations").
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List

from triage.kb import Article
from triage.text import tokenize


@dataclass(frozen=True)
class ScoredArticle:
    article: Article
    score: float


class BM25Index:
    def __init__(self, articles: Iterable[Article], k1: float = 1.5, b: float = 0.75, title_weight: int = 3):
        self.articles = list(articles)
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(a.title) * title_weight + tokenize(a.body)) for a in self.articles]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_length = sum(self.lengths) / max(len(self.lengths), 1)
        n = len(self.docs)
        doc_freq = Counter(term for d in self.docs for term in d)
        self.idf = {t: math.log((n - df + 0.5) / (df + 0.5) + 1) for t, df in doc_freq.items()}

    def search(self, query: str, k: int = 5) -> List[ScoredArticle]:
        """Top-k articles with a positive score, best first. Ties keep KB order."""
        terms = set(tokenize(query))
        scored = []
        for article, doc, length in zip(self.articles, self.docs, self.lengths):
            score = 0.0
            for term in terms:
                tf = doc.get(term, 0)
                if tf:
                    norm = tf + self.k1 * (1 - self.b + self.b * length / self.avg_length)
                    score += self.idf[term] * tf * (self.k1 + 1) / norm
            if score > 0:
                scored.append(ScoredArticle(article, round(score, 3)))
        scored.sort(key=lambda s: -s.score)
        return scored[:k]
