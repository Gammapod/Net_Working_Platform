from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select

from net_working_platform.application.discovery_decisions import (
    build_discovery_turn_json_schema,
    execute_discovery_decision,
    parse_discovery_decision,
)
from net_working_platform.application.llm_decisions import build_turn_decision_json_schema, execute_llm_decision, parse_llm_decision
from net_working_platform.domain.model import NegotiationDecision
from net_working_platform.experiments.scenarios import seed_weak_discovery_scenario
from net_working_platform.storage.repositories import SqlNegotiationRepository
from net_working_platform.storage.schema import agent_connections, metadata, negotiations, protocol_events
from net_working_platform.storage.services import create_sql_discovery_service, create_sql_negotiation_service
from scripts.dev.openai_provider import request_openai_decision
from scripts.dev.run_weak_discovery_experiment import _request_openai_json


def run_discovery_negotiation_lifecycle_experiment(
    *,
    db_url: str,
    output_dir: Path,
    baseline_model: str = "gpt-4o-mini",
    reset_db: bool = False,
    negotiation_turns: int = 8,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if reset_db:
        _reset_sqlite_database(db_url)
    scenario = seed_weak_discovery_scenario(db_url)
    transcript: list[dict[str, object]] = []
    clients = [
        scenario.marketing_client_agent_ids[0],
        scenario.marketing_client_agent_ids[1],
        scenario.programming_client_agent_id,
    ]
    for index, client_agent_id in enumerate(clients, start=1):
        discovery = _run_discovery_turn(db_url, client_agent_id, scenario.agent_fields[client_agent_id], baseline_model)
        transcript.append({"phase": "discovery", "client_agent_id": client_agent_id, **discovery})
        target_agent_id = _target_from_discovery(discovery)
        if target_agent_id is None:
            continue
        for cycle in [1, 2]:
            negotiation_id = f"negotiation_{client_agent_id}_{target_agent_id}_{cycle}"
            request_record = _run_request_negotiation_turn(
                db_url,
                negotiation_id=negotiation_id,
                client_agent_id=client_agent_id,
                principal_agent_id=target_agent_id,
                field=scenario.agent_fields[client_agent_id],
                cycle=cycle,
                baseline_model=baseline_model,
            )
            transcript.append(request_record)
            if request_record.get("error") is not None:
                continue
            accept_record = _run_accept_negotiation_turn(db_url, negotiation_id, target_agent_id, baseline_model)
            transcript.append(accept_record)
            if accept_record.get("error") is not None or (accept_record.get("raw_decision") or {}).get("action") != "accept_negotiation":
                continue
            transcript.extend(
                _run_negotiation_turns(
                    db_url,
                    negotiation_id=negotiation_id,
                    client_agent_id=client_agent_id,
                    principal_agent_id=target_agent_id,
                    field=scenario.agent_fields[client_agent_id],
                    cycle=cycle,
                    turns=negotiation_turns,
                    baseline_model=baseline_model,
                    start_minutes=index * 100 + cycle * 20,
                )
            )
    summary = _summary(db_url, output_dir, transcript, baseline_model, reset_db)
    (output_dir / "transcript.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in transcript), encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _run_discovery_turn(db_url: str, actor_agent_id: str, field: str, baseline_model: str) -> dict[str, object]:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        service = create_sql_discovery_service(connection, now=_now)
        discoverable = service.list_discoverable_agents(actor_agent_id=actor_agent_id, field=field)
    schema = build_discovery_turn_json_schema(
        actor_agent_id=actor_agent_id,
        valid_actions=["probe_weak_connection", "request_contact"] if discoverable else ["defer"],
        discoverable_agent_ids=[str(r["agent_id"]) for r in discoverable],
        fields=[field] if discoverable else [],
    )
    prompt = "\n".join(
        [
            "You represent a client seeking work. Choose a same-field principal agent when available, not a peer client agent.",
            "Return one JSON discovery decision.",
            json.dumps({"actor_agent_id": actor_agent_id, "field": field, "discoverable_agents": discoverable}, sort_keys=True),
        ]
    )
    raw = _request_openai_json(prompt=prompt, model=baseline_model, json_schema=schema)
    execution = None
    error = None
    try:
        decision = parse_discovery_decision(raw)
        with engine.begin() as connection:
            service = create_sql_discovery_service(connection, now=_now)
            execution = _jsonable(execute_discovery_decision(decision, service))
    except Exception as exc:  # pragma: no cover
        error = {"type": type(exc).__name__, "message": str(exc)}
    return {"field": field, "discoverable_agents": discoverable, "raw_decision": raw, "execution": execution, "error": error}


def _target_from_discovery(record: dict[str, object]) -> str | None:
    raw = record.get("raw_decision")
    if isinstance(raw, dict) and raw.get("action") == "request_contact" and isinstance(raw.get("target_agent_id"), str):
        return raw["target_agent_id"]
    return None


def _run_request_negotiation_turn(
    db_url: str,
    *,
    negotiation_id: str,
    client_agent_id: str,
    principal_agent_id: str,
    field: str,
    cycle: int,
    baseline_model: str,
) -> dict[str, object]:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "actor_agent_id", "target_agent_id", "field", "reason"],
        "properties": {
            "action": {"type": "string", "enum": ["request_negotiation"]},
            "actor_agent_id": {"type": "string", "enum": [client_agent_id]},
            "target_agent_id": {"type": "string", "enum": [principal_agent_id]},
            "field": {"type": "string", "enum": [field]},
            "reason": {"type": "string"},
        },
    }
    prompt = "\n".join([
        "You now have an active directional contact to a same-field principal agent.",
        "Request a negotiation if you want to explore an opportunity. Return one JSON object.",
        json.dumps({"actor_agent_id": client_agent_id, "target_agent_id": principal_agent_id, "field": field, "cycle": cycle}, sort_keys=True),
    ])
    raw = _request_openai_json(prompt=prompt, model=baseline_model, json_schema=schema)
    engine = create_engine(db_url)
    error = None
    execution = None
    try:
        with engine.begin() as connection:
            service = create_sql_negotiation_service(connection, new_id=lambda: negotiation_id, now=_now)
            result = service.request_negotiation(
                from_agent_id=client_agent_id,
                to_agent_id=principal_agent_id,
                subject={"field": field, "cycle": cycle, "need": "job_opportunity", "reason": raw.get("reason", "")},
                max_open_negotiations=2,
            )
            execution = _jsonable(result)
    except Exception as exc:  # pragma: no cover
        error = {"type": type(exc).__name__, "message": str(exc)}
    return {"phase": "request_negotiation", "cycle": cycle, "actor_agent_id": client_agent_id, "target_agent_id": principal_agent_id, "negotiation_id": negotiation_id, "raw_decision": raw, "execution": execution, "error": error}


