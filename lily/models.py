"""Plain data types passed between the pipeline stages.

ticket -> Investigation (what we found) -> Decision (what to do) -> Result (reply + handoff)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional


def parse_time(text: str) -> datetime:
    """Parse an ISO 8601 timestamp and return it in UTC. A time without an offset is taken as UTC.

    Python 3.9's parser is strict, so "Z", "+0200" and fractions that are not 3 or 6 digits are normalised first.
    """
    text = re.sub(r"[zZ]$", "+00:00", text.strip())
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)
    text = re.sub(r"\.(\d+)", lambda m: "." + (m.group(1) + "000000")[:6], text)
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass
class Message:
    role: str  # "customer" or "agent"
    text: str


@dataclass
class Ticket:
    id: str
    created_at: datetime
    channel: str
    customer_name: str
    plan: str
    subject: str
    messages: List[Message]

    @classmethod
    def from_dict(cls, data: dict) -> "Ticket":
        customer = data.get("customer") or {}
        return cls(
            id=data["id"],
            created_at=parse_time(data["created_at"]),
            channel=data.get("channel") or "",
            customer_name=(customer.get("name") or "").strip() or "there",
            plan=customer.get("plan") or "unknown",
            subject=data.get("subject") or "",
            messages=[Message(m.get("role") or "customer", m.get("text") or "") for m in data.get("messages") or []],
        )

    @property
    def first_name(self) -> str:
        parts = self.customer_name.split()
        return parts[0] if parts else "there"

    @property
    def customer_messages(self) -> List[str]:
        return [m.text for m in self.messages if m.role == "customer"]

    @property
    def customer_text(self) -> str:
        """Subject plus everything the customer wrote (not our replies)."""
        return "\n".join([self.subject] + self.customer_messages)


@dataclass
class Evidence:
    source_id: str  # KB article ID or incident ID
    quote: str  # copied verbatim from the source
    supports: str  # why it matters for this ticket


@dataclass
class AttemptedStep:
    article_id: str
    step: int
    how: str  # "customer_reported" | "suggested_earlier" | "not_possible"
    quote: str  # what in the ticket shows it


@dataclass
class Conflict:
    fact: str
    article_a: str
    value_a: str
    article_b: str
    value_b: str
    matters: bool  # does the disagreement change the answer for this ticket?
    why: str


@dataclass
class Analysis:
    """What an analyzer (heuristic or Claude) reports about a ticket. Facts only, no decision."""

    source: str
    summary: str
    core_issue: str
    relevant_ids: List[str]
    evidence: List[Evidence] = field(default_factory=list)
    provided_info: Dict[str, str] = field(default_factory=dict)
    attempted: List[AttemptedStep] = field(default_factory=list)
    reports_failure: bool = False
    conflicts: List[Conflict] = field(default_factory=list)
    low_information: bool = False
    error: Optional[str] = None
