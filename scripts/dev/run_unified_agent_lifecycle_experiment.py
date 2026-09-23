from __future__ import annotations

import argparse
import json
import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url

from net_working_platform.application.llm_decisions import execute_llm_decision, parse_llm_decision
from net_working_platform.domain.model import (
    AgentConnection,
    AgentConnectionState,
    NegotiationDecision,
    Node,
    NodeType,
    RepresentationEdge,
    RepresentationState,
    WeakDiscoveryEdge,
    WeakDiscoveryState,
)
from net_working_platform.storage.repositories import (
    SqlAgentConnectionRepository,
    SqlNegotiationRepository,
    SqlNodeRepository,
    SqlProtocolEventRepository,
    SqlRepresentationEdgeRepository,
    SqlWeakDiscoveryEdgeRepository,
)
from net_working_platform.storage.schema import agent_connections, metadata, negotiations, protocol_events
from net_working_platform.storage.services import create_sql_discovery_service, create_sql_negotiation_service
from scripts.dev.experiment_artifacts import graph_delta, graph_snapshot_for_db, timeline_record_from_transcript_record, write_jsonl

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
MAX_CONTACTS_PER_AGENT = 3
MAX_ACTIVE_NEGOTIATIONS_PER_AGENT = 2


@dataclass(frozen=True)
class UnifiedScenario:
    db_url: str
    agent_fields: dict[str, str]
    represented_types: dict[str, str]


DecisionProvider = Callable[[dict[str, object]], dict[str, Any]]


def run_unified_agent_lifecycle_experiment(
    *,
    db_url: str,
    output_dir: Path,
    turns: int = 30,
    baseline_model: str = "gpt-4o-mini",
    reset_db: bool = False,
    decision_provider: DecisionProvider | None = None,
    contact_limit: int = MAX_CONTACTS_PER_AGENT,
    negotiation_limit: int = MAX_ACTIVE_NEGOTIATIONS_PER_AGENT,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if reset_db:
        _reset_sqlite_database(db_url)
    scenario = seed_unified_lifecycle_scenario(db_url)
    transcript = []
    schedule = list(scenario.agent_fields)
    for turn in range(1, turns + 1):
        actor_agent_id = schedule[(turn - 1) % len(schedule)]
        before_snapshot = _graph_snapshot(db_url, turn=turn, after=False)
        record = _execute_turn(
            db_url=db_url,
            scenario=scenario,
            actor_agent_id=actor_agent_id,
            turn=turn,
            baseline_model=baseline_model,
            decision_provider=decision_provider,
            contact_limit=contact_limit,
            negotiation_limit=negotiation_limit,
        )
        after_snapshot = _graph_snapshot(db_url, turn=turn, after=True)
        record["graph_delta"] = graph_delta(before_snapshot, after_snapshot)
        transcript.append(record)
    summary = _summary(db_url, output_dir, scenario, transcript, baseline_model, reset_db, contact_limit, negotiation_limit)
    (output_dir / "transcript.jsonl").write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in transcript), encoding="utf-8")
    write_jsonl(output_dir / "graph_events.jsonl", [_timeline_record_from_transcript_record(r) for r in transcript])
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def seed_unified_lifecycle_scenario(db_url: str) -> UnifiedScenario:
    engine = create_engine(db_url)
    metadata.create_all(engine)
    agent_specs = {
        "marketing_client_agent_1": ("marketing", "client"),
        "marketing_client_agent_2": ("marketing", "client"),
        "marketing_client_agent_3": ("marketing", "client"),
        "programming_client_agent_1": ("programming", "client"),
        "programming_client_agent_2": ("programming", "client"),
        "marketing_principal_agent_1": ("marketing", "principal"),
        "marketing_principal_agent_2": ("marketing", "principal"),
        "programming_principal_agent_1": ("programming", "principal"),
        "programming_principal_agent_2": ("programming", "principal"),
        "marketing_connector_agent": ("marketing", "principal"),
    }
    with engine.begin() as connection:
        nodes = SqlNodeRepository(connection)
        reps = SqlRepresentationEdgeRepository(connection)
        weak = SqlWeakDiscoveryEdgeRepository(connection)
        for agent_id, (field, represented_type) in agent_specs.items():
            nodes.add(Node(agent_id, NodeType.AGENT), display_name=agent_id.replace("_", " ").title())
            represented_id = agent_id.replace("_agent", "")
            node_type = NodeType.CLIENT if represented_type == "client" else NodeType.PRINCIPAL
            nodes.add(Node(represented_id, node_type), display_name=represented_id.replace("_", " ").title())
            reps.add(RepresentationEdge(agent_id, represented_id, node_type, RepresentationState.ACTIVE))
        for from_agent_id, (from_field, _) in agent_specs.items():
            for to_agent_id, (to_field, to_type) in agent_specs.items():
                if from_agent_id == to_agent_id or from_field != to_field:
                    continue
                weak.add(
                    WeakDiscoveryEdge(
                        from_agent_id=from_agent_id,
                        to_agent_id=to_agent_id,
                        field=from_field,
                        state=WeakDiscoveryState.AVAILABLE,
                        rationale={
                            "reason": "same_field",
                            "field": from_field,
                            "target_represented_type": to_type,
                            "target_represented_id": to_agent_id.replace("_agent", ""),
                        },
                    )
                )
    return UnifiedScenario(
        db_url=db_url,
        agent_fields={agent_id: spec[0] for agent_id, spec in agent_specs.items()},
        represented_types={agent_id: spec[1] for agent_id, spec in agent_specs.items()},
    )


