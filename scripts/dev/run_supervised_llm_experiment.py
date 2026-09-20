from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from net_working_platform.application.llm_decisions import execute_llm_decision, parse_llm_decision
from net_working_platform.domain.model import Negotiation, ProtocolEvent
from net_working_platform.storage.repositories import SqlProtocolEventRepository
from net_working_platform.storage.services import create_sql_negotiation_service
from tests.support.llm_scenarios import seed_inbound_request_scenario


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
        "scenario": {
            "name": "inbound_request",
            "observing_agent_id": scenario.observing_agent_id,
            "requesting_agent_id": scenario.requesting_agent_id,
            "negotiation_id": scenario.negotiation_id,
        },
        "decision_context": scenario.decision_context,
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
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    raw_decision = _load_decision(args.decision_json, args.decision_file)
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