def _run_accept_negotiation_turn(db_url: str, negotiation_id: str, principal_agent_id: str, baseline_model: str) -> dict[str, object]:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        service = create_sql_negotiation_service(connection, new_id=lambda: "unused", now=_now)
        context = service.get_agent_decision_context(agent_id=principal_agent_id, recent_event_limit=20, max_active_negotiations=2)
    schema = build_turn_decision_json_schema(valid_actions=["accept_negotiation", "reject_negotiation"], actor_agent_id=principal_agent_id, negotiation_id=negotiation_id, available_fact_fields=[])
    prompt = "\n".join([
        "You are a principal-side agent receiving a requested negotiation from a same-field client agent.",
        "Accept if the request is field-relevant; reject only if clearly not relevant.",
        json.dumps({"actor_agent_id": principal_agent_id, "negotiation_id": negotiation_id, "decision_context": context}, sort_keys=True),
    ])
    raw = None
    execution = None
    error = None
    try:
        decision = request_openai_decision(prompt=prompt, model=baseline_model, json_schema=schema)
        raw = {"action": decision.action.value, **decision.payload}
        with engine.begin() as connection:
            service = create_sql_negotiation_service(connection, new_id=lambda: "unused", now=_now)
            execution = _jsonable(execute_llm_decision(parse_llm_decision(raw), service))
    except Exception as exc:  # pragma: no cover
        error = {"type": type(exc).__name__, "message": str(exc)}
    return {"phase": "accept_negotiation", "actor_agent_id": principal_agent_id, "negotiation_id": negotiation_id, "raw_decision": raw, "execution": execution, "error": error}


