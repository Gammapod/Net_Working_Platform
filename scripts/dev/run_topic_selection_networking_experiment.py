from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url

from net_working_platform.experiments.scenarios import (
    MultiPartyContactScenario,
    seed_ambiguous_multi_party_contact_scenario,
    seed_multi_party_contact_scenario,
)
from net_working_platform.storage.schema import metadata, negotiations, protocol_events
from net_working_platform.storage.services import create_sql_negotiation_service
from scripts.dev.run_unified_agent_lifecycle_experiment import _jsonable, _request_openai_json

TopicDecisionProvider = Callable[[dict[str, object]], dict[str, Any]]


def run_topic_selection_networking_experiment(
    *,
    db_url: str,
    output_dir: Path,
    baseline_model: str = "gpt-4o-mini",
    reset_db: bool = False,
    scenario_kind: str = "clear",
    decision_provider: TopicDecisionProvider | None = None,
) -> dict[str, object]:
    """Run one networking turn where a portfolio client agent chooses negotiation topics."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if reset_db:
        _reset_sqlite_database(db_url)
    scenario = _seed_scenario(db_url, scenario_kind)
    context = _topic_selection_context(scenario)
    raw = decision_provider(context) if decision_provider else _request_openai_json(
        prompt=_prompt(context),
        model=baseline_model,
        json_schema=_topic_selection_schema(scenario),
    )
    execution = _execute_topic_decision(db_url, scenario, raw)
    summary = _summary(db_url, output_dir, scenario, context, raw, execution, baseline_model, reset_db, scenario_kind)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _topic_selection_context(scenario: MultiPartyContactScenario) -> dict[str, object]:
    return {
        "mode": "networking_topic_selection",
        "scenario_id": scenario.scenario_id,
        "workflow_endpoint": "open_negotiation_request",
        "actor_agent_id": scenario.client_agent_id,
        "contact_agent_id": scenario.principal_agent_id,
        "own_client_topics": list(scenario.client_summaries.values()),
        "contact_principal_topics": list(scenario.principal_summaries.values()),
        "instruction": "Choose exactly one client topic and exactly one principal topic for the negotiation request.",
    }


def _topic_selection_schema(scenario: MultiPartyContactScenario) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "actor_agent_id", "target_agent_id", "client_topic_id", "principal_topic_id", "reason"],
        "properties": {
            "action": {"type": "string", "enum": ["request_negotiation"]},
            "actor_agent_id": {"type": "string", "enum": [scenario.client_agent_id]},
            "target_agent_id": {"type": "string", "enum": [scenario.principal_agent_id]},
            "client_topic_id": {"type": "string", "enum": sorted(scenario.client_ids)},
            "principal_topic_id": {"type": "string", "enum": sorted(scenario.principal_ids)},
            "reason": {"type": "string"},
        },
    }


def _prompt(context: dict[str, object]) -> str:
    return "\n".join([
        "You are a client-side portfolio agent in networking mode.",
        "You have one existing contact. Open one negotiation request by choosing one of your client topics and one of the contact's principal topics.",
        "Do not negotiate terms yet; the endpoint is the request itself.",
        json.dumps(context, sort_keys=True),
    ])


def _execute_topic_decision(
    db_url: str, scenario: MultiPartyContactScenario, raw: dict[str, Any]
) -> dict[str, object]:
    if raw.get("action") != "request_negotiation":
        raise ValueError("topic-selection experiment only supports request_negotiation")
    actor = str(raw["actor_agent_id"])
    target = str(raw["target_agent_id"])
    client_topic_id = str(raw["client_topic_id"])
    principal_topic_id = str(raw["principal_topic_id"])
    if actor != scenario.client_agent_id or target != scenario.principal_agent_id:
        raise ValueError("decision selected an agent outside the scenario")
    if client_topic_id not in scenario.client_ids:
        raise ValueError("decision selected a client topic not represented by the actor")
    if principal_topic_id not in scenario.principal_ids:
        raise ValueError("decision selected a principal topic not represented by the contact")
    engine = create_engine(db_url)
    with engine.begin() as connection:
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: f"topic_negotiation_{client_topic_id}_{principal_topic_id}",
            now=lambda: datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc),
        )
        subject = {
            "topic_type": "client_principal_pair",
            "client_id": client_topic_id,
            "principal_id": principal_topic_id,
            "client_topic": scenario.client_summaries[client_topic_id],
            "principal_topic": scenario.principal_summaries[principal_topic_id],
            "reason": str(raw["reason"]),
        }
        negotiation = service.request_negotiation(
            from_agent_id=actor,
            to_agent_id=target,
            subject=subject,
            max_open_negotiations=5,
        )
    result = _jsonable(negotiation)
    result["subject"] = subject
    return result


def _summary(
    db_url: str,
    output_dir: Path,
    scenario: MultiPartyContactScenario,
    context: dict[str, object],
    raw: dict[str, Any],
    execution: dict[str, object],
    baseline_model: str,
    reset_db: bool,
    scenario_kind: str,
) -> dict[str, object]:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        negotiation_rows = connection.execute(select(negotiations)).all()
        event_rows = connection.execute(select(protocol_events)).all()
    subject = execution["subject"] if isinstance(execution.get("subject"), dict) else {}
    return {
        "scenario": "topic_selection_networking",
        "scenario_kind": scenario_kind,
        "scenario_id": scenario.scenario_id,
        "baseline_model": baseline_model,
        "reset_db": reset_db,
        "context": context,
        "raw_decision": raw,
        "execution": execution,
        "metrics": {
            "negotiations_requested": len(negotiation_rows),
            "open_negotiation_request_events": sum(1 for row in event_rows if row._mapping["type"] == "open_negotiation_request"),
            "selected_client_topic_id": subject.get("client_id"),
            "selected_principal_topic_id": subject.get("principal_id"),
            "exactly_one_client_topic": isinstance(subject.get("client_id"), str) and isinstance(subject.get("client_topic"), dict),
            "exactly_one_principal_topic": isinstance(subject.get("principal_id"), str) and isinstance(subject.get("principal_topic"), dict),
        },
        "outputs": {"summary": str(output_dir / "summary.json")},
    }


def _seed_scenario(db_url: str, scenario_kind: str) -> MultiPartyContactScenario:
    if scenario_kind == "clear":
        return seed_multi_party_contact_scenario(db_url)
    if scenario_kind == "ambiguous":
        return seed_ambiguous_multi_party_contact_scenario(db_url)
    raise ValueError("scenario_kind must be 'clear' or 'ambiguous'")


def _reset_sqlite_database(db_url: str) -> None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return
    database_path = Path(url.database)
    for path in [database_path, Path(f"{database_path}-wal"), Path(f"{database_path}-shm")]:
        if path.exists():
            path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one multi-party topic-selection networking turn.")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--baseline-model", default="gpt-4o-mini")
    parser.add_argument("--scenario-kind", choices=["clear", "ambiguous"], default="clear")
    parser.add_argument("--reset-db", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(run_topic_selection_networking_experiment(
        db_url=args.db_url,
        output_dir=args.output_dir,
        baseline_model=args.baseline_model,
        reset_db=args.reset_db,
        scenario_kind=args.scenario_kind,
    ), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
