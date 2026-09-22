from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url

from net_working_platform.application.discovery_decisions import (
    build_discovery_turn_json_schema,
    execute_discovery_decision,
    parse_discovery_decision,
)
from net_working_platform.experiments.scenarios import WeakDiscoveryScenario, seed_weak_discovery_scenario
from net_working_platform.storage.schema import agent_connections, metadata, protocol_events
from net_working_platform.storage.services import create_sql_discovery_service

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def run_weak_discovery_experiment(
    *,
    db_url: str,
    output_dir: Path,
    baseline_model: str = "gpt-4o-mini",
    reset_db: bool = False,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    if reset_db:
        _reset_sqlite_database(db_url)
    scenario = seed_weak_discovery_scenario(db_url)
    scheduled_agents = [
        scenario.marketing_client_agent_ids[0],
        scenario.marketing_client_agent_ids[1],
        scenario.programming_client_agent_id,
    ]
    transcript = [_execute_turn(db_url, scenario, agent_id, baseline_model) for agent_id in scheduled_agents]
    summary = _summary(db_url, output_dir, scenario, transcript, baseline_model, reset_db)
    (output_dir / "transcript.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in transcript),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _execute_turn(db_url: str, scenario: WeakDiscoveryScenario, actor_agent_id: str, baseline_model: str) -> dict[str, object]:
    field = scenario.agent_fields[actor_agent_id]
    engine = create_engine(db_url)
    with engine.begin() as connection:
        service = create_sql_discovery_service(connection, now=_fixed_now)
        discoverable = service.list_discoverable_agents(actor_agent_id=actor_agent_id, field=field)

    valid_actions = ["probe_weak_connection", "request_contact"] if discoverable else ["defer"]
    schema = build_discovery_turn_json_schema(
        actor_agent_id=actor_agent_id,
        valid_actions=valid_actions,
        discoverable_agent_ids=[str(record["agent_id"]) for record in discoverable],
        fields=[field] if discoverable else [],
    )
    prompt = _prompt(actor_agent_id, field, discoverable)
    raw_decision = _request_openai_json(prompt=prompt, model=baseline_model, json_schema=schema)
    validation = _validate(raw_decision, actor_agent_id, discoverable, field)
    execution = None
    error = None
    if validation["valid"]:
        try:
            decision = parse_discovery_decision(raw_decision)
            with engine.begin() as connection:
                service = create_sql_discovery_service(connection, now=_fixed_now)
                execution = _jsonable(execute_discovery_decision(decision, service))
        except Exception as exc:  # pragma: no cover - transcript diagnostics
            error = {"type": type(exc).__name__, "message": str(exc)}
    return {
        "actor_agent_id": actor_agent_id,
        "field": field,
        "discoverable_agents": discoverable,
        "prompt": prompt,
        "raw_decision": raw_decision,
        "validation": validation,
        "execution": execution,
        "error": error,
    }


def _prompt(actor_agent_id: str, field: str, discoverable: list[dict[str, object]]) -> str:
    return "\n".join(
        [
            "You are a representative agent testing weak discovery on Net Working Platform.",
            "Goal: find useful same-field agents for possible future negotiation. Do not choose agents outside the provided discoverable list.",
            "In this experiment the scheduled actors represent clients seeking jobs; prefer principal agents offering same-field opportunities over peer client agents.",
            "Prefer request_contact when a discoverable agent appears directly relevant; otherwise probe or defer.",
            "Return exactly one JSON object matching the schema.",
            json.dumps(
                {
                    "actor_agent_id": actor_agent_id,
                    "represented_party_field": field,
                    "discoverable_agents": discoverable,
                },
                sort_keys=True,
            ),
        ]
    )


def _request_openai_json(*, prompt: str, model: str, json_schema: dict[str, object]) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI discovery experiments")
    payload = {
        "model": model,
        "input": prompt,
        "max_output_tokens": 500,
        "text": {"format": {"type": "json_schema", "name": "discovery_decision", "schema": json_schema, "strict": True}},
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        response_payload = json.loads(response.read().decode("utf-8"))
    text = "".join(
        content.get("text", "")
        for item in response_payload.get("output", [])
        for content in item.get("content", [])
        if content.get("type") == "output_text"
    )
    return json.loads(text)


def _validate(raw_decision: dict[str, Any], actor_agent_id: str, discoverable: list[dict[str, object]], field: str) -> dict[str, object]:
    try:
        parsed = parse_discovery_decision(raw_decision)
    except Exception as exc:
        return {"valid": False, "error": {"type": type(exc).__name__, "message": str(exc)}}
    valid_targets = {record["agent_id"] for record in discoverable}
    if parsed.action.value != "defer" and raw_decision.get("target_agent_id") not in valid_targets:
        return {"valid": False, "action": parsed.action.value, "error": {"type": "TargetUnavailable"}}
    if raw_decision.get("actor_agent_id") != actor_agent_id or raw_decision.get("field") != field:
        return {"valid": False, "action": parsed.action.value, "error": {"type": "FocusMismatch"}}
    return {"valid": True, "action": parsed.action.value}


def _summary(db_url: str, output_dir: Path, scenario: WeakDiscoveryScenario, transcript: list[dict[str, object]], baseline_model: str, reset_db: bool) -> dict[str, object]:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        rows = connection.execute(select(agent_connections)).all()
        event_rows = connection.execute(select(protocol_events)).all()
    final_connections = [_jsonable(dict(row._mapping)) for row in rows]
    events = [_jsonable(dict(row._mapping)) for row in event_rows]
    return {
        "scenario": "weak_discovery",
        "baseline_model": baseline_model,
        "reset_db": reset_db,
        "agent_fields": scenario.agent_fields,
        "metrics": {
            "turns": len(transcript),
            "valid_decisions": sum(1 for record in transcript if record["validation"]["valid"]),
            "invalid_decisions": sum(1 for record in transcript if not record["validation"]["valid"] or record["error"] is not None),
            "connections_created": len(final_connections),
            "events_by_type": _counts(row["type"] for row in events),
            "decisions_by_action": _counts(record.get("validation", {}).get("action") for record in transcript),
        },
        "final_connections": final_connections,
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


def _jsonable(value: object) -> object:
    if hasattr(value, "from_agent_id") and hasattr(value, "to_agent_id") and hasattr(value, "state"):
        return {"from_agent_id": value.from_agent_id, "to_agent_id": value.to_agent_id, "state": value.state.value}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _fixed_now():
    from datetime import datetime, timezone

    return datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)


def _reset_sqlite_database(db_url: str) -> None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return
    database_path = Path(url.database)
    for path in [database_path, Path(f"{database_path}-wal"), Path(f"{database_path}-shm")]:
        if path.exists():
            path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a weak discovery LLM experiment.")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--baseline-model", default="gpt-4o-mini")
    parser.add_argument("--reset-db", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(run_weak_discovery_experiment(db_url=args.db_url, output_dir=args.output_dir, baseline_model=args.baseline_model, reset_db=args.reset_db), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