def _execute_turn(
    *,
    db_url: str,
    scenario: UnifiedScenario,
    actor_agent_id: str,
    turn: int,
    baseline_model: str,
    decision_provider: DecisionProvider | None,
    contact_limit: int,
    negotiation_limit: int,
) -> dict[str, object]:
    context = _combined_context(db_url, scenario, actor_agent_id, contact_limit, negotiation_limit)
    valid_actions = _valid_unified_actions(context)
    if not valid_actions:
        valid_actions = ["defer"]
    schema = _unified_turn_schema(context, valid_actions)
    prompt = _prompt(context)
    raw = None
    execution = None
    error = None
    try:
        raw = decision_provider(context) if decision_provider is not None else _request_openai_json(prompt=prompt, model=baseline_model, json_schema=schema)
        execution = _execute_raw_decision(db_url, scenario, raw, now=_now(turn), negotiation_limit=negotiation_limit)
    except Exception as exc:  # pragma: no cover
        error = {"type": type(exc).__name__, "message": str(exc)}
    return {
        "turn": turn,
        "actor_agent_id": actor_agent_id,
        "context": context,
        "valid_actions": valid_actions,
        "raw_decision": raw,
        "execution": execution,
        "error": error,
    }


def _combined_context(
    db_url: str,
    scenario: UnifiedScenario,
    actor_agent_id: str,
    contact_limit: int,
    negotiation_limit: int,
) -> dict[str, object]:
    engine = create_engine(db_url)
    field = scenario.agent_fields[actor_agent_id]
    represented_type = scenario.represented_types[actor_agent_id]
    with engine.begin() as connection:
        discovery = create_sql_discovery_service(connection, now=lambda: _now(0))
        negotiation_service = create_sql_negotiation_service(connection, new_id=lambda: "unused", now=lambda: _now(0))
        contacts = _contacts_from(connection, actor_agent_id)
        active_negotiations = SqlNegotiationRepository(connection).list_active_for_agent(actor_agent_id)
        decision_context = negotiation_service.get_agent_decision_context(
            agent_id=actor_agent_id,
            recent_event_limit=20,
            max_active_negotiations=negotiation_limit,
        )
        discoverable = discovery.list_discoverable_agents(actor_agent_id=actor_agent_id, field=field)
    open_contact_targets = {str(contact["to_agent_id"]) for contact in contacts}
    focus_negotiation_id = _select_focus_negotiation(decision_context)
    return {
        "actor_agent_id": actor_agent_id,
        "field": field,
        "represented_type": represented_type,
        "contact_limit": contact_limit,
        "contacts": contacts,
        "contact_slots_remaining": max(contact_limit - len(contacts), 0),
        "discoverable_agents": [record for record in discoverable if str(record["agent_id"]) not in open_contact_targets],
        "negotiation_limit": negotiation_limit,
        "active_negotiation_count": len(active_negotiations),
        "negotiation_slots_remaining": max(negotiation_limit - len(active_negotiations), 0),
        "focus_negotiation_id": focus_negotiation_id or "",
        "decision_context": decision_context,
    }


def _valid_unified_actions(context: dict[str, object]) -> list[str]:
    actions: list[str] = []
    focus_negotiation_id = str(context.get("focus_negotiation_id", ""))
    if focus_negotiation_id:
        decision_context = context.get("decision_context", {})
        if isinstance(decision_context, dict):
            by_negotiation = decision_context.get("valid_next_actions_by_negotiation", {})
            if isinstance(by_negotiation, dict):
                valid = by_negotiation.get(focus_negotiation_id, [])
                if isinstance(valid, list):
                    return [str(action) for action in valid] or ["defer"]

    contacts = context.get("contacts", [])
    if isinstance(contacts, list) and contacts and int(context["negotiation_slots_remaining"]) > 0:
        actions.append("request_negotiation")
    else:
        discoverable = context.get("discoverable_agents", [])
        if isinstance(discoverable, list) and discoverable and int(context["contact_slots_remaining"]) > 0:
            actions.extend(["probe_weak_connection", "request_contact"])
    if not actions:
        actions.append("defer")
    return actions


