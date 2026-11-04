"""The (fictional) public status page: known incidents by product component."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from triage.models import parse_time


@dataclass(frozen=True)
class Incident:
    id: str
    component: str
    title: str
    status: str
    started_at: datetime
    resolved_at: Optional[datetime]
    public_message: str

    def active_at(self, when: datetime) -> bool:
        if when < self.started_at:
            return False
        return self.resolved_at is None or when < self.resolved_at


def load_status(path) -> List[Incident]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        Incident(
            id=i["id"],
            component=i["component"],
            title=i["title"],
            status=i["status"],
            started_at=parse_time(i["started_at"]),
            resolved_at=parse_time(i["resolved_at"]) if i.get("resolved_at") else None,
            public_message=i["public_message"],
        )
        for i in data["incidents"]
    ]


def active_incidents(incidents: List[Incident], component: str, when: datetime) -> List[Incident]:
    """Incidents affecting `component` that were open when the ticket arrived."""
    return [i for i in incidents if i.component == component and i.active_at(when)]
