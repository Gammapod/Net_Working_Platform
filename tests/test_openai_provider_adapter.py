from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from net_working_platform.application.llm_decisions import LlmDecisionAction, build_turn_decision_json_schema
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
                            "text": '{"action":"defer","actor_agent_id":"agent_2","negotiation_id":"","reason":"needs_more_information","body":"","proposal":{"summary":"","details":""}}',
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
                            "text": '{"action":"accept_negotiation","negotiation_id":"negotiation_1","actor_agent_id":"agent_2","reason":"not used","body":"","proposal":{"summary":"","details":""}}',
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


def test_openai_adapter_accepts_turn_specific_schema_override() -> None:
    """Protects INV-L-006."""
    turn_schema = build_turn_decision_json_schema(
        valid_actions=["accept_match", "close_negotiation"],
        actor_agent_id="agent_1",
        negotiation_id="negotiation_1",
    )
    opener = FakeOpener(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"action":"accept_match","negotiation_id":"negotiation_1","actor_agent_id":"agent_1"}',
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
        json_schema=turn_schema,
        opener=opener,
    )

    assert opener.captured_payload is not None
    assert opener.captured_payload["text"] == {
        "format": {
            "type": "json_schema",
            "name": "llm_decision",
            "schema": turn_schema,
            "strict": True,
        }
    }
    assert decision.action == LlmDecisionAction.ACCEPT_MATCH


def test_openai_adapter_normalizes_schema_constrained_message_decision() -> None:
    """Protects INV-L-006."""
    opener = FakeOpener(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"action":"send_message","negotiation_id":"negotiation_1","actor_agent_id":"agent_2","reason":"","body":"Can you clarify?","proposal":{"summary":"","details":""}}',
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

    assert decision.action == LlmDecisionAction.SEND_MESSAGE
    assert decision.payload == {
        "negotiation_id": "negotiation_1",
        "actor_agent_id": "agent_2",
        "body": "Can you clarify?",
    }


def test_openai_adapter_normalizes_schema_constrained_attached_fact_disclosures() -> None:
    """Protects INV-L-006."""
    opener = FakeOpener(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"action":"send_message","negotiation_id":"negotiation_1","actor_agent_id":"client_agent","reason":"","body":"Sharing compensation context.","disclose_fact_fields":["salary_range","career_path"],"proposal":{"summary":"","details":""}}',
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

    assert decision.action == LlmDecisionAction.SEND_MESSAGE
    assert decision.payload == {
        "negotiation_id": "negotiation_1",
        "actor_agent_id": "client_agent",
        "body": "Sharing compensation context.",
        "disclose_fact_fields": ["salary_range", "career_path"],
    }


def test_openai_adapter_normalizes_schema_constrained_reject_decision() -> None:
    """Protects INV-L-006."""
    opener = FakeOpener(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"action":"reject_negotiation","negotiation_id":"negotiation_1","actor_agent_id":"agent_2","reason":"not proceeding","body":"provider-only","proposal":{"summary":"","details":""}}',
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

    assert decision.action == LlmDecisionAction.REJECT_NEGOTIATION
    assert decision.payload == {
        "negotiation_id": "negotiation_1",
        "actor_agent_id": "agent_2",
        "reason": "not proceeding",
    }


def test_openai_adapter_normalizes_schema_constrained_propose_match_decision() -> None:
    """Protects INV-L-006."""
    opener = FakeOpener(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"action":"propose_match","negotiation_id":"negotiation_1","actor_agent_id":"agent_2","reason":"","body":"","proposal":{"summary":"Match candidate to principal need","details":"Evidence and terms can be reviewed in event history."}}',
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

    assert decision.action == LlmDecisionAction.PROPOSE_MATCH
    assert decision.payload == {
        "negotiation_id": "negotiation_1",
        "actor_agent_id": "agent_2",
        "proposal": {
            "summary": "Match candidate to principal need",
            "details": "Evidence and terms can be reviewed in event history.",
        },
    }


def test_openai_adapter_normalizes_schema_constrained_accept_match_decision() -> None:
    """Protects INV-L-006."""
    opener = FakeOpener(
        {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"action":"accept_match","negotiation_id":"negotiation_1","actor_agent_id":"agent_1","reason":"","body":"","proposal":{"summary":"","details":""}}',
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

    assert decision.action == LlmDecisionAction.ACCEPT_MATCH
    assert decision.payload == {
        "negotiation_id": "negotiation_1",
        "actor_agent_id": "agent_1",
    }


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
