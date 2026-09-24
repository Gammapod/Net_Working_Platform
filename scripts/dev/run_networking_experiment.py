from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url

from net_working_platform.application.graph_mermaid import render_graph_snapshot_mermaid
from net_working_platform.experiments.artifacts import graph_delta, graph_snapshot_for_db, timeline_record_from_transcript_record, write_jsonl
from net_working_platform.experiments.prompts import build_representative_decision_prompt_package
from net_working_platform.experiments.scenarios import seed_viewer_showcase_scenario
from net_working_platform.storage.repositories import SqlNegotiationRepository
from net_working_platform.storage.schema import agent_connections, metadata, negotiations, protocol_events
from net_working_platform.storage.services import create_sql_discovery_service, create_sql_negotiation_service
from scripts.dev.run_unified_agent_lifecycle_experiment import (
    MAX_ACTIVE_NEGOTIATIONS_PER_AGENT,
    MAX_CONTACTS_PER_AGENT,
    UnifiedScenario,
    _jsonable,
    _request_openai_json,
    seed_unified_lifecycle_scenario,
)

NetworkingDecisionProvider = Callable[[dict[str, object]], dict[str, Any]]


def run_networking_experiment(
    *,
    db_url: str,
    output_dir: Path,
    turns: int = 30,
    baseline_model: str = "gpt-4o-mini",
    reset_db: bool = False,
    contact_limit: int = MAX_CONTACTS_PER_AGENT,
    negotiation_limit: int = MAX_ACTIVE_NEGOTIATIONS_PER_AGENT,
    decision_provider: NetworkingDecisionProvider | None = None,
    scenario_name: str = "unified-lifecycle",
) -> dict[str, object]:
    """Run a networking-only market experiment.

    Networking endpoints are negotiation requests. This runner intentionally does
    not continue into negotiation responses/messages/proposals; those belong to
    negotiation experiments.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    if reset_db:
        _reset_sqlite_database(db_url)
    scenario = _seed_networking_scenario(db_url, scenario_name)
    initial_snapshot = graph_snapshot_for_db(db_url, generated_at=_now(0))
    transcript: list[dict[str, object]] = []
    schedule = list(scenario.agent_fields)
    for turn in range(1, turns + 1):
        actor_agent_id = schedule[(turn - 1) % len(schedule)]
        before_snapshot = graph_snapshot_for_db(db_url, generated_at=_now(turn))
        context = _networking_context(db_url, scenario, actor_agent_id, contact_limit, negotiation_limit)
        if context["workflow_complete"]:
            after_snapshot = graph_snapshot_for_db(db_url, generated_at=_now(turn))
            transcript.append({"turn": turn, "actor_agent_id": actor_agent_id, "context": context, "raw_decision": None, "execution": None, "error": None, "skipped": True, "graph_delta": graph_delta(before_snapshot, after_snapshot)})
            continue
        raw = None
        execution = None
        error = None
        try:
            raw = decision_provider(context) if decision_provider else _request_openai_json(
                prompt=_prompt(context),
                model=baseline_model,
                json_schema=_networking_schema(context),
            )
            execution = _execute_networking_decision(db_url, scenario, raw, negotiation_limit, now=_now(turn))
        except Exception as exc:  # pragma: no cover - live diagnostics
            error = {"type": type(exc).__name__, "message": str(exc)}
        after_snapshot = graph_snapshot_for_db(db_url, generated_at=_now(turn))
        transcript.append({"turn": turn, "actor_agent_id": actor_agent_id, "context": context, "raw_decision": raw, "execution": execution, "error": error, "skipped": False, "graph_delta": graph_delta(before_snapshot, after_snapshot)})

    final_snapshot = graph_snapshot_for_db(db_url, generated_at=_now(turns + 1))
    summary = _summary(db_url, output_dir, scenario, transcript, baseline_model, reset_db, contact_limit, negotiation_limit, scenario_name)
    (output_dir / "transcript.jsonl").write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in transcript), encoding="utf-8")
    write_jsonl(output_dir / "graph_events.jsonl", [timeline_record_from_transcript_record(record) for record in transcript])
    _write_graph_artifacts(output_dir, initial_snapshot, final_snapshot)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _seed_networking_scenario(db_url: str, scenario_name: str) -> object:
    if scenario_name == "unified-lifecycle":
        return seed_unified_lifecycle_scenario(db_url)
    if scenario_name == "viewer-showcase-llm":
        return seed_viewer_showcase_scenario(db_url)
    raise ValueError(f"unsupported networking scenario: {scenario_name}")


def _networking_context(
    db_url: str,
    scenario: UnifiedScenario,
    actor_agent_id: str,
    contact_limit: int,
    negotiation_limit: int,
) -> dict[str, object]:
    engine = create_engine(db_url)
    field = scenario.agent_fields[actor_agent_id]
    with engine.begin() as connection:
        discovery = create_sql_discovery_service(connection, now=lambda: _now(0))
        contacts = _contacts_from(connection, actor_agent_id)
        active_negotiations = SqlNegotiationRepository(connection).list_active_for_agent(actor_agent_id)
        outbound_negotiations = connection.execute(select(negotiations).where(negotiations.c.from_agent_id == actor_agent_id)).all()
        discoverable = discovery.list_discoverable_agents(actor_agent_id=actor_agent_id, field=field)
    contact_targets = {str(contact["to_agent_id"]) for contact in contacts}
    return {
        "actor_agent_id": actor_agent_id,
        "field": field,
        "represented_type": scenario.represented_types[actor_agent_id],
        "represented_portfolio": list(getattr(scenario, "represented_portfolios", {}).get(actor_agent_id, [])),
        "strategy_priority": getattr(scenario, "strategy_priorities", {}).get(actor_agent_id, {}),
        "workflow_complete": len(outbound_negotiations) > 0,
        "contact_limit": contact_limit,
        "contacts": contacts,
        "contact_slots_remaining": max(contact_limit - len(contacts), 0),
        "discoverable_agents": [record for record in discoverable if str(record["agent_id"]) not in contact_targets],
        "negotiation_limit": negotiation_limit,
        "active_negotiation_count": len(active_negotiations),
        "negotiation_slots_remaining": max(negotiation_limit - len(active_negotiations), 0),
    }


def _valid_networking_actions(context: dict[str, object]) -> list[str]:
    if context["workflow_complete"]:
        return ["defer"]
    contacts = context.get("contacts", [])
    if isinstance(contacts, list) and contacts and int(context["negotiation_slots_remaining"]) > 0:
        return ["request_negotiation"]
    discoverable = context.get("discoverable_agents", [])
    if isinstance(discoverable, list) and discoverable and int(context["contact_slots_remaining"]) > 0:
        return ["probe_weak_connection", "request_contact"]
    return ["defer"]


def _networking_schema(context: dict[str, object]) -> dict[str, object]:
    actions = _valid_networking_actions(context)
    target_values: list[str]
    if "request_negotiation" in actions:
        target_values = [str(record["to_agent_id"]) for record in context.get("contacts", []) if isinstance(record, dict)]
    elif any(action in actions for action in ["probe_weak_connection", "request_contact"]):
        target_values = [str(record["agent_id"]) for record in context.get("discoverable_agents", []) if isinstance(record, dict)]
    else:
        target_values = [""]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "actor_agent_id", "target_agent_id", "field", "reason"],
        "properties": {
            "action": {"type": "string", "enum": actions},
            "actor_agent_id": {"type": "string", "enum": [str(context["actor_agent_id"])]},
            "target_agent_id": {"type": "string", "enum": sorted(target_values) or [""]},
            "field": {"type": "string", "enum": [str(context["field"])]},
            "reason": {"type": "string"},
        },
    }


def _prompt(context: dict[str, object]) -> str:
    package = build_representative_decision_prompt_package(
        decision_context=context,
        represented_type=str(context["represented_type"]),
        represented_portfolio=context.get("represented_portfolio") if isinstance(context.get("represented_portfolio"), list) else None,
        strategy_priority=context.get("strategy_priority") if isinstance(context.get("strategy_priority"), dict) else None,
    )
    return str(package["prompt"])


def _execute_networking_decision(
    db_url: str,
    scenario: UnifiedScenario,
    raw: dict[str, Any],
    negotiation_limit: int,
    *,
    now: datetime,
) -> dict[str, object]:
    action = raw.get("action")
    actor = str(raw["actor_agent_id"])
    engine = create_engine(db_url)
    if action == "defer":
        return {"executed": False, "action": "defer", "reason": str(raw.get("reason", ""))}
    if action == "probe_weak_connection":
        with engine.begin() as connection:
            service = create_sql_discovery_service(connection, now=lambda: now)
            return _jsonable(service.probe_weak_connection(actor_agent_id=actor, target_agent_id=str(raw["target_agent_id"]), field=str(raw["field"]), criteria={"role_field": raw["field"]}))
    if action == "request_contact":
        with engine.begin() as connection:
            service = create_sql_discovery_service(connection, now=lambda: now)
            return _jsonable(service.request_contact(actor_agent_id=actor, target_agent_id=str(raw["target_agent_id"]), field=str(raw["field"]), reason=str(raw["reason"])))
    if action == "request_negotiation":
        target = str(raw["target_agent_id"])
        negotiation_id = f"networking_negotiation_{actor}_{target}_{int(now.timestamp())}"
        with engine.begin() as connection:
            service = create_sql_negotiation_service(connection, new_id=lambda: negotiation_id, now=lambda: now)
            return _jsonable(service.request_negotiation(
                from_agent_id=actor,
                to_agent_id=target,
                subject={"field": scenario.agent_fields[actor], "reason": str(raw["reason"]), "need": "job_opportunity"},
                max_open_negotiations=negotiation_limit,
            ))
    raise ValueError(f"unsupported networking action: {action}")


def _contacts_from(connection: object, actor_agent_id: str) -> list[dict[str, object]]:
    rows = connection.execute(select(agent_connections).where(agent_connections.c.from_agent_id == actor_agent_id)).all()
    return [_jsonable(dict(row._mapping)) for row in rows]


def _write_graph_artifacts(output_dir: Path, initial_snapshot: dict[str, object], final_snapshot: dict[str, object]) -> None:
    (output_dir / "initial_graph.json").write_text(json.dumps(initial_snapshot, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "final_graph.json").write_text(json.dumps(final_snapshot, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "initial_graph.mmd").write_text(render_graph_snapshot_mermaid(initial_snapshot), encoding="utf-8")
    (output_dir / "final_graph.mmd").write_text(render_graph_snapshot_mermaid(final_snapshot), encoding="utf-8")


def _summary(
    db_url: str,
    output_dir: Path,
    scenario: UnifiedScenario,
    transcript: list[dict[str, object]],
    baseline_model: str,
    reset_db: bool,
    contact_limit: int,
    negotiation_limit: int,
    scenario_name: str,
) -> dict[str, object]:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        contact_rows = connection.execute(select(agent_connections)).all()
        negotiation_rows = connection.execute(select(negotiations)).all()
        event_rows = connection.execute(select(protocol_events)).all()
    completed_agents = {row._mapping["from_agent_id"] for row in negotiation_rows}
    return {
        "scenario": scenario_name,
        "runner": "networking",
        "baseline_model": baseline_model,
        "reset_db": reset_db,
        "turns": len(transcript),
        "bandwidth_limits": {"contact_limit": contact_limit, "negotiation_limit": negotiation_limit},
        "metrics": {
            "contacts_created": len(contact_rows),
            "negotiations_requested": len(negotiation_rows),
            "workflows_completed": len(completed_agents),
            "workflow_completion_rate": len(completed_agents) / max(len(scenario.agent_fields), 1),
            "events_by_type": _counts(row._mapping["type"] for row in event_rows),
            "decisions_by_action": _counts((record.get("raw_decision") or {}).get("action") for record in transcript if isinstance(record.get("raw_decision"), dict)),
            "errors": sum(1 for record in transcript if record.get("error") is not None),
            "skipped_completed_workflows": sum(1 for record in transcript if record.get("skipped")),
        },
        "outputs": {"summary": str(output_dir / "summary.json"), "transcript": str(output_dir / "transcript.jsonl")},
    }


def _counts(values: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _now(turn: int) -> datetime:
    return datetime(2026, 1, 13, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=turn)


def _reset_sqlite_database(db_url: str) -> None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return
    database_path = Path(url.database)
    for path in [database_path, Path(f"{database_path}-wal"), Path(f"{database_path}-shm")]:
        if path.exists():
            path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run networking-only experiment ending at negotiation requests.")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--turns", type=int, default=30)
    parser.add_argument("--baseline-model", default="gpt-4o-mini")
    parser.add_argument("--contact-limit", type=int, default=MAX_CONTACTS_PER_AGENT)
    parser.add_argument("--negotiation-limit", type=int, default=MAX_ACTIVE_NEGOTIATIONS_PER_AGENT)
    parser.add_argument("--scenario", default="unified-lifecycle", choices=["unified-lifecycle", "viewer-showcase-llm"])
    parser.add_argument("--reset-db", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(run_networking_experiment(
        db_url=args.db_url,
        output_dir=args.output_dir,
        turns=args.turns,
        baseline_model=args.baseline_model,
        reset_db=args.reset_db,
            contact_limit=args.contact_limit,
            negotiation_limit=args.negotiation_limit,
            scenario_name=args.scenario,
        ), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
