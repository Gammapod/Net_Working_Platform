from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from net_working_platform.application.graph_mermaid import render_graph_snapshot_mermaid
from net_working_platform.application.graph_snapshots import build_graph_snapshot
from net_working_platform.application.llm_decisions import execute_llm_decision, parse_llm_decision
from net_working_platform.domain.model import (
    AgentConnection,
    AgentConnectionState,
    NegotiationDecision,
    Node,
    NodeType,
    ProtocolEvent,
    RepresentationEdge,
    RepresentationState,
)
from net_working_platform.storage.graph_snapshots import SqlGraphSnapshotReader
from net_working_platform.storage.repositories import (
    SqlAgentConnectionRepository,
    SqlNodeRepository,
    SqlProtocolEventRepository,
    SqlRepresentationEdgeRepository,
)
from net_working_platform.storage.schema import metadata
from net_working_platform.storage.services import create_sql_negotiation_service
from scripts.dev.experiment_artifacts import graph_delta, read_jsonl, timeline_record_from_transcript_record, write_jsonl
from scripts.dev.run_scaled_experiment import run_scaled_experiment


SUPPORTED_SEED_SCHEMA_VERSION = 1


def run_experiment_from_seed(
    *,
    seed_path: Path,
    output_dir: Path,
    db_url: str | None = None,
    reset_db: bool = False,
) -> dict[str, object]:
    """Run a repository-user experiment from a versioned seed file.

    Protects INV-X-001.
    """
    seed = _load_seed(seed_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_db_url = db_url or f"sqlite+pysqlite:///{output_dir / 'run.db'}"

    experiment = seed["experiment"]
    kind = experiment["kind"]
    if kind == "scaled":
        summary = _run_scaled_seed(
            experiment=experiment,
            db_url=resolved_db_url,
            output_dir=output_dir,
            reset_db=reset_db,
        )
        runner = "scripts.dev.run_scaled_experiment"
    elif kind == "editable_graph_scripted":
        summary = _run_editable_graph_scripted_seed(
            experiment=experiment,
            db_url=resolved_db_url,
            output_dir=output_dir,
            reset_db=reset_db,
        )
        runner = "scripts.dev.run_experiment.editable_graph_scripted"
    else:
        raise ValueError(f"unsupported experiment kind: {kind}")

    seed_output = output_dir / "seed.json"
    run_output = output_dir / "run.json"
    seed_output.write_text(json.dumps(seed, indent=2, sort_keys=True), encoding="utf-8")

    run_metadata = _run_metadata(
        seed=seed,
        seed_path=seed_path,
        db_url=resolved_db_url,
        output_dir=output_dir,
        reset_db=reset_db,
        runner=runner,
    )
    run_output.write_text(json.dumps(run_metadata, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        **summary,
        "artifact_schema_version": 1,
        "seed_id": seed["id"],
        "outputs": {
            **summary.get("outputs", {}),
            "run": str(run_output),
            "seed": str(seed_output),
        },
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _run_scaled_seed(
    *,
    experiment: dict[str, Any],
    db_url: str,
    output_dir: Path,
    reset_db: bool,
) -> dict[str, object]:
    scaled = experiment.get("scaled", {})
    if not isinstance(scaled, dict):
        raise ValueError("experiment.scaled must be an object")
    summary = run_scaled_experiment(
        db_url=db_url,
        output_dir=output_dir,
        scenario_name=str(scaled.get("scenario", "two-client-two-principal")),
        turns=_optional_int(scaled.get("turns")),
        rounds=int(scaled.get("rounds", 1)),
        client_count=int(scaled.get("client_count", 20)),
        principal_count=int(scaled.get("principal_count", 10)),
        negotiations_per_client=int(scaled.get("negotiations_per_client", 2)),
        decision_source=str(scaled.get("decision_source", "scripted")),
        reset_db=reset_db,
    )
    graph_events_path = output_dir / "graph_events.jsonl"
    if not graph_events_path.exists():
        transcript = read_jsonl(output_dir / "transcript.jsonl")
        graph_events = [timeline_record_from_transcript_record(record) for record in transcript]
        write_jsonl(graph_events_path, graph_events)
    return _with_graph_events_output(summary, output_dir)


def _run_editable_graph_scripted_seed(
    *,
    experiment: dict[str, Any],
    db_url: str,
    output_dir: Path,
    reset_db: bool,
) -> dict[str, object]:
    config = experiment.get("editable_graph_scripted")
    if not isinstance(config, dict):
        raise ValueError("experiment.editable_graph_scripted must be an object")
    _validate_editable_graph_config(config)
    if reset_db:
        _reset_sqlite_database(db_url)

    engine = create_engine(db_url)
    metadata.create_all(engine)
    max_open_negotiations = int(config.get("max_open_negotiations", 5))

    with engine.begin() as connection:
        _import_editable_graph_seed(connection, config, max_open_negotiations=max_open_negotiations)
        initial_snapshot = build_graph_snapshot(
            SqlGraphSnapshotReader(connection),
            now=lambda: datetime(2026, 1, 8, 12, 30, tzinfo=timezone.utc),
        )

    transcript = []
    graph_events = []
    for index, turn in enumerate(config.get("scripted_turns", []), start=1):
        turn_record, timeline_record = _execute_editable_scripted_turn(
            db_url=db_url,
            turn=turn,
            index=index,
        )
        transcript.append(turn_record)
        graph_events.append(timeline_record)

    with engine.begin() as connection:
        final_snapshot = build_graph_snapshot(
            SqlGraphSnapshotReader(connection),
            now=lambda: datetime(2026, 1, 8, 13, 0, tzinfo=timezone.utc),
        )

    _write_graph_artifacts(output_dir, initial_snapshot, final_snapshot)
    (output_dir / "transcript.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in transcript),
        encoding="utf-8",
    )
    write_jsonl(output_dir / "graph_events.jsonl", graph_events)
    summary = _editable_summary(
        db_url=db_url,
        output_dir=output_dir,
        transcript=transcript,
        reset_db=reset_db,
        initial_snapshot=initial_snapshot,
        final_snapshot=final_snapshot,
    )
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return _with_graph_events_output(summary, output_dir)


def _validate_editable_graph_config(config: dict[str, Any]) -> None:
    for key in ["nodes", "representation_edges", "agent_connections", "initial_negotiations", "scripted_turns"]:
        if not isinstance(config.get(key), list):
            raise ValueError(f"editable_graph_scripted.{key} must be a list")


def _import_editable_graph_seed(connection: object, config: dict[str, Any], *, max_open_negotiations: int) -> None:
    nodes = SqlNodeRepository(connection)
    representations = SqlRepresentationEdgeRepository(connection)
    agent_connections = SqlAgentConnectionRepository(connection)
    for record in config["nodes"]:
        nodes.add(
            Node(id=str(record["id"]), type=NodeType(str(record["type"]))),
            display_name=record.get("display_name"),
        )
    for record in config["representation_edges"]:
        representations.add(
            RepresentationEdge(
                agent_id=str(record["agent_id"]),
                represented_node_id=str(record["represented_node_id"]),
                represented_node_type=NodeType(str(record["represented_node_type"])),
                state=RepresentationState(str(record.get("state", "active"))),
            )
        )
    for record in config["agent_connections"]:
        agent_connections.add(
            AgentConnection(
                from_agent_id=str(record["from_agent_id"]),
                to_agent_id=str(record["to_agent_id"]),
                state=AgentConnectionState(str(record.get("state", "active"))),
            )
        )
    for record in config["initial_negotiations"]:
        _create_initial_negotiation(connection, record, max_open_negotiations=max_open_negotiations)


def _create_initial_negotiation(connection: object, record: dict[str, Any], *, max_open_negotiations: int) -> None:
    negotiation_id = str(record["id"])
    service = create_sql_negotiation_service(
        connection,
        new_id=lambda: negotiation_id,
        now=lambda: datetime(2026, 1, 8, 12, 0, tzinfo=timezone.utc),
    )
    negotiation = service.request_negotiation(
        from_agent_id=str(record["from_agent_id"]),
        to_agent_id=str(record["to_agent_id"]),
        subject=dict(record.get("subject", {})),
        max_open_negotiations=max_open_negotiations,
    )
    state = str(record.get("state", "requested"))
    if state == "requested":
        return
    if state == "open":
        service.respond_to_negotiation(
            negotiation_id=negotiation.id,
            actor_agent_id=str(record["to_agent_id"]),
            decision=NegotiationDecision.ACCEPT,
        )
        return
    raise ValueError("initial_negotiations currently support requested or open state")


def _execute_editable_scripted_turn(*, db_url: str, turn: dict[str, Any], index: int) -> tuple[dict[str, object], dict[str, object]]:
    raw_decision = turn.get("decision")
    if not isinstance(raw_decision, dict):
        raise ValueError("scripted turn decision must be an object")
    negotiation_id = str(raw_decision.get("negotiation_id") or turn.get("negotiation_id"))
    engine = create_engine(db_url)
    with engine.begin() as connection:
        before_events = SqlProtocolEventRepository(connection).list_for_negotiation(negotiation_id)
        before_snapshot = build_graph_snapshot(
            SqlGraphSnapshotReader(connection),
            now=lambda: datetime(2026, 1, 8, 12, 10, tzinfo=timezone.utc) + timedelta(minutes=index - 1),
        )
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: "unused",
            now=lambda: datetime(2026, 1, 8, 12, 10, tzinfo=timezone.utc) + timedelta(minutes=index - 1),
        )
        decision = parse_llm_decision(raw_decision)
        execution = execute_llm_decision(decision, service)
        after_events = SqlProtocolEventRepository(connection).list_for_negotiation(negotiation_id)
        after_snapshot = build_graph_snapshot(
            SqlGraphSnapshotReader(connection),
            now=lambda: datetime(2026, 1, 8, 12, 10, tzinfo=timezone.utc) + timedelta(minutes=index - 1, seconds=1),
        )
    turn_record = {
        "turn": index,
        "actor_agent_id": raw_decision.get("actor_agent_id"),
        "negotiation_id": negotiation_id,
        "raw_decision": raw_decision,
        "validation": {"valid": True, "action": decision.action.value},
        "execution": _jsonable(execution),
        "error": None,
        "event_delta": [_event_to_record(event) for event in after_events[len(before_events) :]],
    }
    return turn_record, timeline_record_from_transcript_record(
        turn_record,
        graph_delta=graph_delta(before_snapshot, after_snapshot),
    )


def _write_graph_artifacts(output_dir: Path, initial_snapshot: dict[str, object], final_snapshot: dict[str, object]) -> None:
    (output_dir / "initial_graph.json").write_text(json.dumps(initial_snapshot, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "final_graph.json").write_text(json.dumps(final_snapshot, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "initial_graph.mmd").write_text(render_graph_snapshot_mermaid(initial_snapshot), encoding="utf-8")
    (output_dir / "final_graph.mmd").write_text(render_graph_snapshot_mermaid(final_snapshot), encoding="utf-8")


def _editable_summary(
    *,
    db_url: str,
    output_dir: Path,
    transcript: list[dict[str, object]],
    reset_db: bool,
    initial_snapshot: dict[str, object],
    final_snapshot: dict[str, object],
) -> dict[str, object]:
    executed_actions = [record.get("execution", {}).get("action") for record in transcript if isinstance(record.get("execution"), dict)]
    return {
        "scenario": "editable_graph_scripted",
        "db_url": db_url,
        "reset_db": reset_db,
        "turns_executed": len(transcript),
        "metrics": {
            "messages_sent": executed_actions.count("send_message"),
            "match_proposals": executed_actions.count("propose_match"),
            "matches_accepted": executed_actions.count("accept_match"),
            "negotiations_closed": executed_actions.count("close_negotiation"),
            "invalid_attempts": 0,
            "initial_negotiation_states": _negotiation_state_counts(initial_snapshot),
            "final_negotiation_states": _negotiation_state_counts(final_snapshot),
            "event_deltas_by_type": _counts(
                event.get("type")
                for record in transcript
                for event in record.get("event_delta", [])
                if isinstance(event, dict)
            ),
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


def _load_seed(seed_path: Path) -> dict[str, Any]:
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    if not isinstance(seed, dict):
        raise ValueError("seed must be a JSON object")
    schema_version = seed.get("schema_version")
    if schema_version != SUPPORTED_SEED_SCHEMA_VERSION:
        raise ValueError(f"unsupported seed schema_version: {schema_version}")
    if not isinstance(seed.get("id"), str) or not seed["id"]:
        raise ValueError("seed.id must be a non-empty string")
    experiment = seed.get("experiment")
    if not isinstance(experiment, dict):
        raise ValueError("seed.experiment must be an object")
    if not isinstance(experiment.get("kind"), str):
        raise ValueError("seed.experiment.kind must be a string")
    return seed


def _with_graph_events_output(summary: dict[str, object], output_dir: Path) -> dict[str, object]:
    return {
        **summary,
        "outputs": {
            **summary.get("outputs", {}),
            "graph_events": str(output_dir / "graph_events.jsonl"),
        },
    }

def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _run_metadata(
    *,
    seed: dict[str, Any],
    seed_path: Path,
    db_url: str,
    output_dir: Path,
    reset_db: bool,
    runner: str,
) -> dict[str, object]:
    return {
        "artifact_schema_version": 1,
        "seed_id": seed["id"],
        "seed_source": str(seed_path),
        "runner": runner,
        "db_url": db_url,
        "reset_db": reset_db,
        "outputs": {
            "run": str(output_dir / "run.json"),
            "seed": str(output_dir / "seed.json"),
            "summary": str(output_dir / "summary.json"),
            "transcript": str(output_dir / "transcript.jsonl"),
            "graph_events": str(output_dir / "graph_events.jsonl"),
            "initial_graph_json": str(output_dir / "initial_graph.json"),
            "final_graph_json": str(output_dir / "final_graph.json"),
            "initial_graph_mermaid": str(output_dir / "initial_graph.mmd"),
            "final_graph_mermaid": str(output_dir / "final_graph.mmd"),
        },
    }


def _reset_sqlite_database(db_url: str) -> None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite"):
        raise ValueError("reset_db is only supported for sqlite database URLs")
    if not url.database or url.database == ":memory:":
        return
    database_path = Path(url.database)
    for path in [database_path, Path(f"{database_path}-wal"), Path(f"{database_path}-shm")]:
        if path.exists():
            path.unlink()


def _event_to_record(event: ProtocolEvent) -> dict[str, object]:
    return {
        "type": event.type.value,
        "actor_agent_id": event.actor_agent_id,
        "negotiation_id": event.negotiation_id,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": event.payload,
    }


def _jsonable(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if hasattr(value, "id") and hasattr(value, "state"):
        return {
            "id": value.id,
            "from_agent_id": value.from_agent_id,
            "to_agent_id": value.to_agent_id,
            "state": value.state.value,
            "subject": value.subject,
        }
    return value


def _negotiation_state_counts(snapshot: dict[str, object]) -> dict[str, int]:
    return _counts(
        edge.get("state")
        for edge in snapshot.get("edges", [])
        if isinstance(edge, dict) and edge.get("kind") == "negotiation"
    )


def _counts(values: object) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an experiment from a versioned seed file.")
    parser.add_argument("--seed", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--db-url")
    parser.add_argument("--reset-db", action="store_true")
    args = parser.parse_args(argv)

    print(
        json.dumps(
            run_experiment_from_seed(
                seed_path=args.seed,
                output_dir=args.output_dir,
                db_url=args.db_url,
                reset_db=args.reset_db,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
