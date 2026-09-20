from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from net_working_platform.domain.model import NegotiationDecision


class LlmDecisionAction(StrEnum):
    ACCEPT_NEGOTIATION = "accept_negotiation"
    REJECT_NEGOTIATION = "reject_negotiation"
    SEND_MESSAGE = "send_message"
    PROPOSE_MATCH = "propose_match"
    ACCEPT_MATCH = "accept_match"
    CLOSE_NEGOTIATION = "close_negotiation"
    DEFER = "defer"


class LlmDecisionValidationError(ValueError):
    pass


class LlmDecisionExecutionError(ValueError):
    pass


@dataclass(frozen=True)
class LlmDecision:
    action: LlmDecisionAction
    payload: dict[str, object]


class LlmNegotiationService(Protocol):
    def respond_to_negotiation(
        self,
        *,
        negotiation_id: str,
        actor_agent_id: str,
        decision: NegotiationDecision,
    ) -> object: ...


_STRING_FIELDS = {"action", "negotiation_id", "actor_agent_id", "body", "reason"}
_OBJECT_FIELDS = {"proposal"}

_ACTION_FIELDS: dict[LlmDecisionAction, tuple[set[str], set[str]]] = {
    LlmDecisionAction.ACCEPT_NEGOTIATION: (
        {"action", "negotiation_id", "actor_agent_id"},
        set(),
    ),
    LlmDecisionAction.REJECT_NEGOTIATION: (
        {"action", "negotiation_id", "actor_agent_id"},
        {"reason"},
    ),
    LlmDecisionAction.SEND_MESSAGE: (
        {"action", "negotiation_id", "actor_agent_id", "body"},
        set(),
    ),
    LlmDecisionAction.PROPOSE_MATCH: (
        {"action", "negotiation_id", "actor_agent_id", "proposal"},
        set(),
    ),
    LlmDecisionAction.ACCEPT_MATCH: (
        {"action", "negotiation_id", "actor_agent_id"},
        set(),
    ),
    LlmDecisionAction.CLOSE_NEGOTIATION: (
        {"action", "negotiation_id", "actor_agent_id", "reason"},
        set(),
    ),
    LlmDecisionAction.DEFER: (
        {"action", "actor_agent_id", "reason"},
        set(),
    ),
}


def parse_llm_decision(raw: dict[str, Any]) -> LlmDecision:
    """Parse and validate one LLM-facing decision signal.

    Protects INV-L-001, INV-L-002, and INV-L-003.
    """
    if not isinstance(raw, dict):
        raise LlmDecisionValidationError("decision must be an object")

    action_value = raw.get("action")
    if not isinstance(action_value, str):
        raise LlmDecisionValidationError("missing required field: action")

    try:
        action = LlmDecisionAction(action_value)
    except ValueError as exc:
        raise LlmDecisionValidationError(f"unsupported action: {action_value}") from exc

    required_fields, optional_fields = _ACTION_FIELDS[action]
    allowed_fields = required_fields | optional_fields

    for field in sorted(required_fields):
        if field not in raw:
            raise LlmDecisionValidationError(f"missing required field: {field}")

    for field in raw:
        if field not in allowed_fields:
            raise LlmDecisionValidationError(f"unexpected field: {field}")

    for field in sorted(allowed_fields):
        if field in raw:
            _validate_field_type(field, raw[field])

    return LlmDecision(
        action=action,
        payload={field: raw[field] for field in raw if field != "action"},
    )


def _validate_field_type(field: str, value: object) -> None:
    if field in _STRING_FIELDS and not isinstance(value, str):
        raise LlmDecisionValidationError(f"field {field} must be string")
    if field in _OBJECT_FIELDS and not isinstance(value, dict):
        raise LlmDecisionValidationError(f"field {field} must be object")


def execute_llm_decision(decision: LlmDecision, service: LlmNegotiationService) -> dict[str, object]:
    """Execute a validated LLM decision through application services.

    Protects INV-L-004. Initial execution support is intentionally limited to
    requested-negotiation response decisions and explicit defer.
    """
    if decision.action == LlmDecisionAction.ACCEPT_NEGOTIATION:
        result = service.respond_to_negotiation(
            negotiation_id=_required_string(decision, "negotiation_id"),
            actor_agent_id=_required_string(decision, "actor_agent_id"),
            decision=NegotiationDecision.ACCEPT,
        )
        return {"executed": True, "action": decision.action.value, "result": result}

    if decision.action == LlmDecisionAction.REJECT_NEGOTIATION:
        result = service.respond_to_negotiation(
            negotiation_id=_required_string(decision, "negotiation_id"),
            actor_agent_id=_required_string(decision, "actor_agent_id"),
            decision=NegotiationDecision.REJECT,
        )
        return {"executed": True, "action": decision.action.value, "result": result}

    if decision.action == LlmDecisionAction.DEFER:
        return {
            "executed": False,
            "action": decision.action.value,
            "reason": _required_string(decision, "reason"),
            "actor_agent_id": _required_string(decision, "actor_agent_id"),
        }

    raise LlmDecisionExecutionError(f"execution not implemented for action: {decision.action.value}")


def _required_string(decision: LlmDecision, field: str) -> str:
    value = decision.payload[field]
    if not isinstance(value, str):
        raise LlmDecisionExecutionError(f"field {field} must be string")
    return value
