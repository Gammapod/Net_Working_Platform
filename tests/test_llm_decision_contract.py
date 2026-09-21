from __future__ import annotations

import pytest

from net_working_platform.application.llm_decisions import (
    LLM_DECISION_JSON_SCHEMA,
    LlmDecisionAction,
    LlmDecisionValidationError,
    build_turn_decision_json_schema,
    parse_llm_decision,
)


def test_parse_llm_accept_negotiation_decision() -> None:
    """Protects INV-L-001 and INV-L-002."""
    decision = parse_llm_decision(
        {
            "action": "accept_negotiation",
            "negotiation_id": "negotiation_1",
            "actor_agent_id": "agent_2",
        }
    )

    assert decision.action == LlmDecisionAction.ACCEPT_NEGOTIATION
    assert decision.payload == {
        "negotiation_id": "negotiation_1",
        "actor_agent_id": "agent_2",
    }


def test_parse_llm_decision_rejects_unknown_action() -> None:
    """Protects INV-L-001."""
    with pytest.raises(LlmDecisionValidationError, match="unsupported action"):
        parse_llm_decision(
            {
                "action": "delete_database",
                "actor_agent_id": "agent_2",
            }
        )


def test_parse_llm_decision_requires_action_specific_fields() -> None:
    """Protects INV-L-002."""
    with pytest.raises(LlmDecisionValidationError, match="missing required field: body"):
        parse_llm_decision(
            {
                "action": "send_message",
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_2",
            }
        )

    with pytest.raises(LlmDecisionValidationError, match="field proposal must be object"):
        parse_llm_decision(
            {
                "action": "propose_match",
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_2",
                "proposal": "not an object",
            }
        )


def test_parse_llm_decision_rejects_extra_fields() -> None:
    """Protects INV-L-002."""
    with pytest.raises(LlmDecisionValidationError, match="unexpected field: command"):
        parse_llm_decision(
            {
                "action": "accept_negotiation",
                "negotiation_id": "negotiation_1",
                "actor_agent_id": "agent_2",
                "command": "run arbitrary shell",
            }
        )


def test_parse_llm_defer_decision() -> None:
    """Protects INV-L-003."""
    decision = parse_llm_decision(
        {
            "action": "defer",
            "actor_agent_id": "agent_2",
            "reason": "needs_more_information",
        }
    )

    assert decision.action == LlmDecisionAction.DEFER
    assert decision.payload == {
        "actor_agent_id": "agent_2",
        "reason": "needs_more_information",
    }


def test_llm_decision_json_schema_describes_supported_actions() -> None:
    """Protects INV-L-005."""
    assert LLM_DECISION_JSON_SCHEMA["type"] == "object"
    assert LLM_DECISION_JSON_SCHEMA["oneOf"]
    assert LLM_DECISION_JSON_SCHEMA["additionalProperties"] is False

    action_values = {
        branch["properties"]["action"]["const"]
        for branch in LLM_DECISION_JSON_SCHEMA["oneOf"]
    }
    assert action_values == {
        "accept_negotiation",
        "reject_negotiation",
        "send_message",
        "propose_match",
        "accept_match",
        "close_negotiation",
        "defer",
    }


def test_turn_decision_json_schema_constrains_actions_actor_and_negotiation() -> None:
    """Protects INV-L-005 and INV-L-006."""
    schema = build_turn_decision_json_schema(
        valid_actions=["accept_match", "close_negotiation"],
        actor_agent_id="agent_1",
        negotiation_id="negotiation_1",
    )

    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["action"] == {"type": "string", "enum": ["accept_match", "close_negotiation"]}
    assert schema["properties"]["actor_agent_id"] == {"type": "string", "enum": ["agent_1"]}
    assert schema["properties"]["negotiation_id"] == {"type": "string", "enum": ["negotiation_1"]}
