"""Text normalisation shared by retrieval, attempt matching and conflict checks.

Deliberately simple and dependency-free: lowercase, split into words, drop
stopwords, map a few synonyms, and strip common English suffixes. It is a
crude stemmer, but it is the same crude stemmer on both sides of every
comparison, which is what matters here.
"""
from __future__ import annotations

import re
from typing import List

STOPWORDS = set("""
a about above after again against all am an and any are as at be because been before being
below between both but by can cannot could did do does doing down during each few for from
further had has have having he her here hers herself him himself his how i if in into is it
its itself just me more most my myself no nor not now of off on once only or other our ours
ourselves out over own same she should so some such than that the their theirs them
themselves then there these they this those through to too under until up very was we were
what when where which while who whom why will with would you your yours yourself yourselves
also already back even still im ive dont doesnt didnt cant isnt arent wasnt hasnt havent wont
don didn doesn isn aren wasn hasn haven won couldn shouldn wouldn ll re ve
hi hello hey thanks thank please pls asap
app quillstack
get got use using try tried want need know let make help
""".split())

# Applied to the raw lowercase word before stemming.
SYNONYMS = {
    "login": "sign", "logins": "sign", "signin": "sign",
    "invitation": "invite", "invitations": "invite",
    "reboot": "restart", "rebooted": "restart", "rebooting": "restart",
    "megabyte": "mb", "megabytes": "mb",
    "removal": "remove",
    "deletion": "delete",
}

# "log in", "logged out", "logging back in" mean signing in or out; a "sync log" does not.
_LOG_IN_OUT = re.compile(r"\blog(?:ged|ging)?(?=[\s-]+(?:in|out|back|into|on|off)\b)")
_WORD = re.compile(r"[a-z0-9]+")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")


def stem(word: str) -> str:
    """Strip one common suffix, then a trailing 'e' ("updated", "update" -> "updat")."""
    if not word.endswith("ss"):
        for suffix in ("ing", "ed", "es", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 3:
                word = word[: -len(suffix)]
                break
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word


def tokenize(text: str) -> List[str]:
    """Content tokens of `text`, in order, with repeats."""
    tokens = []
    for word in _WORD.findall(_LOG_IN_OUT.sub("sign", text.lower())):
        if len(word) < 2 or word in STOPWORDS:
            continue
        tokens.append(stem(SYNONYMS.get(word, word)))
    return tokens


def sentences(text: str) -> List[str]:
    """Split text into sentences on . ! ? and line breaks."""
    return [s.strip() for s in _SENTENCE_BREAK.split(text) if s and s.strip()]


def normalise_quote(text: str) -> str:
    """Collapse whitespace and straighten quotes so verbatim checks ignore formatting."""
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("**", "")
    return re.sub(r"\s+", " ", text).strip()
