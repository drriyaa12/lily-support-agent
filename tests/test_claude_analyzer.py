"""ClaudeAnalyzer against a fake client shaped like the Anthropic SDK (no network, no key)."""
import copy
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from tests.helpers import make_ticket
from lily.agent import build_agent, load_resources
from lily.claude_analyzer import ClaudeAnalyzer, ReplayAnalyzer


class FakeMessages:
    def __init__(self, response):
        self.response, self.calls = response, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class RaisingMessages:
    def __init__(self, error):
        self.error = error

    def create(self, **kwargs):
        raise self.error


class APIConnectionError(Exception):
    """Same name as the SDK's connection error. The analyzer classifies errors by class name and status code."""


class APIStatusError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def raising_client(error):
    return SimpleNamespace(messages=RaisingMessages(error), beta=SimpleNamespace(messages=RaisingMessages(error)))


class CleanEnvironment(unittest.TestCase):
    """Review finding: exported SUPPORT_AGENT_* variables changed what these tests saw."""

    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("SUPPORT_AGENT_MODEL", "SUPPORT_AGENT_EFFORT"):
            os.environ.pop(name, None)


class FakeClient:
    """The two SDK entry points the analyzer may call: client.messages and client.beta.messages."""

    def __init__(self, response):
        self.messages = FakeMessages(response)
        self.beta = SimpleNamespace(messages=FakeMessages(response))


def sdk_message(payload=None, stop_reason="end_turn", text=None, category=None):
    """Shaped like an SDK Message: an (empty, default-display) thinking block, then the JSON text block."""
    return SimpleNamespace(
        id="msg_test", type="message", role="assistant", model="claude-opus-5-5",
        content=[SimpleNamespace(type="thinking", thinking="", signature="sig"),
                 SimpleNamespace(type="text", text=text if text is not None else json.dumps(payload), citations=None)],
        stop_reason=stop_reason, stop_sequence=None,
        stop_details=(SimpleNamespace(type="refusal", category=category, explanation="declined")
                      if stop_reason == "refusal" else None),
        usage=SimpleNamespace(input_tokens=1200, output_tokens=300, cache_creation_input_tokens=0,
                              cache_read_input_tokens=0),
    )


TICKET = make_ticket("Files I edit on my Mac (macOS 14) aren't syncing to the web app. I've updated the app and "
                     "signed out and back in, but it didn't help.", subject="Desktop not syncing",
                     created_at="2026-10-22T11:35:00Z")

PAYLOAD = {
    "summary": "Desktop edits on macOS 14 are not syncing; updating and re-signing in did not help.",
    "core_issue": "Desktop app changes do not sync.",
    "relevant_article_ids": ["KB-104"],
    "evidence": [{"source_id": "KB-104",
                  "quote": "Use this guide when edits made in the Quillstack desktop app do not appear on other "
                           "devices or for teammates, or the app shows \"Syncing…\" for a long time.",
                  "supports": "Same symptom."}],
    "provided_info": [{"field": "os", "value": "macOS 14"}],
    "attempted_steps": [
        {"article_id": "KB-104", "step": 1, "how": "customer_reported", "quote": "I've updated the app"},
        {"article_id": "KB-104", "step": 2, "how": "customer_reported", "quote": "signed out and back in"},
    ],
    "reports_failure": True,
    "conflicts": [{"topic": "sync log", "article_a": "KB-104", "says_a": "a", "article_b": "KB-107",
                   "says_b": "b", "matters_for_ticket": False, "why": "not relevant"}],
    "low_information": False,
}


