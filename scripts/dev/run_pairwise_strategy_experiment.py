from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from net_working_platform.application.llm_decisions import (
    LlmDecision,
    LlmDecisionAction,
    build_turn_decision_json_schema,
    execute_llm_decision,
    parse_llm_decision,
)
from net_working_platform.domain.model import Negotiation, ProtocolEvent
from net_working_platform.experiments.prompts import build_strategy_prompt_package
from net_working_platform.experiments.scenarios import PairwiseStrategyScenario, seed_pairwise_strategy_scenario
from net_working_platform.experiments.strategies import AgentStrategy, get_strategy
from net_working_platform.storage.repositories import SqlNegotiationRepository, SqlProtocolEventRepository
from net_working_platform.storage.schema import metadata
from net_working_platform.storage.services import create_sql_negotiation_service
from scripts.dev.openai_provider import request_openai_decision


DecisionProvider = Callable[[str], LlmDecision | dict[str, Any]]


def run_pairwise_strategy_experiment(
    *,
    db_url: str,
    output_dir: Path,
    client_strategy_id: str,
    principal_strategy_id: str,
    turns: int = 6,
    decision_source: str = "openai",
    decision_provider: DecisionProvider | None = None,
    baseline_model: str = "gpt-4o-mini",
    reset_db: bool = False,
) -> dict[str, object]:
    if decision_source not in {"openai", "injected_llm"}:
        raise ValueError(f"unsupported decision source: {decision_source}")
    if turns < 1:
        raise ValueError("turns must be at least 1")

    client_strategy = get_strategy(client_strategy_id)
    principal_strategy = get_strategy(principal_strategy_id)
    if client_strategy.role != "client":
        raise ValueError("client_strategy_id must refer to a client strategy")
    if principal_strategy.role != "principal":
        raise ValueError("principal_strategy_id must refer to a principal strategy")

    output_dir.mkdir(parents=True, exist_ok=True)
    if reset_db:
        _reset_sqlite_database(db_url)
    scenario = seed_pairwise_strategy_scenario(
        db_url,
        client_strategy_id=client_strategy_id,
        principal_strategy_id=principal_strategy_id,
    )

    transcript: list[dict[str, object]] = []
    for index, scheduled_actor in enumerate(_scheduled_actors(scenario, turns), start=1):
        transcript.append(
            _execute_turn(
                db_url=db_url,
                scenario=scenario,
                turn=index,
                scheduled_actor_agent_id=scheduled_actor,
                client_strategy=client_strategy,
                principal_strategy=principal_strategy,
                decision_source=decision_source,
                decision_provider=decision_provider,
                baseline_model=baseline_model,
            )
        )

    summary = _summary(
        db_url=db_url,
        output_dir=output_dir,
        scenario=scenario,
        transcript=transcript,
        client_strategy=client_strategy,
        principal_strategy=principal_strategy,
        decision_source=decision_source,
        baseline_model=baseline_model,
        reset_db=reset_db,
    )
    (output_dir / "transcript.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in transcript),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _scheduled_actors(scenario: PairwiseStrategyScenario, turns: int) -> list[str]:
    actors = [scenario.client_agent_id, scenario.principal_agent_id]
    return [actors[index % 2] for index in range(turns)]


def _execute_turn(
    *,
    db_url: str,
    scenario: PairwiseStrategyScenario,
    turn: int,
    scheduled_actor_agent_id: str,
    client_strategy: AgentStrategy,
    principal_strategy: AgentStrategy,
    decision_source: str,
    decision_provider: DecisionProvider | None,
    baseline_model: str,
) -> dict[str, object]:
    active_strategy = client_strategy if scheduled_actor_agent_id == scenario.client_agent_id else principal_strategy
    counterpart_strategy = principal_strategy if active_strategy.role == "client" else client_strategy
    represented_party_facts = scenario.client_facts if active_strategy.role == "client" else scenario.principal_facts
    counterpart_facts = scenario.principal_facts if active_strategy.role == "client" else scenario.client_facts
    context_package = _context_package(
        db_url=db_url,
        scenario=scenario,
        scheduled_actor_agent_id=scheduled_actor_agent_id,
        active_strategy=active_strategy,
        counterpart_strategy=counterpart_strategy,
        represented_party_facts=represented_party_facts,
        counterpart_facts=counterpart_facts,
    )
    valid_actions = _valid_actions_from_context(context_package, scenario.negotiation_id)
    if not valid_actions:
        return {
            "turn": turn,
            "decision_source": decision_source,
            "scheduled_actor_agent_id": scheduled_actor_agent_id,
            "negotiation_id": scenario.negotiation_id,
            "strategy": active_strategy.to_prompt_record(),
            "counterpart_strategy": counterpart_strategy.to_prompt_record(),
            "prompt": context_package["prompt"],
            "raw_decision": None,
            "validation": {
                "valid": False,
                "error": {
                    "type": "NoAvailableActions",
                    "message": "no valid next actions are available for the scheduled turn",
                },
            },
            "execution": None,
            "error": None,
            "event_delta": [],
            "skipped": True,
        }
    decision_schema = build_turn_decision_json_schema(
        valid_actions=valid_actions,
        actor_agent_id=scheduled_actor_agent_id,
        negotiation_id=scenario.negotiation_id,
    )
    raw_decision: dict[str, Any] | None = None
    provider_error = None
    try:
        raw_decision = _request_decision(
            prompt=str(context_package["prompt"]),
            provider=decision_provider,
            baseline_model=baseline_model,
            decision_schema=decision_schema,
        )
    except Exception as exc:  # pragma: no cover - defensive transcript path
        provider_error = {"type": type(exc).__name__, "message": str(exc)}

    validation = {"valid": False, "error": provider_error} if provider_error else _validate_decision(raw_decision or {})
    if validation["valid"]:
        validation = _validate_focus(
            raw_decision=raw_decision or {},
            expected_actor_agent_id=scheduled_actor_agent_id,
            expected_negotiation_id=scenario.negotiation_id,
            validation=validation,
        )
    if validation["valid"]:
        validation = _validate_action_available(
            raw_decision=raw_decision or {},
            context_package=context_package,
            expected_negotiation_id=scenario.negotiation_id,
            validation=validation,
        )

    execution_result = None
    error = None
    event_delta: list[dict[str, object]] = []
    if validation["valid"]:
        try:
            if validation.get("action") == LlmDecisionAction.DEFER.value:
                execution_result = {"executed": False, "action": "defer", "result": None}
            else:
                before_events = _event_count(db_url, scenario.negotiation_id)
                execution_result = _execute_decision(
                    db_url=db_url,
                    raw_decision=raw_decision or {},
                    occurred_at=datetime(2026, 1, 8, 12, 10, tzinfo=timezone.utc) + timedelta(minutes=turn - 1),
                )
                events = _events(db_url, scenario.negotiation_id)
                event_delta = events[before_events:]
        except Exception as exc:  # pragma: no cover - defensive transcript path
            error = {"type": type(exc).__name__, "message": str(exc)}

    return {
        "turn": turn,
        "decision_source": decision_source,
        "scheduled_actor_agent_id": scheduled_actor_agent_id,
        "negotiation_id": scenario.negotiation_id,
        "strategy": active_strategy.to_prompt_record(),
        "counterpart_strategy": counterpart_strategy.to_prompt_record(),
        "prompt": context_package["prompt"],
        "raw_decision": raw_decision,
        "validation": validation,
        "execution": execution_result,
        "error": error,
        "event_delta": event_delta,
        "skipped": False,
    }


def _context_package(
    *,
    db_url: str,
    scenario: PairwiseStrategyScenario,
    scheduled_actor_agent_id: str,
    active_strategy: AgentStrategy,
    counterpart_strategy: AgentStrategy,
    represented_party_facts: dict[str, object],
    counterpart_facts: dict[str, object],
) -> dict[str, object]:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: "unused",
            now=lambda: datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc),
        )
        decision_context = service.get_agent_decision_context(
            agent_id=scheduled_actor_agent_id,
            max_active_negotiations=5,
            recent_event_limit=30,
        )
    return build_strategy_prompt_package(
        decision_context=decision_context,
        active_strategy=active_strategy,
        counterpart_strategy=counterpart_strategy,
        represented_party_facts=represented_party_facts,
        counterpart_facts=counterpart_facts,
        scheduled_actor_agent_id=scheduled_actor_agent_id,
        focus_negotiation_id=scenario.negotiation_id,
    )


