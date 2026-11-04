"""The support agent: investigate -> decide -> respond."""
from __future__ import annotations

from pathlib import Path

from triage.baseline import BaselineAgent
from triage.investigator import Investigator
from triage.kb import load_kb
from triage.models import Ticket
from triage.policy import decide
from triage.respond import build_handoff, compose_reply
from triage.result import Result
from triage.retrieval import BM25Index
from triage.status import load_status

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class SupportAgent:
    name = "agent"

    def __init__(self, investigator: Investigator):
        self.investigator = investigator

    def handle(self, ticket: Ticket) -> Result:
        investigation = self.investigator.investigate(ticket)
        decision = decide(investigation)
        reply = compose_reply(decision, investigation)
        handoff = build_handoff(decision, investigation) if decision.action == "escalate" else None
        return Result(self.name, ticket, investigation, decision, reply, handoff)


def load_resources(data_dir: Path = DATA_DIR):
    kb = load_kb(Path(data_dir) / "kb")
    return kb, BM25Index(kb.values()), load_status(Path(data_dir) / "status.json")


def build_agent(analyzer, data_dir: Path = DATA_DIR) -> SupportAgent:
    kb, index, incidents = load_resources(data_dir)
    return SupportAgent(Investigator(kb, index, incidents, analyzer))


def build_baseline(data_dir: Path = DATA_DIR) -> BaselineAgent:
    kb, index, _ = load_resources(data_dir)
    return BaselineAgent(kb, index)
