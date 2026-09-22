from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class DiscoveryDecisionAction(StrEnum):
    PROBE_WEAK_CONNECTION = "probe_weak_connection"
    REQUEST_CONTACT = "request_contact"
    REQUEST_NEGOTIATION = "request_negotiation"
    DEFER = "defer"


class DiscoveryDecisionValidationError(ValueError):
    pass


@dataclass(frozen=True)
class DiscoveryDecision:
    action: DiscoveryDecisionAction
    payload: dict[str, object]


class DiscoveryServicePort(Protocol):
    def probe_weak_connection(
        self,
        *,
        actor_agent_id: str,
        target_agent_id: str,
        field: str,
        criteria: dict[str, object],
    ) -> object: ...

    def request_contact(
        self,
        *,
        actor_agent_id: str,
        target_agent_id: str,
        field: str,
        reason: str,
    ) -> object: ...


DISCOVERY_DECISION_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "actor_agent_id", "target_agent_id", "field", "reason", "criteria"],
    "properties": {
        "action": {
            "type": "string",
        "enum": ["probe_weak_connection", "request_contact", "request_negotiation", "defer"],
        },
        "actor_agent_id": {"type": "string"},
        "target_agent_id": {"type": "string"},
        "field": {"type": "string"},
        "reason": {"type": "string"},
        "criteria": {
            "type": "object",
            "additionalProperties": False,
            "required": ["role_field"],
            "properties": {"role_field": {"type": "string"}},
        },
    },
}


def build_discovery_turn_json_schema(
    *,
    actor_agent_id: str,
    valid_actions: list[str],
    discoverable_agent_ids: list[str],
    fields: list[str],
) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "actor_agent_id", "target_agent_id", "field", "reason", "criteria"],
        "properties": {
            "action": {"type": "string", "enum": valid_actions},
            "actor_agent_id": {"type": "string", "enum": [actor_agent_id]},
            "target_agent_id": {"type": "string", "enum": discoverable_agent_ids or [""]},
            "field": {"type": "string", "enum": fields or [""]},
            "reason": {"type": "string"},
            "criteria": {
                "type": "object",
                "additionalProperties": False,
                "required": ["role_field"],
                "properties": {"role_field": {"type": "string", "enum": fields or [""]}},
            },
        },
    }


def parse_discovery_decision(raw: dict[str, Any]) -> DiscoveryDecision:
    if not isinstance(raw, dict):
        raise DiscoveryDecisionValidationError("decision must be an object")
    action_value = raw.get("action")
    if not isinstance(action_value, str):
        raise DiscoveryDecisionValidationError("missing required field: action")
    try:
        action = DiscoveryDecisionAction(action_value)
    except ValueError as exc:
        raise DiscoveryDecisionValidationError(f"unsupported action: {action_value}") from exc

    required = {"action", "actor_agent_id", "target_agent_id", "field", "reason", "criteria"}
    for field in sorted(required):
        if field not in raw:
            raise DiscoveryDecisionValidationError(f"missing required field: {field}")
    for field in raw:
        if field not in required:
            raise DiscoveryDecisionValidationError(f"unexpected field: {field}")
    for field in ["actor_agent_id", "target_agent_id", "field", "reason"]:
        if not isinstance(raw[field], str):
            raise DiscoveryDecisionValidationError(f"field {field} must be string")
    if not isinstance(raw["criteria"], dict):
        raise DiscoveryDecisionValidationError("field criteria must be object")
    return DiscoveryDecision(action=action, payload={field: raw[field] for field in raw if field != "action"})


def execute_discovery_decision(decision: DiscoveryDecision, service: DiscoveryServicePort) -> dict[str, object]:
    if decision.action == DiscoveryDecisionAction.DEFER:
        return {"executed": False, "action": "defer", "reason": str(decision.payload["reason"])}
    if decision.action == DiscoveryDecisionAction.PROBE_WEAK_CONNECTION:
        result = service.probe_weak_connection(
            actor_agent_id=str(decision.payload["actor_agent_id"]),
            target_agent_id=str(decision.payload["target_agent_id"]),
            field=str(decision.payload["field"]),
            criteria=dict(decision.payload["criteria"]),
        )
        return {"executed": True, "action": decision.action.value, "result": result}
    if decision.action == DiscoveryDecisionAction.REQUEST_CONTACT:
        result = service.request_contact(
            actor_agent_id=str(decision.payload["actor_agent_id"]),
            target_agent_id=str(decision.payload["target_agent_id"]),
            field=str(decision.payload["field"]),
            reason=str(decision.payload["reason"]),
        )
        return {"executed": True, "action": decision.action.value, "result": result}
    raise AssertionError(f"unhandled discovery action: {decision.action}")
