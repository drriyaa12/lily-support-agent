import unittest

from tests.helpers import DATA, real_kb
from triage.fields import FIELDS
from triage.kb import parse_article

SAMPLE = """---
id: KB-900
title: Sample article
component: sync
updated: 2026-01-01
required_info: [os, app_version]
escalate: always
queue: Technical Support
fact: refund_window_days = 14
fact: max_upload_mb_paid = 250
---
Intro sentence one. Intro sentence two.

## Steps
1. **Do the first thing.** Detail one.
2. **Do the second thing.** Detail two.

## When to escalate
Escalate with logs.
"""


class ParseArticleTests(unittest.TestCase):
    def test_reads_front_matter(self):
        a = parse_article(SAMPLE)
        self.assertEqual(a.id, "KB-900")
        self.assertEqual(a.component, "sync")
        self.assertEqual(a.required_info, ["os", "app_version"])
        self.assertEqual(a.escalate, "always")
        self.assertEqual(a.queue, "Technical Support")
        self.assertEqual(a.facts, {"refund_window_days": "14", "max_upload_mb_paid": "250"})

    def test_reads_numbered_steps(self):
        steps = parse_article(SAMPLE).steps
        self.assertEqual([s.number for s in steps], [1, 2])
        self.assertEqual(steps[0].title, "Do the first thing")
        self.assertEqual(steps[1].detail, "Detail two.")

    def test_reads_intro_and_escalation_note(self):
        a = parse_article(SAMPLE)
        self.assertEqual(a.intro, "Intro sentence one. Intro sentence two.")
        self.assertEqual(a.escalation_note, "Escalate with logs.")

    def test_defaults_when_optional_keys_missing(self):
        a = parse_article("---\nid: KB-1\ntitle: T\ncomponent: c\n---\nBody only.\n")
        self.assertEqual(a.required_info, [])
        self.assertEqual(a.escalate, "when_steps_fail")
        self.assertEqual(a.steps, [])
        self.assertEqual(a.facts, {})

    def test_rejects_missing_front_matter(self):
        with self.assertRaises(ValueError):
            parse_article("No front matter here.")

    def test_rejects_unknown_escalation_mode(self):
        with self.assertRaises(ValueError):
            parse_article("---\nid: KB-1\ntitle: T\ncomponent: c\nescalate: sometimes\n---\nBody.\n")


class RepositoryKbTests(unittest.TestCase):
    """Integrity checks on the shipped KB, so a typo in an article fails loudly."""

    def test_article_ids_match_file_names(self):
        kb = real_kb()
        files = sorted(p.stem for p in (DATA / "kb").glob("*.md"))
        self.assertEqual(sorted(kb), files)

    def test_required_info_uses_known_fields(self):
        for article in real_kb().values():
            for name in article.required_info:
                self.assertIn(name, FIELDS, f"{article.id} requires unknown field {name}")

    def test_steps_are_numbered_from_one_without_gaps(self):
        for article in real_kb().values():
            numbers = [s.number for s in article.steps]
            self.assertEqual(numbers, list(range(1, len(numbers) + 1)), article.id)


if __name__ == "__main__":
    unittest.main()