def _unified_turn_schema(context: dict[str, object], valid_actions: list[str]) -> dict[str, object]:
    target_values: set[str] = set()
    if any(action in valid_actions for action in ["probe_weak_connection", "request_contact"]):
        target_values.update(str(record["agent_id"]) for record in context.get("discoverable_agents", []) if isinstance(record, dict))
    if "request_negotiation" in valid_actions:
        target_values.update(str(record["to_agent_id"]) for record in context.get("contacts", []) if isinstance(record, dict))
    targets = sorted(target_values) or [""]
    focus_negotiation_id = str(context.get("focus_negotiation_id", ""))
    negotiation_ids = [focus_negotiation_id] if focus_negotiation_id else [""]
    field = str(context["field"])
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "actor_agent_id", "target_agent_id", "negotiation_id", "field", "reason", "body", "proposal"],
        "properties": {
            "action": {"type": "string", "enum": valid_actions},
            "actor_agent_id": {"type": "string", "enum": [str(context["actor_agent_id"])]},
            "target_agent_id": {"type": "string", "enum": targets},
            "negotiation_id": {"type": "string", "enum": negotiation_ids},
            "field": {"type": "string", "enum": [field]},
            "reason": {"type": "string"},
            "body": {"type": "string"},
            "proposal": {
                "type": "object",
                "additionalProperties": False,
                "required": ["summary", "details"],
                "properties": {"summary": {"type": "string"}, "details": {"type": "string"}},
            },
        },
    }


def _select_focus_negotiation(decision_context: dict[str, object]) -> str | None:
    by_negotiation = decision_context.get("valid_next_actions_by_negotiation", {})
    if not isinstance(by_negotiation, dict):
        return None
    priorities = [
        {"accept_negotiation", "reject_negotiation"},
        {"accept_match", "close_negotiation"},
        {"propose_match", "send_message", "close_negotiation"},
    ]
    for priority in priorities:
        for negotiation_id, actions in sorted(by_negotiation.items()):
            if isinstance(actions, list) and priority.intersection({str(action) for action in actions}):
                return str(negotiation_id)
    return None


def _prompt(context: dict[str, object]) -> str:
    return "\n".join(
        [
            "You are an autonomous representative agent on Net Working Platform.",
            "Choose exactly one valid action. Prefer useful same-field principals for client agents. Respect contact and negotiation limits.",
            "If you already have a relevant contact and negotiation capacity, prefer request_negotiation over adding more contacts.",
            "If an inbound negotiation is requested and relevant, accept it. If an open negotiation fits, move toward proposal or terminal outcome.",
            json.dumps(context, sort_keys=True),
        ]
    )


def _execute_raw_decision(
    db_url: str,
    scenario: UnifiedScenario,
    raw: dict[str, Any],
    *,
    now: datetime,
    negotiation_limit: int,
) -> dict[str, object]:
    action = raw.get("action")
    actor = str(raw.get("actor_agent_id"))
    engine = create_engine(db_url)
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
        negotiation_id = f"negotiation_{actor}_{target}_{int(now.timestamp())}"
        with engine.begin() as connection:
            service = create_sql_negotiation_service(connection, new_id=lambda: negotiation_id, now=lambda: now)
            return _jsonable(
                service.request_negotiation(
                    from_agent_id=actor,
                    to_agent_id=target,
                    subject={"field": scenario.agent_fields[actor], "reason": str(raw["reason"]), "need": "job_opportunity"},
                    max_open_negotiations=negotiation_limit,
                )
            )
    if action == "defer":
        return {"executed": False, "action": "defer", "reason": str(raw.get("reason", ""))}
    llm_raw = _to_llm_decision_raw(raw)
    with engine.begin() as connection:
        service = create_sql_negotiation_service(connection, new_id=lambda: "unused", now=lambda: now)
        return _jsonable(execute_llm_decision(parse_llm_decision(llm_raw), service))


def _to_llm_decision_raw(raw: dict[str, Any]) -> dict[str, object]:
    action = raw["action"]
    base = {"action": action, "actor_agent_id": raw["actor_agent_id"], "negotiation_id": raw["negotiation_id"]}
    if action == "send_message":
        return {**base, "body": raw["body"]}
    if action == "propose_match":
        return {**base, "proposal": raw["proposal"]}
    if action in {"reject_negotiation", "close_negotiation"}:
        return {**base, "reason": raw["reason"]}
    return base