def _request_decision(
    *,
    prompt: str,
    provider: DecisionProvider | None,
    baseline_model: str,
    decision_schema: dict[str, object],
) -> dict[str, Any]:
    decision = (
        provider(prompt)
        if provider is not None
        else request_openai_decision(prompt=prompt, model=baseline_model, json_schema=decision_schema)
    )
    if isinstance(decision, LlmDecision):
        return {"action": decision.action.value, **decision.payload}
    return decision


def _valid_actions_from_context(context_package: dict[str, object], negotiation_id: str) -> list[str]:
    decision_context = context_package.get("decision_context", {})
    if not isinstance(decision_context, dict):
        return []
    valid_by_negotiation = decision_context.get("valid_next_actions_by_negotiation", {})
    if not isinstance(valid_by_negotiation, dict):
        return []
    valid_actions = valid_by_negotiation.get(negotiation_id, [])
    if not isinstance(valid_actions, list):
        return []
    return [str(action) for action in valid_actions]


def _reset_sqlite_database(db_url: str) -> None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite"):
        raise ValueError("reset_db is only supported for sqlite database URLs")
    if not url.database or url.database == ":memory:":
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


def _validate_decision(decision: dict[str, Any]) -> dict[str, object]:
    try:
        parsed = parse_llm_decision(decision)
    except Exception as exc:
        return {"valid": False, "error": {"type": type(exc).__name__, "message": str(exc)}}
    return {"valid": True, "action": parsed.action.value}


