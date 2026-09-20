from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from net_working_platform.application.llm_decisions import (
    LLM_DECISION_JSON_SCHEMA,
    LlmDecisionAction,
    execute_llm_decision,
    parse_llm_decision,
)
from net_working_platform.domain.model import Negotiation, ProtocolEvent
from net_working_platform.storage.repositories import SqlNegotiationRepository, SqlProtocolEventRepository
from net_working_platform.storage.services import create_sql_negotiation_service
from tests.support.llm_scenarios import seed_inbound_request_scenario


EXECUTOR_SUPPORTED_ACTIONS = ["accept_negotiation", "reject_negotiation", "defer"]
LLM_DECISION_CONTRACT_PATH = "docs/source-of-truth/llm-decision-contract.md"
PROMPT_TEMPLATE = """You are acting as the representative agent identified by agent_id in the decision context.

You may choose exactly one protocol decision. Return only one JSON object.
Do not include markdown, commentary, or extra keys.

Allowed actions are defined by the LLM Decision Contract:
- accept_negotiation
- reject_negotiation
- send_message
- propose_match
- accept_match
- close_negotiation
- defer

For this experiment, prefer one of:
- accept_negotiation
- reject_negotiation
- defer

Decision context:
<CONTEXT_JSON>

Return one JSON object now."""


def build_context_package(*, db_url: str, max_active_negotiations: int = 5) -> dict[str, object]:
    """Build a provider-neutral prompt/context package without executing a decision."""
    scenario = seed_inbound_request_scenario(db_url)
    engine = create_engine(db_url)
    with engine.begin() as connection:
        events = SqlProtocolEventRepository(connection).list_for_negotiation(scenario.negotiation_id)

    return {
        "mode": "context_only",
        "scenario": _scenario_record(scenario),
        "contract": {
            "path": LLM_DECISION_CONTRACT_PATH,
            "executor_supported_actions": EXECUTOR_SUPPORTED_ACTIONS,
        },
        "llm_decision_json_schema": LLM_DECISION_JSON_SCHEMA,
        "response_format": {
            "type": "json_schema",
            "json_schema": LLM_DECISION_JSON_SCHEMA,
        },
        "prompt": PROMPT_TEMPLATE.replace(
            "<CONTEXT_JSON>",
            json.dumps(
                _decision_context_with_capacity(scenario.decision_context, max_active_negotiations),
                sort_keys=True,
            ),
        ),
        "decision_context": _decision_context_with_capacity(scenario.decision_context, max_active_negotiations),
        "event_log_source": "protocol_events",
        "structured_event_log": [_event_to_record(event) for event in events],
    }


def build_fit_context_package(
    *,
    db_url: str,
    request_subject: dict[str, object],
    observing_agent_fit_criteria: dict[str, object],
    max_active_negotiations: int = 5,
) -> dict[str, object]:
    """Build a provider-neutral context package for fit-quality experiments."""
    scenario = seed_inbound_request_scenario(db_url, subject=request_subject)
    engine = create_engine(db_url)
    with engine.begin() as connection:
        events = SqlProtocolEventRepository(connection).list_for_negotiation(scenario.negotiation_id)

    decision_context = {
        **_decision_context_with_capacity(scenario.decision_context, max_active_negotiations),
        "observing_agent_fit_criteria": observing_agent_fit_criteria,
    }
    return {
        "mode": "context_only",
        "scenario": _scenario_record(scenario),
        "contract": {
            "path": LLM_DECISION_CONTRACT_PATH,
            "executor_supported_actions": EXECUTOR_SUPPORTED_ACTIONS,
        },
        "llm_decision_json_schema": LLM_DECISION_JSON_SCHEMA,
        "response_format": {
            "type": "json_schema",
            "json_schema": LLM_DECISION_JSON_SCHEMA,
        },
        "prompt": PROMPT_TEMPLATE.replace("<CONTEXT_JSON>", json.dumps(decision_context, sort_keys=True)),
        "decision_context": decision_context,
        "event_log_source": "protocol_events",
        "structured_event_log": [_event_to_record(event) for event in events],
    }


def run_supervised_experiment(*, db_url: str, raw_decision: dict[str, Any]) -> dict[str, object]:
    """Run the current dev-only supervised LLM experiment.

    The returned structured event log is backed by the database `protocol_events`
    table through `SqlProtocolEventRepository`, matching the history surface used
    by application services.
    """
    scenario = seed_inbound_request_scenario(db_url)
    decision = parse_llm_decision(raw_decision)

    engine = create_engine(db_url)
    with engine.begin() as connection:
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: "unused",
            now=lambda: datetime(2026, 1, 8, 12, 5, tzinfo=timezone.utc),
        )
        execution_result = execute_llm_decision(decision, service)
        events = SqlProtocolEventRepository(connection).list_for_negotiation(scenario.negotiation_id)

    return {
        "scenario": _scenario_record(scenario),
        "decision_context": scenario.decision_context,
        "raw_decision": raw_decision,
        "validation": {"valid": True, "action": decision.action.value},
        "execution": _jsonable_execution_result(execution_result),
        "event_log_source": "protocol_events",
        "structured_event_log": [_event_to_record(event) for event in events],
    }


