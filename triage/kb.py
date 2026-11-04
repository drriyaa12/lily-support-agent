"""Knowledge-base articles: Markdown files with a small front-matter header.

Front matter keys (one per line, `key: value`):
  id, title, component, updated, queue
  required_info: [field, field]    details the agent must have before proposing steps
  escalate: when_steps_fail|always  "always" means never self-serve, hand to a human
  fact: name = value                repeatable; structured claims used to detect conflicts

The body is free text, with an optional "## Steps" section of numbered,
bold-titled steps and an optional "## When to escalate" section.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

ESCALATION_MODES = {"when_steps_fail", "always"}

# Readable names for KB facts; unknown facts fall back to their key.
FACT_LABELS = {
    "max_upload_mb_paid": "the largest file you can upload on a paid plan",
    "refund_window_days": "how long after a charge a refund is possible",
    "remove_member_role": "who can remove members from a workspace",
}


def fact_label(fact: str) -> str:
    return FACT_LABELS.get(fact, fact.replace("_", " "))

_STEP = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*(.*)$")


@dataclass(frozen=True)
class Step:
    number: int
    title: str
    detail: str

    @property
    def text(self) -> str:
        return f"{self.title}. {self.detail}".strip()


@dataclass
class Article:
    id: str
    title: str
    component: str
    updated: str = ""
    queue: str = "Support"
    required_info: List[str] = field(default_factory=list)
    escalate: str = "when_steps_fail"
    facts: Dict[str, str] = field(default_factory=dict)
    intro: str = ""
    steps: List[Step] = field(default_factory=list)
    escalation_note: str = ""
    body: str = ""

    @property
    def text(self) -> str:
        """Everything a quote may legitimately be copied from."""
        return f"{self.title}\n{self.body}"

    def step(self, number: int) -> Step:
        for s in self.steps:
            if s.number == number:
                return s
        raise KeyError(f"{self.id} has no step {number}")


def _parse_list(value: str) -> List[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [item.strip() for item in value.split(",") if item.strip()]


def parse_article(markdown: str) -> Article:
    parts = markdown.split("---", 2)
    if len(parts) < 3 or parts[0].strip():
        raise ValueError("article must start with a '---' front-matter block")
    header, body = parts[1], parts[2].strip()

    meta: Dict[str, str] = {}
    facts: Dict[str, str] = {}
    for line in header.strip().splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "fact":
            name, _, fact_value = value.partition("=")
            facts[name.strip()] = fact_value.strip()
        else:
            meta[key] = value

    for required in ("id", "title", "component"):
        if not meta.get(required):
            raise ValueError(f"article is missing '{required}'")
    escalate = meta.get("escalate", "when_steps_fail")
    if escalate not in ESCALATION_MODES:
        raise ValueError(f"{meta['id']}: unknown escalate mode '{escalate}'")

    sections = re.split(r"^## +", body, flags=re.MULTILINE)
    intro = sections[0].strip()
    steps: List[Step] = []
    escalation_note = ""
    for section in sections[1:]:
        heading, _, content = section.partition("\n")
        heading = heading.strip().lower()
        if heading == "steps":
            for line in content.splitlines():
                m = _STEP.match(line.strip())
                if m:
                    steps.append(Step(int(m.group(1)), m.group(2).strip().rstrip("."), m.group(3).strip()))
        elif heading == "when to escalate":
            escalation_note = " ".join(content.split())

    return Article(
        id=meta["id"],
        title=meta["title"],
        component=meta["component"],
        updated=meta.get("updated", ""),
        queue=meta.get("queue", "Support"),
        required_info=_parse_list(meta.get("required_info", "")),
        escalate=escalate,
        facts=facts,
        intro=" ".join(intro.split()),
        steps=steps,
        escalation_note=escalation_note,
        body=body,
    )


def load_kb(directory) -> Dict[str, Article]:
    """Load every *.md article in `directory`, keyed by article ID."""
    articles = {}
    for path in sorted(Path(directory).glob("*.md")):
        article = parse_article(path.read_text(encoding="utf-8"))
        if article.id in articles:
            raise ValueError(f"duplicate article id {article.id}")
        articles[article.id] = article
    return articles