def _validate_focus(
    *,
    raw_decision: dict[str, Any],
    expected_actor_agent_id: str,
    expected_negotiation_id: str,
    validation: dict[str, object],
) -> dict[str, object]:
    actor_agent_id = raw_decision.get("actor_agent_id")
    if actor_agent_id != expected_actor_agent_id:
        return {
            "valid": False,
            "action": validation.get("action"),
            "error": {
                "type": "FocusMismatch",
                "message": f"decision actor_agent_id must be {expected_actor_agent_id}",
                "expected_actor_agent_id": expected_actor_agent_id,
                "actual_actor_agent_id": actor_agent_id,
            },
        }
    if validation.get("action") == LlmDecisionAction.DEFER.value:
        return validation
    negotiation_id = raw_decision.get("negotiation_id")
    if negotiation_id != expected_negotiation_id:
        return {
            "valid": False,
            "action": validation.get("action"),
            "error": {
                "type": "FocusMismatch",
                "message": f"decision negotiation_id must be {expected_negotiation_id}",
                "expected_negotiation_id": expected_negotiation_id,
                "actual_negotiation_id": negotiation_id,
            },
        }
    return validation


def _validate_action_available(
    *,
    raw_decision: dict[str, Any],
    context_package: dict[str, object],
    expected_negotiation_id: str,
    validation: dict[str, object],
) -> dict[str, object]:
    decision_context = context_package.get("decision_context", {})
    if not isinstance(decision_context, dict):
        return validation
    valid_by_negotiation = decision_context.get("valid_next_actions_by_negotiation", {})
    if not isinstance(valid_by_negotiation, dict):
        return validation
    valid_actions = valid_by_negotiation.get(expected_negotiation_id, [])
    if not isinstance(valid_actions, list):
        return validation
    action = raw_decision.get("action")
    if action not in valid_actions:
        return {
            "valid": False,
            "action": validation.get("action"),
            "error": {
                "type": "ActionUnavailable",
                "message": f"decision action must be valid for negotiation {expected_negotiation_id}",
                "expected_negotiation_id": expected_negotiation_id,
                "valid_actions": valid_actions,
                "actual_action": action,
            },
        }
    return validation