def execute_decision_against_existing_scenario(*, db_url: str, raw_decision: dict[str, Any]) -> dict[str, object]:
    """Execute a decision against an already prepared inbound-request scenario."""
    decision = parse_llm_decision(raw_decision)

    engine = create_engine(db_url)
    with engine.begin() as connection:
        negotiation_id = _existing_scenario_negotiation_id(decision, SqlNegotiationRepository(connection))
        negotiation = SqlNegotiationRepository(connection).get(negotiation_id)
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: "unused",
            now=lambda: datetime(2026, 1, 8, 12, 5, tzinfo=timezone.utc),
        )
        execution_result = execute_llm_decision(decision, service)
        events = SqlProtocolEventRepository(connection).list_for_negotiation(negotiation_id)

    return {
        "scenario": _scenario_record_from_negotiation(negotiation),
        "raw_decision": raw_decision,
        "validation": {"valid": True, "action": decision.action.value},
        "execution": _jsonable_execution_result(execution_result),
        "event_log_source": "protocol_events",
        "structured_event_log": [_event_to_record(event) for event in events],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a dev-only supervised LLM experiment.")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--decision-json")
    parser.add_argument("--decision-file")
    parser.add_argument("--context-only", action="store_true")
    parser.add_argument("--use-existing-scenario", action="store_true")
    parser.add_argument("--max-active-negotiations", type=int, default=5)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    if args.context_only:
        if args.decision_json or args.decision_file:
            raise SystemExit("--context-only cannot be combined with --decision-json or --decision-file")
        result = build_context_package(
            db_url=args.db_url,
            max_active_negotiations=args.max_active_negotiations,
        )
    else:
        raw_decision = _load_decision(args.decision_json, args.decision_file)
        if args.use_existing_scenario:
            result = execute_decision_against_existing_scenario(db_url=args.db_url, raw_decision=raw_decision)
        else:
            result = run_supervised_experiment(db_url=args.db_url, raw_decision=raw_decision)

    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0


def _load_decision(decision_json: str | None, decision_file: str | None) -> dict[str, Any]:
    if bool(decision_json) == bool(decision_file):
        raise SystemExit("provide exactly one of --decision-json or --decision-file")

    if decision_json is not None:
        loaded = json.loads(decision_json)
    else:
        loaded = json.loads(Path(decision_file or "").read_text(encoding="utf-8"))

    if not isinstance(loaded, dict):
        raise SystemExit("decision must be a JSON object")
    return loaded


def _jsonable_execution_result(result: dict[str, object]) -> dict[str, object]:
    return {key: _jsonable(value) for key, value in result.items()}


def _jsonable(value: object) -> object:
    if isinstance(value, Negotiation):
        return {
            "id": value.id,
            "from_agent_id": value.from_agent_id,
            "to_agent_id": value.to_agent_id,
            "state": value.state.value,
            "subject": value.subject,
        }
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _scenario_record(scenario: object) -> dict[str, str]:
    return {
        "name": "inbound_request",
        "observing_agent_id": scenario.observing_agent_id,
        "requesting_agent_id": scenario.requesting_agent_id,
        "negotiation_id": scenario.negotiation_id,
    }


def _scenario_record_from_negotiation(negotiation: Negotiation) -> dict[str, str]:
    return {
        "name": "inbound_request",
        "observing_agent_id": negotiation.to_agent_id,
        "requesting_agent_id": negotiation.from_agent_id,
        "negotiation_id": negotiation.id,
    }


def _decision_negotiation_id(decision: object) -> str:
    negotiation_id = decision.payload.get("negotiation_id")
    if not isinstance(negotiation_id, str):
        raise SystemExit("decision must include a negotiation_id for existing-scenario execution")
    return negotiation_id


def _decision_actor_agent_id(decision: object) -> str:
    actor_agent_id = decision.payload.get("actor_agent_id")
    if not isinstance(actor_agent_id, str):
        raise SystemExit("decision must include an actor_agent_id for existing-scenario execution")
    return actor_agent_id


def _existing_scenario_negotiation_id(decision: object, negotiations: SqlNegotiationRepository) -> str:
    if decision.action != LlmDecisionAction.DEFER:
        return _decision_negotiation_id(decision)

    active_negotiations = negotiations.list_active_for_agent(_decision_actor_agent_id(decision))
    if len(active_negotiations) != 1:
        raise SystemExit("defer existing-scenario execution requires exactly one active negotiation")
    return active_negotiations[0].id


def _decision_context_with_capacity(
    decision_context: dict[str, object],
    max_active_negotiations: int,
) -> dict[str, object]:
    active_load = decision_context.get("active_load")
    if not isinstance(active_load, int):
        raise ValueError("decision context active_load must be an integer")
    return {
        **decision_context,
        "max_active_negotiations": max_active_negotiations,
        "capacity_remaining": max(max_active_negotiations - active_load, 0),
    }


def _event_to_record(event: ProtocolEvent) -> dict[str, object]:
    return {
        "type": event.type.value,
        "actor_agent_id": event.actor_agent_id,
        "negotiation_id": event.negotiation_id,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": event.payload,
    }


if __name__ == "__main__":
    raise SystemExit(main())
