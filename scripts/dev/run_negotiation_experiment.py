from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from net_working_platform.application.graph_mermaid import render_graph_snapshot_mermaid
from net_working_platform.application.llm_decisions import build_turn_decision_json_schema, execute_llm_decision, parse_llm_decision
from net_working_platform.experiments.artifacts import graph_delta, graph_snapshot_for_db, timeline_record_from_transcript_record, write_jsonl
from net_working_platform.experiments.prompts import build_representative_decision_prompt_package
from net_working_platform.experiments.scenarios import PairwiseStrategyScenario, seed_pairwise_strategy_scenario
from net_working_platform.experiments.strategies import get_strategy
from net_working_platform.storage.repositories import SqlProtocolEventRepository
from net_working_platform.storage.schema import metadata, negotiations, protocol_events
from net_working_platform.storage.services import create_sql_negotiation_service
from scripts.dev.run_unified_agent_lifecycle_experiment import _request_openai_json

NegotiationDecisionProvider = Callable[[dict[str, object]], dict[str, Any]]


def run_negotiation_experiment(
    *,
    db_url: str,
    output_dir: Path,
    turns: int = 12,
    baseline_model: str = "gpt-4o-mini",
    reset_db: bool = False,
    scenario_name: str = "pairwise-facts",
    client_strategy_id: str = "CLIENT-FAST-ANY",
    principal_strategy_id: str = "PRINCIPAL-FAST-MINIMUMS",
    decision_provider: NegotiationDecisionProvider | None = None,
) -> dict[str, object]:
    """Run a negotiation-only model experiment from an active negotiation seed."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if reset_db:
        _reset_sqlite_database(db_url)
    scenario = _seed_negotiation_scenario(
        db_url,
        scenario_name=scenario_name,
        client_strategy_id=client_strategy_id,
        principal_strategy_id=principal_strategy_id,
    )
    initial_snapshot = graph_snapshot_for_db(db_url, generated_at=_now(0))
    schedule = [scenario.client_agent_id, scenario.principal_agent_id]
    transcript: list[dict[str, object]] = []
    for turn in range(1, turns + 1):
        actor_agent_id = schedule[(turn - 1) % len(schedule)]
        before_snapshot = graph_snapshot_for_db(db_url, generated_at=_now(turn))
        record = _execute_turn(
            db_url=db_url,
            scenario=scenario,
            actor_agent_id=actor_agent_id,
            turn=turn,
            baseline_model=baseline_model,
            decision_provider=decision_provider,
        )
        after_snapshot = graph_snapshot_for_db(db_url, generated_at=_now(turn) + timedelta(seconds=1))
        record["graph_delta"] = graph_delta(before_snapshot, after_snapshot)
        transcript.append(record)

    final_snapshot = graph_snapshot_for_db(db_url, generated_at=_now(turns + 1))
    summary = _summary(
        db_url=db_url,
        output_dir=output_dir,
        scenario=scenario,
        transcript=transcript,
        baseline_model=baseline_model,
        reset_db=reset_db,
        scenario_name=scenario_name,
        client_strategy_id=client_strategy_id,
        principal_strategy_id=principal_strategy_id,
    )
    (output_dir / "transcript.jsonl").write_text("".join(json.dumps(_jsonable(record), sort_keys=True) + "\n" for record in transcript), encoding="utf-8")
    write_jsonl(output_dir / "graph_events.jsonl", [timeline_record_from_transcript_record(record, validation=record.get("validation")) for record in transcript])
    _write_graph_artifacts(output_dir, initial_snapshot, final_snapshot)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _seed_negotiation_scenario(
    db_url: str,
    *,
    scenario_name: str,
    client_strategy_id: str,
    principal_strategy_id: str,
) -> PairwiseStrategyScenario:
    if scenario_name != "pairwise-facts":
        raise ValueError(f"unsupported negotiation scenario: {scenario_name}")
    return seed_pairwise_strategy_scenario(
        db_url,
        client_strategy_id=client_strategy_id,
        principal_strategy_id=principal_strategy_id,
    )


def _execute_turn(
    *,
    db_url: str,
    scenario: PairwiseStrategyScenario,
    actor_agent_id: str,
    turn: int,
    baseline_model: str,
    decision_provider: NegotiationDecisionProvider | None,
) -> dict[str, object]:
    before_event_count = _event_count(db_url, scenario.negotiation_id)
    context = _decision_context(db_url, scenario, actor_agent_id)
    valid_actions = _valid_actions(context, scenario.negotiation_id)
    available_fact_fields = _available_fact_fields(context, scenario.negotiation_id)
    validation: dict[str, object] | None = None
    raw = None
    execution = None
    error = None
    try:
        if not valid_actions:
            raise ValueError("no valid negotiation actions available for scheduled actor")
        schema = build_turn_decision_json_schema(
            valid_actions=valid_actions,
            actor_agent_id=actor_agent_id,
            negotiation_id=scenario.negotiation_id,
            available_fact_fields=available_fact_fields,
        )
        raw = decision_provider(context) if decision_provider is not None else _request_openai_json(
            prompt=_prompt(context, scenario, actor_agent_id),
            model=baseline_model,
            json_schema=schema,
        )
        decision = parse_llm_decision(raw)
        focus_error = _focus_error(
            raw=raw,
            expected_actor_agent_id=actor_agent_id,
            expected_negotiation_id=scenario.negotiation_id,
            valid_actions=valid_actions,
        )
        if focus_error is not None:
            validation = {"valid": False, "error": focus_error, "available_fact_fields": available_fact_fields}
            return {
                "turn": turn,
                "actor_agent_id": actor_agent_id,
                "negotiation_id": scenario.negotiation_id,
                "context": context,
                "valid_actions": valid_actions,
                "raw_decision": raw,
                "validation": validation,
                "execution": None,
                "error": None,
                "event_delta": [],
            }
        validation = {"valid": True, "action": decision.action.value, "available_fact_fields": available_fact_fields}
        with create_engine(db_url).begin() as connection:
            service = create_sql_negotiation_service(
                connection,
                new_id=lambda: "unused",
                now=lambda: _now(turn),
                represented_party_profiles_by_agent=scenario.represented_party_profiles_by_agent,
            )
            execution = _jsonable(execute_llm_decision(decision, service))
    except Exception as exc:  # pragma: no cover - live diagnostics
        error = {"type": type(exc).__name__, "message": str(exc)}
        validation = validation or {"valid": False, "error": error, "available_fact_fields": available_fact_fields}
    return {
        "turn": turn,
        "actor_agent_id": actor_agent_id,
        "negotiation_id": scenario.negotiation_id,
        "context": context,
        "valid_actions": valid_actions,
        "raw_decision": raw,
        "validation": validation,
        "execution": execution,
        "error": error,
        "event_delta": _event_delta(db_url, scenario.negotiation_id, before_event_count),
    }


def _focus_error(
    *,
    raw: dict[str, Any],
    expected_actor_agent_id: str,
    expected_negotiation_id: str,
    valid_actions: list[str],
) -> dict[str, object] | None:
    if raw.get("actor_agent_id") != expected_actor_agent_id:
        return {
            "type": "FocusMismatch",
            "expected_actor_agent_id": expected_actor_agent_id,
            "actual_actor_agent_id": raw.get("actor_agent_id"),
        }
    if raw.get("negotiation_id") != expected_negotiation_id:
        return {
            "type": "FocusMismatch",
            "expected_negotiation_id": expected_negotiation_id,
            "actual_negotiation_id": raw.get("negotiation_id"),
        }
    if raw.get("action") not in valid_actions:
        return {
            "type": "ActionUnavailable",
            "action": raw.get("action"),
            "valid_actions": valid_actions,
        }
    return None


def _decision_context(db_url: str, scenario: PairwiseStrategyScenario, actor_agent_id: str) -> dict[str, object]:
    with create_engine(db_url).begin() as connection:
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: "unused",
            now=lambda: _now(0),
            represented_party_profiles_by_agent=scenario.represented_party_profiles_by_agent,
        )
        decision_context = service.get_agent_decision_context(agent_id=actor_agent_id, recent_event_limit=20, max_active_negotiations=2)
    role = "client" if actor_agent_id == scenario.client_agent_id else "principal"
    strategy_id = scenario.client_strategy_id if role == "client" else scenario.principal_strategy_id
    return {
        "actor_agent_id": actor_agent_id,
        "represented_type": role,
        "active_strategy": get_strategy(strategy_id).to_prompt_record(),
        "focus_negotiation_id": scenario.negotiation_id,
        "decision_context": decision_context,
    }


def _prompt(context: dict[str, object], scenario: PairwiseStrategyScenario, actor_agent_id: str) -> str:
    role = "client" if actor_agent_id == scenario.client_agent_id else "principal"
    strategy = context.get("active_strategy") if isinstance(context.get("active_strategy"), dict) else {}
    package = build_representative_decision_prompt_package(
        decision_context=context,
        represented_type=role,
        strategy_priority=strategy,
    )
    return str(package["prompt"])


def _valid_actions(context: dict[str, object], negotiation_id: str) -> list[str]:
    decision_context = context.get("decision_context", {})
    if not isinstance(decision_context, dict):
        return []
    by_negotiation = decision_context.get("valid_next_actions_by_negotiation", {})
    if not isinstance(by_negotiation, dict):
        return []
    actions = by_negotiation.get(negotiation_id, [])
    return [str(action) for action in actions] if isinstance(actions, list) else []


def _available_fact_fields(context: dict[str, object], negotiation_id: str) -> list[str]:
    decision_context = context.get("decision_context", {})
    if not isinstance(decision_context, dict):
        return []
    available = decision_context.get("available_fact_disclosures_by_negotiation", {})
    if not isinstance(available, dict):
        return []
    records = available.get(negotiation_id, [])
    if not isinstance(records, list):
        return []
    return sorted({str(record["field"]) for record in records if isinstance(record, dict) and "field" in record})


def _event_count(db_url: str, negotiation_id: str) -> int:
    with create_engine(db_url).begin() as connection:
        return len(SqlProtocolEventRepository(connection).list_for_negotiation(negotiation_id))


def _event_delta(db_url: str, negotiation_id: str, before_event_count: int) -> list[dict[str, object]]:
    with create_engine(db_url).begin() as connection:
        events = SqlProtocolEventRepository(connection).list_for_negotiation(negotiation_id)
    return [_event_to_record(event) for event in events[before_event_count:]]


def _event_to_record(event: object) -> dict[str, object]:
    return {
        "type": event.type.value,
        "actor_agent_id": event.actor_agent_id,
        "negotiation_id": event.negotiation_id,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": _jsonable(event.payload),
    }


def _summary(
    *,
    db_url: str,
    output_dir: Path,
    scenario: PairwiseStrategyScenario,
    transcript: list[dict[str, object]],
    baseline_model: str,
    reset_db: bool,
    scenario_name: str,
    client_strategy_id: str,
    principal_strategy_id: str,
) -> dict[str, object]:
    with create_engine(db_url).begin() as connection:
        negotiation_rows = connection.execute(negotiations.select()).all()
        event_rows = connection.execute(protocol_events.select()).all()
    return {
        "scenario": scenario_name,
        "runner": "negotiation",
        "runner_family": "negotiation-only",
        "seed_id": scenario_name,
        "seed_variant": "default",
        "baseline_model": baseline_model,
        "reset_db": reset_db,
        "turns": len(transcript),
        "client_strategy": client_strategy_id,
        "principal_strategy": principal_strategy_id,
        "focus_negotiation_id": scenario.negotiation_id,
        "metrics": {
            "messages_sent": sum(1 for row in event_rows if row._mapping["type"] == "message"),
            "invalid_attempts": sum(1 for record in transcript if isinstance(record.get("validation"), dict) and record["validation"].get("valid") is False),
            "focus_mismatch_attempts": sum(1 for record in transcript if isinstance(record.get("validation"), dict) and isinstance(record["validation"].get("error"), dict) and record["validation"]["error"].get("type") == "FocusMismatch"),
            "negotiation_states": _counts(row._mapping["state"] for row in negotiation_rows),
            "events_by_type": _counts(row._mapping["type"] for row in event_rows),
            "decisions_by_action": _counts((record.get("raw_decision") or {}).get("action") for record in transcript if isinstance(record.get("raw_decision"), dict)),
            "errors": sum(1 for record in transcript if record.get("error") is not None),
        },
        "outputs": {
            "summary": str(output_dir / "summary.json"),
            "transcript": str(output_dir / "transcript.jsonl"),
            "graph_events": str(output_dir / "graph_events.jsonl"),
        },
    }


def _write_graph_artifacts(output_dir: Path, initial_snapshot: dict[str, object], final_snapshot: dict[str, object]) -> None:
    (output_dir / "initial_graph.json").write_text(json.dumps(initial_snapshot, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "final_graph.json").write_text(json.dumps(final_snapshot, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "initial_graph.mmd").write_text(render_graph_snapshot_mermaid(initial_snapshot), encoding="utf-8")
    (output_dir / "final_graph.mmd").write_text(render_graph_snapshot_mermaid(final_snapshot), encoding="utf-8")


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
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "__dict__"):
        return _jsonable(value.__dict__)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _now(turn: int) -> datetime:
    return datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=turn)


def _reset_sqlite_database(db_url: str) -> None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return
    database_path = Path(url.database)
    for path in [database_path, Path(f"{database_path}-wal"), Path(f"{database_path}-shm")]:
        if path.exists():
            try:
                path.unlink()
            except PermissionError:
                engine = create_engine(db_url)
                try:
                    metadata.drop_all(engine)
                finally:
                    engine.dispose()
                return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run negotiation-only experiment from an active negotiation seed.")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--turns", type=int, default=12)
    parser.add_argument("--baseline-model", default="gpt-4o-mini")
    parser.add_argument("--scenario", default="pairwise-facts", choices=["pairwise-facts"])
    parser.add_argument("--client-strategy", default="CLIENT-FAST-ANY")
    parser.add_argument("--principal-strategy", default="PRINCIPAL-FAST-MINIMUMS")
    parser.add_argument("--reset-db", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(run_negotiation_experiment(
        db_url=args.db_url,
        output_dir=args.output_dir,
        turns=args.turns,
        baseline_model=args.baseline_model,
        reset_db=args.reset_db,
        scenario_name=args.scenario,
        client_strategy_id=args.client_strategy,
        principal_strategy_id=args.principal_strategy,
    ), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