def _contacts_from(connection: object, actor_agent_id: str) -> list[dict[str, object]]:
    rows = connection.execute(select(agent_connections).where(agent_connections.c.from_agent_id == actor_agent_id, agent_connections.c.state == AgentConnectionState.ACTIVE.value)).all()
    return [_jsonable(dict(row._mapping)) for row in rows]


def _summary(
    db_url: str,
    output_dir: Path,
    scenario: UnifiedScenario,
    transcript: list[dict[str, object]],
    baseline_model: str,
    reset_db: bool,
    contact_limit: int,
    negotiation_limit: int,
) -> dict[str, object]:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        connection_rows = connection.execute(select(agent_connections)).all()
        negotiation_rows = connection.execute(select(negotiations)).all()
        event_rows = connection.execute(select(protocol_events)).all()
    return {
        "scenario": "unified_agent_lifecycle",
        "baseline_model": baseline_model,
        "reset_db": reset_db,
        "turns": len(transcript),
        "bandwidth_limits": {
            "contact_limit": contact_limit,
            "negotiation_limit": negotiation_limit,
            "message_quota": 3,
        },
        "metrics": {
            "contacts_created": len(connection_rows),
            "negotiations_created": len(negotiation_rows),
            "negotiation_states": _counts(row._mapping["state"] for row in negotiation_rows),
            "events_by_type": _counts(row._mapping["type"] for row in event_rows),
            "decisions_by_action": _counts((record.get("raw_decision") or {}).get("action") for record in transcript if isinstance(record.get("raw_decision"), dict)),
            "errors": sum(1 for record in transcript if record.get("error") is not None),
        },
        "outputs": {"summary": str(output_dir / "summary.json"), "transcript": str(output_dir / "transcript.jsonl"), "graph_events": str(output_dir / "graph_events.jsonl")},
    }


def _graph_snapshot(db_url: str, *, turn: int, after: bool) -> dict[str, object]:
    timestamp = _now(turn) + timedelta(seconds=1 if after else 0)
    return graph_snapshot_for_db(db_url, generated_at=timestamp)


def _timeline_record_from_transcript_record(record: dict[str, object]) -> dict[str, object]:
    return timeline_record_from_transcript_record(record, validation={"valid": record.get("error") is None})


def _request_openai_json(*, prompt: str, model: str, json_schema: dict[str, object]) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required")
    payload = {"model": model, "input": prompt, "max_output_tokens": 500, "text": {"format": {"type": "json_schema", "name": "unified_decision", "schema": json_schema, "strict": True}}}
    request = urllib.request.Request(OPENAI_RESPONSES_URL, data=json.dumps(payload).encode("utf-8"), headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    text = "".join(content.get("text", "") for item in response_payload.get("output", []) for content in item.get("content", []) if content.get("type") == "output_text")
    return json.loads(text)


def _counts(values: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _jsonable(value: object) -> object:
    if value is None:
        return None
    if hasattr(value, "from_agent_id") and hasattr(value, "to_agent_id") and hasattr(value, "state"):
        return {"from_agent_id": value.from_agent_id, "to_agent_id": value.to_agent_id, "state": value.state.value}
    if hasattr(value, "id") and hasattr(value, "state"):
        return {"id": value.id, "state": value.state.value, "from_agent_id": value.from_agent_id, "to_agent_id": value.to_agent_id}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _now(turn: int) -> datetime:
    return datetime(2026, 1, 12, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=turn)


def _reset_sqlite_database(db_url: str) -> None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return
    database_path = Path(url.database)
    for path in [database_path, Path(f"{database_path}-wal"), Path(f"{database_path}-shm")]:
        if path.exists():
            path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run unified agent lifecycle experiment.")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--turns", type=int, default=30)
    parser.add_argument("--baseline-model", default="gpt-4o-mini")
    parser.add_argument("--contact-limit", type=int, default=MAX_CONTACTS_PER_AGENT)
    parser.add_argument("--negotiation-limit", type=int, default=MAX_ACTIVE_NEGOTIATIONS_PER_AGENT)
    parser.add_argument("--reset-db", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(run_unified_agent_lifecycle_experiment(
        db_url=args.db_url,
        output_dir=args.output_dir,
        turns=args.turns,
        baseline_model=args.baseline_model,
        reset_db=args.reset_db,
        contact_limit=args.contact_limit,
        negotiation_limit=args.negotiation_limit,
    ), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
