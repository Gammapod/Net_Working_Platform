from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine

from net_working_platform.application.graph_snapshots import build_graph_snapshot
from net_working_platform.storage.graph_snapshots import SqlGraphSnapshotReader


def read_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


def graph_snapshot_for_db(db_url: str, *, generated_at: datetime) -> dict[str, object]:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        return build_graph_snapshot(SqlGraphSnapshotReader(connection), now=lambda: generated_at)


def timeline_record_from_transcript_record(
    record: dict[str, object],
    *,
    graph_delta: dict[str, object] | None = None,
    validation: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "artifact_schema_version": 1,
        "turn": record.get("turn"),
        "actor_agent_id": record.get("actor_agent_id") or record.get("scheduled_actor_agent_id"),
        "negotiation_id": record.get("negotiation_id") or _raw_decision_negotiation_id(record.get("raw_decision")),
        "raw_decision": record.get("raw_decision"),
        "validation": validation if validation is not None else record.get("validation"),
        "protocol_event_delta": record.get("event_delta", []),
        "graph_delta": graph_delta if graph_delta is not None else record.get("graph_delta", empty_graph_delta()),
    }


def empty_graph_delta() -> dict[str, object]:
    return {
        "nodes_added": [],
        "nodes_removed": [],
        "nodes_changed": [],
        "edges_added": [],
        "edges_removed": [],
        "edges_changed": [],
    }


def graph_delta(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
    before_nodes = _records_by_id(before.get("nodes", []))
    after_nodes = _records_by_id(after.get("nodes", []))
    before_edges = _records_by_id(before.get("edges", []))
    after_edges = _records_by_id(after.get("edges", []))
    return {
        "nodes_added": [after_nodes[key] for key in sorted(set(after_nodes) - set(before_nodes))],
        "nodes_removed": [before_nodes[key] for key in sorted(set(before_nodes) - set(after_nodes))],
        "nodes_changed": _changed_records(before_nodes, after_nodes),
        "edges_added": [after_edges[key] for key in sorted(set(after_edges) - set(before_edges))],
        "edges_removed": [before_edges[key] for key in sorted(set(before_edges) - set(after_edges))],
        "edges_changed": _changed_records(before_edges, after_edges),
    }


def _raw_decision_negotiation_id(raw_decision: object) -> object:
    if isinstance(raw_decision, dict):
        return raw_decision.get("negotiation_id")
    return None


def _records_by_id(value: object) -> dict[str, dict[str, object]]:
    if not isinstance(value, list):
        return {}
    records = {}
    for item in value:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            records[item["id"]] = item
    return records


def _changed_records(
    before: dict[str, dict[str, object]],
    after: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    changes = []
    for key in sorted(set(before).intersection(after)):
        if before[key] != after[key]:
            changes.append({"id": key, "before": before[key], "after": after[key]})
    return changes
