"""Shared test helpers: repository paths, ticket builder, and the real KB."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

_KB = None


def make_ticket(*messages, subject="Help", created_at="2026-10-28T10:00:00Z", plan="Team", name="Test C."):
    """Build a Ticket. Each message is a string (from the customer) or a (role, text) tuple."""
    from lily.models import Ticket

    msgs = []
    for m in messages:
        role, text = ("customer", m) if isinstance(m, str) else m
        msgs.append({"role": role, "text": text})
    return Ticket.from_dict({
        "id": "T-TEST",
        "created_at": created_at,
        "channel": "test",
        "customer": {"name": name, "plan": plan},
        "subject": subject,
        "messages": msgs,
    })


def real_kb():
    """The repository's knowledge base, loaded once."""
    global _KB
    if _KB is None:
        from lily.kb import load_kb
        _KB = load_kb(DATA / "kb")
    return _KB


def make_article(aid="KB-1", steps=4, required=(), escalate="when_steps_fail", component="sync"):
    from lily.kb import parse_article

    md = (f"---\nid: {aid}\ntitle: Article {aid}\ncomponent: {component}\nescalate: {escalate}\n"
          f"required_info: [{', '.join(required)}]\nqueue: Technical Support\n---\nIntro sentence.\n\n")
    if steps:
        md += "## Steps\n" + "".join(f"{i}. **Step {i}.** Detail {i}.\n" for i in range(1, steps + 1))
    return parse_article(md + "\n## When to escalate\nEscalate with logs.\n")


def make_investigation(relevant=(), provided=None, attempted=(), conflicts=(), incidents=(),
                       low_information=False, error=None, evidence=None):
    from lily.investigator import Investigation
    from lily.models import Analysis, Evidence

    relevant = list(relevant)
    if evidence is None:
        evidence = [Evidence(relevant[0].id, "Intro sentence.", "test")] if relevant else []
    analysis = Analysis(source="test", summary="s", core_issue="c", relevant_ids=[a.id for a in relevant],
                        low_information=low_information, error=error)
    return Investigation(make_ticket("text"), [], analysis, relevant, evidence, provided or {}, list(attempted),
                         list(conflicts), list(incidents), [])