def _run_negotiation_turns(
    db_url: str,
    *,
    negotiation_id: str,
    client_agent_id: str,
    principal_agent_id: str,
    field: str,
    cycle: int,
    turns: int,
    baseline_model: str,
    start_minutes: int,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    actors = [client_agent_id, principal_agent_id]
    for turn in range(1, turns + 1):
        actor = actors[(turn - 1) % 2]
        engine = create_engine(db_url)
        with engine.begin() as connection:
            service = create_sql_negotiation_service(connection, new_id=lambda: "unused", now=lambda: _now_offset(start_minutes + turn))
            context = service.get_agent_decision_context(agent_id=actor, recent_event_limit=30, max_active_negotiations=10)
        valid_actions = context["valid_next_actions_by_negotiation"].get(negotiation_id, [])
        if not valid_actions:
            records.append({"phase": "negotiation", "cycle": cycle, "turn": turn, "actor_agent_id": actor, "negotiation_id": negotiation_id, "skipped": True})
            continue
        schema = build_turn_decision_json_schema(valid_actions=valid_actions, actor_agent_id=actor, negotiation_id=negotiation_id, available_fact_fields=[])
        prompt = _negotiation_prompt(actor, negotiation_id, field, cycle, context)
        before = _event_count(db_url)
        raw = None
        execution = None
        error = None
        try:
            decision = request_openai_decision(prompt=prompt, model=baseline_model, json_schema=schema)
            raw = {"action": decision.action.value, **decision.payload}
            parsed = parse_llm_decision(raw)
            with engine.begin() as connection:
                service = create_sql_negotiation_service(connection, new_id=lambda: "unused", now=lambda: _now_offset(start_minutes + turn))
                execution = _jsonable(execute_llm_decision(parsed, service))
        except Exception as exc:  # pragma: no cover
            error = {"type": type(exc).__name__, "message": str(exc)}
        records.append({
            "phase": "negotiation",
            "cycle": cycle,
            "turn": turn,
            "actor_agent_id": actor,
            "negotiation_id": negotiation_id,
            "valid_actions": valid_actions,
            "raw_decision": raw,
            "execution": execution,
            "error": error,
            "event_delta_count": _event_count(db_url) - before,
            "skipped": False,
        })
    return records


def _negotiation_prompt(actor: str, negotiation_id: str, field: str, cycle: int, context: dict[str, object]) -> str:
    return "\n".join([
        "You are negotiating after weak discovery formed an active connection.",
        "Use valid actions only. Move toward a terminal outcome: matched if the field fits, closed if it does not.",
        "If a proposal is pending, accept or close unless a short clarification message is essential.",
        json.dumps({"actor_agent_id": actor, "negotiation_id": negotiation_id, "field": field, "cycle": cycle, "decision_context": context}, sort_keys=True),
    ])


def _summary(db_url: str, output_dir: Path, transcript: list[dict[str, object]], baseline_model: str, reset_db: bool) -> dict[str, object]:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        negotiation_rows = connection.execute(select(negotiations)).all()
        connection_rows = connection.execute(select(agent_connections)).all()
        event_rows = connection.execute(select(protocol_events)).all()
    states = _counts(row._mapping["state"] for row in negotiation_rows)
    events = _counts(row._mapping["type"] for row in event_rows)
    actions = _counts((r.get("raw_decision") or {}).get("action") for r in transcript if isinstance(r.get("raw_decision"), dict))
    summary = {
        "scenario": "discovery_negotiation_lifecycle",
        "baseline_model": baseline_model,
        "reset_db": reset_db,
        "metrics": {
            "connections_created": len(connection_rows),
            "negotiations_created": len(negotiation_rows),
            "negotiation_states": states,
            "events_by_type": events,
            "decisions_by_action": actions,
            "errors": sum(1 for r in transcript if r.get("error")),
            "skipped_turns": sum(1 for r in transcript if r.get("skipped")),
        },
        "outputs": {"summary": str(output_dir / "summary.json"), "transcript": str(output_dir / "transcript.jsonl")},
    }
    return summary


def _event_count(db_url: str) -> int:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        return len(connection.execute(select(protocol_events)).all())


def _counts(values: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _jsonable(value: object) -> object:
    if hasattr(value, "from_agent_id") and hasattr(value, "to_agent_id") and hasattr(value, "state"):
        return {"from_agent_id": value.from_agent_id, "to_agent_id": value.to_agent_id, "state": value.state.value}
    if hasattr(value, "id") and hasattr(value, "state"):
        return {"id": value.id, "state": value.state.value}
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return value


def _now() -> datetime:
    return datetime(2026, 1, 11, 12, 0, tzinfo=timezone.utc)


def _now_offset(minutes: int) -> datetime:
    return _now() + timedelta(minutes=minutes)


def _reset_sqlite_database(db_url: str) -> None:
    from sqlalchemy.engine import make_url

    url = make_url(db_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return
    database_path = Path(url.database)
    for path in [database_path, Path(f"{database_path}-wal"), Path(f"{database_path}-shm")]:
        if path.exists():
            path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run discovery-to-negotiation lifecycle experiment.")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--baseline-model", default="gpt-4o-mini")
    parser.add_argument("--negotiation-turns", type=int, default=8)
    parser.add_argument("--reset-db", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(run_discovery_negotiation_lifecycle_experiment(db_url=args.db_url, output_dir=args.output_dir, baseline_model=args.baseline_model, reset_db=args.reset_db, negotiation_turns=args.negotiation_turns), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
