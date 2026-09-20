from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from net_working_platform.application.llm_decisions import LlmDecisionAction
from scripts.dev.openai_provider import OPENAI_EXECUTABLE_DECISION_JSON_SCHEMA, request_openai_decision


@dataclass
class FakeResponse:
    body: dict[str, object]

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.body).encode("utf-8")


@dataclass
class FakeOpener:
    body: dict[str, object]
    captured_url: str | None = None
    captured_headers: dict[str, str] | None = None
    captured_payload: dict[str, object] | None = None

    def __call__(self, request: object, timeout: int) -> FakeResponse:
        del timeout
        self.captured_url = request.full_url
        self.captured_headers = dict(request.header_items())
        self.captured_payload = json.loads(request.data.decode("utf-8"))
        return FakeResponse(self.body)


def test_openai_adapter_builds_schema_constrained_responses_request() -> None:
    """Protects INV-L-006."""
    opener = FakeOpener(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"action":"defer","actor_agent_id":"agent_2","reason":"needs_more_information"}',
                        }
                    ]
                }
            ]
        }
    )

    request_openai_decision(
        prompt="Return a valid decision.",
        api_key="test-key",
        model="gpt-4o-mini",
        opener=opener,
    )

    assert opener.captured_url == "https://api.openai.com/v1/responses"
    assert opener.captured_headers is not None
    assert opener.captured_headers["Authorization"] == "Bearer test-key"
    assert opener.captured_payload is not None
    assert opener.captured_payload["model"] == "gpt-4o-mini"
    assert opener.captured_payload["input"] == "Return a valid decision."
    assert opener.captured_payload["text"] == {
            "format": {
                "type": "json_schema",
                "name": "llm_decision",
                "schema": OPENAI_EXECUTABLE_DECISION_JSON_SCHEMA,
                "strict": True,
            }
        }


def test_openai_adapter_parses_schema_constrained_decision_text() -> None:
    """Protects INV-L-006."""
    opener = FakeOpener(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"action":"accept_negotiation","negotiation_id":"negotiation_1","actor_agent_id":"agent_2","reason":"not used"}',
                        }
                    ]
                }
            ]
        }
    )

    decision = request_openai_decision(
        prompt="Return a valid decision.",
        api_key="test-key",
        model="gpt-4o-mini",
        opener=opener,
    )

    assert decision.action == LlmDecisionAction.ACCEPT_NEGOTIATION
    assert decision.payload == {"negotiation_id": "negotiation_1", "actor_agent_id": "agent_2"}


def test_openai_adapter_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Protects INV-L-006."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        request_openai_decision(
            prompt="Return a valid decision.",
            api_key=None,
            model="gpt-4o-mini",
            opener=FakeOpener({"output": []}),
        )
