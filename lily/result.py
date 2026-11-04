"""The outcome of handling one ticket, plus readable and machine-readable renderings."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Optional

from lily.investigator import Investigation
from lily.models import Ticket
from lily.policy import Decision
from lily.respond import Handoff


@dataclass
class Result:
    system: str
    ticket: Ticket
    investigation: Investigation
    decision: Decision
    reply: str
    handoff: Optional[Handoff]

    @property
    def cited_sources(self) -> List[str]:
        """What the decision relies on: the incident, the conflicting articles, or the chosen article."""
        if self.decision.incident:
            return [self.decision.incident.id]
        if self.decision.conflicts:
            ids = []
            for c in self.decision.conflicts:
                ids += [i for i in (c.article_a, c.article_b) if i not in ids]
            return ids
        return [self.decision.article.id] if self.decision.article else []

    @property
    def offered_steps(self) -> List[int]:
        return [s.number for s in self.decision.steps]

    def to_dict(self) -> dict:
        d = self.decision
        return {
            "ticket_id": self.ticket.id,
            "system": self.system,
            "action": d.action,
            "reason": d.reason,
            "explanation": d.explanation,
            "cited_sources": self.cited_sources,
            "steps_offered": self.offered_steps,
            "missing_info": d.missing_info,
            "attempted": [asdict(a) for a in self.investigation.attempted],
            "trace": d.trace,
            "reply": self.reply,
            "handoff": asdict(self.handoff) if self.handoff else None,
        }

    def to_markdown(self) -> str:
        t, inv, d = self.ticket, self.investigation, self.decision
        lines = [
            f"# {t.id}: {t.subject}",
            f"**System:** {self.system} · **Decision:** {d.action} (`{d.reason}`) · "
            f"**Cites:** {', '.join(self.cited_sources) or 'nothing'}",
            "",
            "## Ticket",
            f"**Customer:** {t.customer_name} ({t.plan} plan, via {t.channel}) · "
            f"**Received:** {t.created_at:%Y-%m-%d %H:%M} UTC",
            "",
        ]
        for m in t.messages:
            lines.append(f"> **{m.role}:** {m.text}")
            lines.append(">")
        lines[-1] = ""
        lines += [
            "## Investigation",
            f"- **Summary:** {inv.analysis.summary}",
            f"- **Core issue:** {inv.analysis.core_issue}",
        ]
        lines += [f"- {entry}" for entry in inv.log]
        if inv.evidence:
            lines += ["", "**Verified evidence:**"]
            lines += [f"- {e.source_id}: \"{e.quote}\" ({e.supports})" for e in inv.evidence]
        if inv.attempted:
            lines += ["", "**Already tried or not possible:**"]
            lines += [f"- {a.article_id} step {a.step} ({a.how}): \"{a.quote}\"" for a in inv.attempted]
        lines += ["", "## Decision trace"]
        lines += [f"- {entry}" for entry in d.trace]
        lines += ["", f"**Why:** {d.explanation}", "", "## Reply to customer", ""]
        lines += [f"> {line}" if line else ">" for line in self.reply.splitlines()]
        if self.handoff:
            lines += ["", "## Handoff to a human", "", self.handoff.to_markdown()]
        return "\n".join(lines) + "\n"
