"""Customer details an article can require before the agent proposes a fix.

Each field has the question the agent asks when it is missing and the
patterns used to find it in ticket text. Patterns are tried in order, so the
more specific one (for example "macOS 15" over "MacBook") wins.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Pattern, Tuple


@dataclass(frozen=True)
class InfoField:
    name: str
    question: str
    patterns: Tuple[Pattern, ...]

    def find(self, text: str):
        for pattern in self.patterns:
            match = pattern.search(text)
            if match:
                return match.group(match.lastindex or 0)
        return None


def _p(regex: str, flags: int = re.IGNORECASE) -> Pattern:
    return re.compile(regex, flags)


FIELDS: Dict[str, InfoField] = {
    "account_email": InfoField(
        "account_email",
        "the email address on your Quillstack account",
        (_p(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"),),
    ),
    "os": InfoField(
        "os",
        "your operating system and its version (for example, Windows 11 or macOS 15)",
        (
            _p(r"\b(?:windows|macos|mac\s?os(?:\s?x)?|ios|ipados|android|ubuntu)\s?\d+(?:\.\d+)?\b"),
            _p(r"\b(?:windows|macos|mac\s?os|macbook|imac|mac|linux|ubuntu|chromeos)\b"),
        ),
    ),
    "app_version": InfoField(
        "app_version",
        "the app version, shown in Help → About (for example, 4.6.2)",
        (_p(r"\b(?:v|version\s*)?(\d+\.\d+\.\d+)\b"),),
    ),
    "invoice_number": InfoField(
        "invoice_number",
        "the invoice number (it looks like INV-123456 and is listed under Settings → Billing → Invoices)",
        (_p(r"\bINV-\d{6}\b"),),
    ),
    "webhook_id": InfoField(
        "webhook_id",
        "the webhook ID from Developer settings → Webhooks (it starts with wh_)",
        (_p(r"\bwh_[a-z0-9]{6,}\b"),),
    ),
}

# Not a field an article can require: asked for when the ticket is too vague to triage.
ISSUE_DETAILS = "issue_details"
ISSUE_DETAILS_QUESTION = (
    "which part of Quillstack is affected (for example the desktop app, uploads, billing or sign-in), "
    "what you expected to happen, and any error message you see"
)


def question_for(name: str) -> str:
    if name == ISSUE_DETAILS:
        return ISSUE_DETAILS_QUESTION
    return FIELDS[name].question


def extract_info(text: str) -> Dict[str, str]:
    """Return {field name: value} for every field found in `text`."""
    found = {}
    for name, field in FIELDS.items():
        value = field.find(text)
        if value:
            found[name] = value
    return found
