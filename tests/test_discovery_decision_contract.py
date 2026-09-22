from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from net_working_platform.application.discovery_decisions import (
    DiscoveryDecisionAction,
    DiscoveryDecisionValidationError,
    build_discovery_turn_json_schema,
    execute_discovery_decision,
    parse_discovery_decision,
)


def test_parse_discovery_request_contact_decision() -> None:
    decision = parse_discovery_decision(
        {
            "action": "request_contact",
            "actor_agent_id": "marketing_client_agent_1",
            "target_agent_id": "marketing_principal_agent",
            "field": "marketing",
            "reason": "Relevant marketing opportunity.",
            "criteria": {"role_field": "marketing"},
        }
    )

    assert decision.action == DiscoveryDecisionAction.REQUEST_CONTACT
    assert decision.payload["target_agent_id"] == "marketing_principal_agent"


def test_parse_discovery_decision_rejects_unknown_action() -> None:
    with pytest.raises(DiscoveryDecisionValidationError, match="unsupported action"):
        parse_discovery_decision(
            {
                "action": "crawl_graph",
                "actor_agent_id": "agent_1",
                "target_agent_id": "agent_2",
                "field": "marketing",
                "reason": "Nope.",
                "criteria": {"role_field": "marketing"},
            }
        )


def test_discovery_turn_schema_constrains_targets_and_fields() -> None:
    schema = build_discovery_turn_json_schema(
        actor_agent_id="marketing_client_agent_1",
        valid_actions=["probe_weak_connection", "request_contact"],
        discoverable_agent_ids=["marketing_client_agent_2", "marketing_principal_agent"],
        fields=["marketing"],
    )

    assert schema["properties"]["action"] == {"type": "string", "enum": ["probe_weak_connection", "request_contact"]}
    assert schema["properties"]["actor_agent_id"] == {"type": "string", "enum": ["marketing_client_agent_1"]}
    assert schema["properties"]["target_agent_id"] == {"type": "string", "enum": ["marketing_client_agent_2", "marketing_principal_agent"]}
    assert schema["properties"]["field"] == {"type": "string", "enum": ["marketing"]}


@dataclass
class RecordingDiscoveryService:
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)

    def probe_weak_connection(self, *, actor_agent_id: str, target_agent_id: str, field: str, criteria: dict[str, object]) -> None:
        self.calls.append(("probe_weak_connection", {"actor_agent_id": actor_agent_id, "target_agent_id": target_agent_id, "field": field, "criteria": criteria}))

    def request_contact(self, *, actor_agent_id: str, target_agent_id: str, field: str, reason: str) -> dict[str, object]:
        self.calls.append(("request_contact", {"actor_agent_id": actor_agent_id, "target_agent_id": target_agent_id, "field": field, "reason": reason}))
        return {"state": "active"}


def test_execute_discovery_decision_uses_service() -> None:
    service = RecordingDiscoveryService()
    decision = parse_discovery_decision(
        {
            "action": "request_contact",
            "actor_agent_id": "marketing_client_agent_1",
            "target_agent_id": "marketing_principal_agent",
            "field": "marketing",
            "reason": "Relevant marketing opportunity.",
            "criteria": {"role_field": "marketing"},
        }
    )

    result = execute_discovery_decision(decision, service)

    assert service.calls == [
        (
            "request_contact",
            {
                "actor_agent_id": "marketing_client_agent_1",
                "target_agent_id": "marketing_principal_agent",
                "field": "marketing",
                "reason": "Relevant marketing opportunity.",
            },
        )
    ]
    assert result == {"executed": True, "action": "request_contact", "result": {"state": "active"}}