def _execute_decision(*, db_url: str, raw_decision: dict[str, Any], occurred_at: datetime) -> dict[str, object]:
    decision = parse_llm_decision(raw_decision)
    engine = create_engine(db_url)
    with engine.begin() as connection:
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: "unused",
            now=lambda: occurred_at,
        )
        result = execute_llm_decision(decision, service)
    return _jsonable(result)


def _event_count(db_url: str, negotiation_id: str) -> int:
    return len(_events(db_url, negotiation_id))


def _events(db_url: str, negotiation_id: str) -> list[dict[str, object]]:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        events = SqlProtocolEventRepository(connection).list_for_negotiation(negotiation_id)
    return [_event_to_record(event) for event in events]


def _summary(
    *,
    db_url: str,
    output_dir: Path,
    scenario: PairwiseStrategyScenario,
    transcript: list[dict[str, object]],
    client_strategy: AgentStrategy,
    principal_strategy: AgentStrategy,
    decision_source: str,
    baseline_model: str,
    reset_db: bool,
) -> dict[str, object]:
    executed_actions = [
        record["execution"].get("action")
        for record in transcript
        if isinstance(record.get("execution"), dict)
    ]
    invalid_attempts = [record for record in transcript if not record["validation"]["valid"] or record["error"] is not None]
    skipped_turns = [record for record in transcript if record.get("skipped")]
    invalid_attempts = [record for record in invalid_attempts if not record.get("skipped")]
    focus_mismatch_attempts = [
        record
        for record in transcript
        if record.get("validation", {}).get("error", {}).get("type") == "FocusMismatch"
    ]
    final_state = _negotiation_state(db_url, scenario.negotiation_id)
    return {
        "scenario": "pairwise_strategy",
        "db_url": db_url,
        "decision_source": decision_source,
        "baseline_model": baseline_model,
        "reset_db": reset_db,
        "turns_executed": len(transcript),
        "client_strategy": client_strategy.to_prompt_record(),
        "principal_strategy": principal_strategy.to_prompt_record(),
        "client_facts": scenario.client_facts,
        "principal_facts": scenario.principal_facts,
        "final_negotiation_state": final_state,
        "metrics": {
            "messages_sent": executed_actions.count("send_message"),
            "match_proposals": executed_actions.count("propose_match"),
            "matches_accepted": executed_actions.count("accept_match"),
            "negotiations_closed": executed_actions.count("close_negotiation"),
            "deferrals": executed_actions.count("defer"),
            "invalid_attempts": len(invalid_attempts),
            "focus_mismatch_attempts": len(focus_mismatch_attempts),
            "skipped_no_action_turns": len(skipped_turns),
            "executed_decisions_by_action": _counts(executed_actions),
            "event_deltas_by_type": _counts(
                event.get("type")
                for record in transcript
                for event in record.get("event_delta", [])
                if isinstance(event, dict)
            ),
        },
        "outputs": {
            "transcript": str(output_dir / "transcript.jsonl"),
            "summary": str(output_dir / "summary.json"),
        },
    }


def _negotiation_state(db_url: str, negotiation_id: str) -> str:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        return SqlNegotiationRepository(connection).get(negotiation_id).state.value


def _counts(values: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a pairwise strategy experiment.")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--client-strategy", required=True)
    parser.add_argument("--principal-strategy", required=True)
    parser.add_argument("--turns", type=int, default=6)
    parser.add_argument("--decision-source", choices=["openai"], default="openai")
    parser.add_argument("--baseline-model", default="gpt-4o-mini")
    parser.add_argument("--reset-db", action="store_true", help="Delete an existing sqlite DB file before seeding.")
    args = parser.parse_args(argv)

    print(
        json.dumps(
            run_pairwise_strategy_experiment(
                db_url=args.db_url,
                output_dir=args.output_dir,
                client_strategy_id=args.client_strategy,
                principal_strategy_id=args.principal_strategy,
                turns=args.turns,
                decision_source=args.decision_source,
                baseline_model=args.baseline_model,
                reset_db=args.reset_db,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