class ClaudeAnalyzerTests(CleanEnvironment):
    @classmethod
    def setUpClass(cls):
        _, cls.index, _ = load_resources()

    def run_analyzer(self, response, **kwargs):
        client = FakeClient(response)
        analyzer = ClaudeAnalyzer(client=client, **kwargs)
        return analyzer.analyze(TICKET, self.index.search(TICKET.customer_text)), client

    def test_request_uses_structured_output_effort_and_server_fallbacks(self):
        _, client = self.run_analyzer(sdk_message(PAYLOAD))
        self.assertEqual(client.messages.calls, [])
        call = client.beta.messages.calls[0]
        self.assertEqual(call["model"], "claude-opus-5-5")
        self.assertEqual(call["betas"], ["server-side-fallback-2026-07-01"])
        self.assertEqual(call["fallbacks"], "default")
        self.assertEqual(call["output_config"]["effort"], "medium")
        self.assertEqual(call["output_config"]["format"]["type"], "json_schema")
        self.assertNotIn("temperature", call)
        content = call["messages"][0]["content"]
        self.assertIn("Desktop not syncing", content)
        self.assertIn('id="KB-104"', content)

    def test_model_without_server_fallback_uses_the_standard_endpoint(self):
        _, client = self.run_analyzer(sdk_message(PAYLOAD), model="claude-haiku-5-5")
        self.assertEqual(client.beta.messages.calls, [])
        self.assertNotIn("fallbacks", client.messages.calls[0])

    def test_output_becomes_an_analysis(self):
        analysis, _ = self.run_analyzer(sdk_message(PAYLOAD))
        self.assertIsNone(analysis.error)
        self.assertEqual(analysis.relevant_ids, ["KB-104"])
        self.assertEqual(analysis.provided_info, {"os": "macOS 14"})
        self.assertEqual([(a.article_id, a.step) for a in analysis.attempted], [("KB-104", 1), ("KB-104", 2)])
        self.assertFalse(analysis.conflicts[0].matters)

    def test_refusal_becomes_an_analysis_error(self):
        analysis, _ = self.run_analyzer(sdk_message(stop_reason="refusal", text="", category="cyber"))
        self.assertIn("refused", analysis.error)

    def test_truncated_output_becomes_an_analysis_error(self):
        analysis, _ = self.run_analyzer(sdk_message(stop_reason="max_tokens", text='{"summary": "cut'))
        self.assertIn("max_tokens", analysis.error)

    def test_invalid_json_becomes_an_analysis_error(self):
        analysis, _ = self.run_analyzer(sdk_message(text="not json"))
        self.assertIn("unreadable", analysis.error)

    def test_saved_output_replays_to_the_same_analysis(self):
        with tempfile.TemporaryDirectory() as raw_dir:
            original, _ = self.run_analyzer(sdk_message(PAYLOAD), raw_dir=raw_dir)
            replayed = ReplayAnalyzer(raw_dir).analyze(TICKET, [])
        self.assertEqual(replayed.source, "replay")
        self.assertEqual((replayed.relevant_ids, replayed.attempted, replayed.evidence),
                         (original.relevant_ids, original.attempted, original.evidence))


class ClaudeErrorTests(CleanEnvironment):
    def test_transient_api_errors_become_analysis_errors(self):
        for error in (APIConnectionError("connection reset"), APIStatusError(529), APIStatusError(429)):
            with self.subTest(error=repr(error)):
                analysis = ClaudeAnalyzer(client=raising_client(error)).analyze(TICKET, [])
                self.assertIn("API error", analysis.error)

    def test_configuration_errors_still_stop_the_run(self):
        with self.assertRaises(APIStatusError):
            ClaudeAnalyzer(client=raising_client(APIStatusError(401))).analyze(TICKET, [])

    def test_environment_overrides_model_and_effort(self):
        os.environ.update(SUPPORT_AGENT_MODEL="claude-sonnet-5-5", SUPPORT_AGENT_EFFORT="high")
        analyzer = ClaudeAnalyzer(client=FakeClient(sdk_message(PAYLOAD)))
        self.assertEqual((analyzer.model, analyzer.effort), ("claude-sonnet-5-5", "high"))


class ClaudeGuardrailTests(CleanEnvironment):
    def test_invented_quote_and_unretrieved_article_are_dropped_before_deciding(self):
        payload = copy.deepcopy(PAYLOAD)
        payload["relevant_article_ids"] = ["KB-104", "KB-402"]
        payload["evidence"].append({"source_id": "KB-104", "quote": "Sync always recovers on its own within a day.",
                                    "supports": "invented"})
        agent = build_agent(ClaudeAnalyzer(client=FakeClient(sdk_message(payload))))
        result = agent.handle(TICKET)
        self.assertEqual([a.id for a in result.investigation.relevant], ["KB-104"])
        self.assertEqual([e.supports for e in result.investigation.evidence], ["Same symptom."])
        self.assertEqual((result.decision.action, result.offered_steps), ("resolve", [3, 4]))


if __name__ == "__main__":
    unittest.main()
