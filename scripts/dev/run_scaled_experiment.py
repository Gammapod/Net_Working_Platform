from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from net_working_platform.application.graph_mermaid import render_graph_snapshot_mermaid
from net_working_platform.application.graph_snapshots import build_graph_snapshot
from net_working_platform.application.llm_decisions import LlmDecision, LlmDecisionAction, parse_llm_decision
from net_working_platform.experiments.scenarios import seed_market_scenario, seed_two_client_two_principal_scenario
from net_working_platform.storage.graph_snapshots import SqlGraphSnapshotReader
from net_working_platform.storage.repositories import SqlProtocolEventRepository
from net_working_platform.storage.schema import metadata
from scripts.dev.experiment_artifacts import graph_delta, graph_snapshot_for_db, timeline_record_from_transcript_record, write_jsonl
from scripts.dev.openai_provider import request_openai_decision
from scripts.dev.run_supervised_llm_experiment import (
    build_existing_agent_context_package,
    execute_decision_against_existing_scenario,
)


DecisionProvider = Callable[[str], LlmDecision | dict[str, Any]]


@dataclass(frozen=True)
class ScriptedTurn:
    round_number: int
    actor_agent_id: str
    negotiation_id: str
    decision: dict[str, Any]
    rationale: str


def run_scaled_experiment(
    *,
    db_url: str,
    output_dir: Path,
    scenario_name: str = "two-client-two-principal",
    turns: int | None = None,
    rounds: int = 1,
    client_count: int = 20,
    principal_count: int = 10,
    negotiations_per_client: int = 2,
    decision_source: str = "scripted",
    decision_provider: DecisionProvider | None = None,
    openai_model: str = "gpt-4o-mini",
    reset_db: bool = False,
) -> dict[str, object]:
    """Run a deterministic scaled-experiment scaffold with transcript artifacts."""
    if scenario_name not in {"two-client-two-principal", "market"}:
        raise ValueError(f"unsupported scenario: {scenario_name}")
    if decision_source not in {"scripted", "openai", "injected_llm"}:
        raise ValueError(f"unsupported decision source: {decision_source}")

    output_dir.mkdir(parents=True, exist_ok=True)
    if reset_db:
        _reset_sqlite_database(db_url)

    scenario_config: dict[str, object]
    if scenario_name == "market":
        scenario = seed_market_scenario(
            db_url,
            client_count=client_count,
            principal_count=principal_count,
            negotiations_per_client=negotiations_per_client,
        )
        scripted_turns = _market_turns(
            negotiation_ids=scenario.negotiation_ids,
            rounds=rounds,
        )
        scenario_config = {
            "client_count": client_count,
            "principal_count": principal_count,
            "negotiations_per_client": negotiations_per_client,
            "initial_negotiation_count": len(scenario.negotiation_ids),
            "requested_rounds": rounds,
        }
    else:
        seed_two_client_two_principal_scenario(db_url)
        scripted_turns = _scripted_turns()
        scenario_config = {
            "client_count": 2,
            "principal_count": 2,
            "negotiations_per_client": None,
            "initial_negotiation_count": 3,
            "requested_rounds": 1,
        }
    engine = create_engine(db_url)
    selected_turns = scripted_turns[: turns or len(scripted_turns)]

    with engine.begin() as connection:
        initial_snapshot = build_graph_snapshot(
            SqlGraphSnapshotReader(connection),
            now=lambda: datetime(2026, 1, 8, 12, 30, tzinfo=timezone.utc),
        )

    transcript: list[dict[str, object]] = []
    for index, turn in enumerate(selected_turns, start=1):
        transcript.append(
            _execute_turn(
                db_url=db_url,
                index=index,
                turn=turn,
                decision_source=decision_source,
                decision_provider=decision_provider,
                openai_model=openai_model,
            )
        )
    graph_events = [timeline_record_from_transcript_record(record) for record in transcript]

    with engine.begin() as connection:
        final_snapshot = build_graph_snapshot(
            SqlGraphSnapshotReader(connection),
            now=lambda: datetime(2026, 1, 8, 13, 0, tzinfo=timezone.utc),
        )

    summary = _summary(
        scenario_name=scenario_name,
        db_url=db_url,
        transcript=transcript,
        output_dir=output_dir,
        scenario_config=scenario_config,
        decision_source=decision_source,
        reset_db=reset_db,
        initial_snapshot=initial_snapshot,
        final_snapshot=final_snapshot,
    )

    (output_dir / "initial_graph.mmd").write_text(render_graph_snapshot_mermaid(initial_snapshot), encoding="utf-8")
    (output_dir / "final_graph.mmd").write_text(render_graph_snapshot_mermaid(final_snapshot), encoding="utf-8")
    (output_dir / "initial_graph.json").write_text(
        json.dumps(initial_snapshot, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "final_graph.json").write_text(
        json.dumps(final_snapshot, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "transcript.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in transcript),
        encoding="utf-8",
    )
    write_jsonl(output_dir / "graph_events.jsonl", graph_events)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _execute_turn(
    *,
    db_url: str,
    index: int,
    turn: ScriptedTurn,
    decision_source: str,
    decision_provider: DecisionProvider | None,
    openai_model: str,
) -> dict[str, object]:
    prompt: str | None = None
    provider_error = None
    raw_decision = turn.decision
    if decision_source in {"openai", "injected_llm"}:
        try:
            prompt = _prompt_for_turn(db_url=db_url, turn=turn)
            raw_decision = _request_decision(
                prompt=prompt,
                provider=decision_provider,
                openai_model=openai_model,
            )
        except Exception as exc:  # pragma: no cover - defensive transcript path
            provider_error = {"type": type(exc).__name__, "message": str(exc)}

    validation = _validate_decision(raw_decision) if provider_error is None else {"valid": False, "error": provider_error}
    if validation["valid"]:
        validation = _validate_turn_focus(turn=turn, raw_decision=raw_decision, validation=validation)
    execution_result = None
    error = None
    event_delta: list[dict[str, object]] = []
    before_snapshot = _graph_snapshot(db_url, index=index, after=False)
    if validation["valid"]:
        try:
            if validation.get("action") == LlmDecisionAction.DEFER.value:
                execution_result = {"executed": True, "action": "defer", "result": None}
            else:
                before_events = _event_count(db_url, turn.negotiation_id)
                result = execute_decision_against_existing_scenario(
                    db_url=db_url,
                    raw_decision=raw_decision,
                    occurred_at=datetime(2026, 1, 8, 12, 5, tzinfo=timezone.utc) + timedelta(minutes=index - 1),
                )
                execution_result = result["execution"]
                event_delta = result["structured_event_log"][before_events:]
        except Exception as exc:  # pragma: no cover - defensive transcript path
            error = {"type": type(exc).__name__, "message": str(exc)}
    after_snapshot = _graph_snapshot(db_url, index=index, after=True)

    return {
        "turn": index,
        "round": turn.round_number,
        "decision_source": decision_source,
        "actor_agent_id": turn.actor_agent_id,
        "negotiation_id": turn.negotiation_id,
        "rationale": turn.rationale,
        "prompt": prompt,
        "raw_decision": raw_decision,
        "validation": validation,
        "execution": execution_result,
        "error": error,
        "event_delta": event_delta,
        "graph_delta": graph_delta(before_snapshot, after_snapshot),
    }


def _request_decision(*, prompt: str, provider: DecisionProvider | None, openai_model: str) -> dict[str, Any]:
    decision = provider(prompt) if provider is not None else request_openai_decision(prompt=prompt, model=openai_model)
    if isinstance(decision, LlmDecision):
        return {"action": decision.action.value, **decision.payload}
    return decision


def _validate_turn_focus(
    *,
    turn: ScriptedTurn,
    raw_decision: dict[str, Any],
    validation: dict[str, object],
) -> dict[str, object]:
    actor_agent_id = raw_decision.get("actor_agent_id")
    if actor_agent_id != turn.actor_agent_id:
        return {
            "valid": False,
            "action": validation.get("action"),
            "error": {
                "type": "FocusMismatch",
                "message": f"decision actor_agent_id must be {turn.actor_agent_id}",
                "expected_actor_agent_id": turn.actor_agent_id,
                "actual_actor_agent_id": actor_agent_id,
            },
        }

    if validation.get("action") == LlmDecisionAction.DEFER.value:
        return validation

    negotiation_id = raw_decision.get("negotiation_id")
    if negotiation_id != turn.negotiation_id:
        return {
            "valid": False,
            "action": validation.get("action"),
            "error": {
                "type": "FocusMismatch",
                "message": f"decision negotiation_id must be {turn.negotiation_id}",
                "expected_negotiation_id": turn.negotiation_id,
                "actual_negotiation_id": negotiation_id,
            },
        }
    return validation


def _reset_sqlite_database(db_url: str) -> None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite"):
        raise ValueError("--reset-db is only supported for sqlite database URLs")
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


def _prompt_for_turn(*, db_url: str, turn: ScriptedTurn) -> str:
    context_package = build_existing_agent_context_package(
        db_url=db_url,
        observing_agent_id=turn.actor_agent_id,
        negotiation_id=turn.negotiation_id,
        max_active_negotiations=1000,
        recent_event_limit=30,
        experiment_instructions=(
            "You are one agent in a scaled market experiment. Choose exactly one protocol-valid action. "
            f"For this turn, act as {turn.actor_agent_id} with primary focus on negotiation "
            f"{turn.negotiation_id}. Prefer send_message, propose_match, accept_match, close_negotiation, "
            "or defer only when that action is valid for the current negotiation state. Do not claim the platform "
            "has determined a correct market outcome; explain fit signals only through protocol fields."
        ),
    )
    return str(context_package["prompt"])


def _validate_decision(decision: dict[str, Any]) -> dict[str, object]:
    try:
        parsed = parse_llm_decision(decision)
    except Exception as exc:
        return {"valid": False, "error": {"type": type(exc).__name__, "message": str(exc)}}
    return {"valid": True, "action": parsed.action.value}


def _event_count(db_url: str, negotiation_id: str) -> int:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        return len(SqlProtocolEventRepository(connection).list_for_negotiation(negotiation_id))


def _scripted_turns() -> list[ScriptedTurn]:
    return [
        ScriptedTurn(
            round_number=1,
            actor_agent_id="client_agent_1",
            negotiation_id="negotiation_client1_principal1",
            decision={
                "action": "send_message",
                "negotiation_id": "negotiation_client1_principal1",
                "actor_agent_id": "client_agent_1",
                "body": "Client 1 has strong backend experience and can start in two weeks.",
            },
            rationale="Client agent shares initial fit evidence.",
        ),
        ScriptedTurn(
            round_number=1,
            actor_agent_id="principal_agent_1",
            negotiation_id="negotiation_client1_principal1",
            decision={
                "action": "propose_match",
                "negotiation_id": "negotiation_client1_principal1",
                "actor_agent_id": "principal_agent_1",
                "proposal": {
                    "summary": "Client 1 for Principal 1 backend need",
                    "details": "Backend experience and availability appear aligned.",
                },
            },
            rationale="Principal agent proposes after visible fit evidence.",
        ),
        ScriptedTurn(
            round_number=1,
            actor_agent_id="client_agent_1",
            negotiation_id="negotiation_client1_principal1",
            decision={
                "action": "accept_match",
                "negotiation_id": "negotiation_client1_principal1",
                "actor_agent_id": "client_agent_1",
            },
            rationale="Client agent accepts proposed match.",
        ),
        ScriptedTurn(
            round_number=1,
            actor_agent_id="client_agent_1",
            negotiation_id="negotiation_client1_principal2",
            decision={
                "action": "close_negotiation",
                "negotiation_id": "negotiation_client1_principal2",
                "actor_agent_id": "client_agent_1",
                "reason": "Prioritized matched opportunity with principal_agent_1.",
            },
            rationale="Client agent closes competing negotiation after match.",
        ),
        ScriptedTurn(
            round_number=1,
            actor_agent_id="client_agent_2",
            negotiation_id="negotiation_client2_principal1",
            decision={
                "action": "send_message",
                "negotiation_id": "negotiation_client2_principal1",
                "actor_agent_id": "client_agent_2",
                "body": "Client 2 remains interested and can share data engineering work samples.",
            },
            rationale="Second client agent continues open negotiation.",
        ),
    ]


def _market_turns(*, negotiation_ids: tuple[str, ...], rounds: int) -> list[ScriptedTurn]:
    if rounds < 1:
        raise ValueError("rounds must be at least 1")

    turns: list[ScriptedTurn] = []
    for round_number in range(1, rounds + 1):
        for sequence, negotiation_id in enumerate(negotiation_ids, start=1):
            client_index, principal_index = _market_negotiation_indexes(negotiation_id)
            client_agent_id = f"client_agent_{client_index}"
            principal_agent_id = f"principal_agent_{principal_index}"
            actor_agent_id = client_agent_id if round_number % 2 == 1 else principal_agent_id

            if round_number == rounds and sequence <= max(1, len(negotiation_ids) // 4):
                turns.append(
                    ScriptedTurn(
                        round_number=round_number,
                        actor_agent_id=principal_agent_id,
                        negotiation_id=negotiation_id,
                        decision={
                            "action": "propose_match",
                            "negotiation_id": negotiation_id,
                            "actor_agent_id": principal_agent_id,
                            "proposal": {
                                "summary": f"Market proposal for client {client_index} and principal {principal_index}",
                                "details": "Scripted market policy proposes top-quartile observed opportunities.",
                            },
                        },
                        rationale="Final-round market policy proposes matches for an observable top slice.",
                    )
                )
                continue

            if round_number > 6:
                turns.append(
                    ScriptedTurn(
                        round_number=round_number,
                        actor_agent_id=actor_agent_id,
                        negotiation_id=negotiation_id,
                        decision={
                            "action": "defer",
                            "actor_agent_id": actor_agent_id,
                            "reason": "Scripted market policy exhausted the free-form message budget for this actor.",
                        },
                        rationale="Scripted market policy defers after the per-actor message budget is exhausted.",
                    )
                )
                continue

            turns.append(
                ScriptedTurn(
                    round_number=round_number,
                    actor_agent_id=actor_agent_id,
                    negotiation_id=negotiation_id,
                    decision={
                        "action": "send_message",
                        "negotiation_id": negotiation_id,
                        "actor_agent_id": actor_agent_id,
                        "body": _market_message_body(
                            round_number=round_number,
                            client_index=client_index,
                            principal_index=principal_index,
                            actor_agent_id=actor_agent_id,
                        ),
                    },
                    rationale="Round-robin scripted policy shares market fit signals without central scoring.",
                )
            )
    return turns


def _market_negotiation_indexes(negotiation_id: str) -> tuple[int, int]:
    prefix = "negotiation_client"
    middle = "_principal"
    if not negotiation_id.startswith(prefix) or middle not in negotiation_id:
        raise ValueError(f"unsupported market negotiation id: {negotiation_id}")
    client_part, principal_part = negotiation_id[len(prefix) :].split(middle, 1)
    return int(client_part), int(principal_part)


def _market_message_body(*, round_number: int, client_index: int, principal_index: int, actor_agent_id: str) -> str:
    if actor_agent_id.startswith("client_agent_"):
        return (
            f"Round {round_number}: client {client_index} reports availability, role fit, "
            f"and interest in principal {principal_index}."
        )
    return (
        f"Round {round_number}: principal {principal_index} reports demand, constraints, "
        f"and follow-up questions for client {client_index}."
    )


def _summary(
    *,
    scenario_name: str,
    db_url: str,
    transcript: list[dict[str, object]],
    output_dir: Path,
    scenario_config: dict[str, object],
    decision_source: str,
    reset_db: bool,
    initial_snapshot: dict[str, object],
    final_snapshot: dict[str, object],
) -> dict[str, object]:
    raw_actions = [
        record["raw_decision"].get("action")
        for record in transcript
        if isinstance(record.get("raw_decision"), dict)
    ]
    executed_actions = [
        record["execution"].get("action")
        for record in transcript
        if isinstance(record.get("execution"), dict)
    ]
    invalid_attempts = [record for record in transcript if not record["validation"]["valid"] or record["error"] is not None]
    focus_mismatch_attempts = [
        record
        for record in transcript
        if record.get("validation", {}).get("error", {}).get("type") == "FocusMismatch"
    ]
    return {
        "scenario": scenario_name,
        "decision_source": decision_source,
        "reset_db": reset_db,
        "scenario_config": scenario_config,
        "db_url": db_url,
        "turns_executed": len(transcript),
        "rounds_observed": len({record["round"] for record in transcript}),
        "metrics": {
            "messages_sent": executed_actions.count("send_message"),
            "match_proposals": executed_actions.count("propose_match"),
            "matches_accepted": executed_actions.count("accept_match"),
            "negotiations_closed": executed_actions.count("close_negotiation"),
            "deferrals": executed_actions.count("defer"),
            "invalid_attempts": len(invalid_attempts),
            "focus_mismatch_attempts": len(focus_mismatch_attempts),
            "raw_decisions_by_action": _counts(raw_actions),
            "executed_decisions_by_action": _counts(executed_actions),
            "event_deltas_by_type": _counts(
                event.get("type")
                for record in transcript
                for event in record.get("event_delta", [])
                if isinstance(event, dict)
            ),
            "initial_negotiation_states": _negotiation_state_counts(initial_snapshot),
            "final_negotiation_states": _negotiation_state_counts(final_snapshot),
        },
        "outputs": {
            "initial_graph": str(output_dir / "initial_graph.mmd"),
            "final_graph": str(output_dir / "final_graph.mmd"),
            "initial_graph_json": str(output_dir / "initial_graph.json"),
            "final_graph_json": str(output_dir / "final_graph.json"),
            "graph_events": str(output_dir / "graph_events.jsonl"),
            "transcript": str(output_dir / "transcript.jsonl"),
            "summary": str(output_dir / "summary.json"),
        },
    }


def _graph_snapshot(db_url: str, *, index: int, after: bool) -> dict[str, object]:
    timestamp = datetime(2026, 1, 8, 12, 5, tzinfo=timezone.utc) + timedelta(minutes=index - 1, seconds=1 if after else 0)
    return graph_snapshot_for_db(db_url, generated_at=timestamp)


def _counts(values: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _negotiation_state_counts(snapshot: dict[str, object]) -> dict[str, int]:
    states = []
    for edge in snapshot.get("edges", []):
        if not isinstance(edge, dict) or edge.get("kind") != "negotiation":
            continue
        states.append(edge.get("state"))
    return _counts(states)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic scaled experiment scaffold.")
    parser.add_argument("--scenario", default="two-client-two-principal")
    parser.add_argument("--turns", type=int)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--clients", type=int, default=20)
    parser.add_argument("--principals", type=int, default=10)
    parser.add_argument("--negotiations-per-client", type=int, default=2)
    parser.add_argument("--decision-source", choices=["scripted", "openai"], default="scripted")
    parser.add_argument("--openai-model", default="gpt-4o-mini")
    parser.add_argument("--reset-db", action="store_true", help="Delete an existing sqlite DB file before seeding.")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    print(
        json.dumps(
            run_scaled_experiment(
                db_url=args.db_url,
                output_dir=args.output_dir,
                scenario_name=args.scenario,
                turns=args.turns,
                rounds=args.rounds,
                client_count=args.clients,
                principal_count=args.principals,
                negotiations_per_client=args.negotiations_per_client,
                decision_source=args.decision_source,
                openai_model=args.openai_model,
                reset_db=args.reset_db,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
