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


def build_viewer_model(
    *,
    summary: dict[str, object],
    run_metadata: dict[str, object],
    seed: dict[str, object],
    initial_graph: dict[str, object],
    final_graph: dict[str, object],
    transcript: list[dict[str, object]],
    graph_events: list[dict[str, object]],
) -> dict[str, object]:
    """Build a deterministic display read-model from run artifacts.

    This is a derived viewer artifact, not a protocol source of truth.
    """
    nodes = _merge_records_by_id(initial_graph.get("nodes", []), final_graph.get("nodes", []))
    edges = _merge_records_by_id(initial_graph.get("edges", []), final_graph.get("edges", []))
    turns = [_viewer_turn(record, edges) for record in graph_events]
    return {
        "artifact_schema_version": 1,
        "kind": "net_working_platform.viewer_model",
        "source_artifacts": {
            "summary": "summary.json",
            "run": "run.json" if run_metadata else None,
            "seed": "seed.json" if seed else None,
            "transcript": "transcript.jsonl",
            "graph_events": "graph_events.jsonl",
            "initial_graph": "initial_graph.json",
            "final_graph": "final_graph.json",
        },
        "summary": summary,
        "run_metadata": run_metadata,
        "seed": {"id": seed.get("id"), "name": seed.get("name"), "schema_version": seed.get("schema_version")},
        "graph": {"initial": initial_graph, "final": final_graph, "nodes": nodes, "edges": edges},
        "turns": turns,
        "object_timelines": _object_timelines(nodes=nodes, edges=edges, turns=turns),
    }


def _viewer_turn(record: dict[str, object], edges: list[dict[str, object]]) -> dict[str, object]:
    raw_decision = record.get("raw_decision") if isinstance(record.get("raw_decision"), dict) else {}
    negotiation_id = str(record.get("negotiation_id") or raw_decision.get("negotiation_id") or "")
    subject = _negotiation_subject(edges, negotiation_id)
    return {
        "turn": record.get("turn"),
        "actor_agent_id": record.get("actor_agent_id"),
        "negotiation_id": negotiation_id or None,
        "action": raw_decision.get("action"),
        "validation": record.get("validation"),
        "topic_party_ids": sorted(_topic_party_ids(subject)),
        "protocol_signals": _protocol_signals(record, subject=subject, edges=edges),
        "graph_delta": record.get("graph_delta", empty_graph_delta()),
        "raw_record": record,
    }


def _protocol_signals(record: dict[str, object], *, subject: object, edges: list[dict[str, object]]) -> list[dict[str, object]]:
    events = record.get("protocol_event_delta", []) or record.get("event_delta", [])
    if isinstance(events, list) and events:
        return [_signal_from_event(event, edges=edges, subject=subject) for event in events if isinstance(event, dict)]
    raw_decision = record.get("raw_decision") if isinstance(record.get("raw_decision"), dict) else {}
    actor = str(raw_decision.get("actor_agent_id") or record.get("actor_agent_id") or "")
    negotiation_id = str(raw_decision.get("negotiation_id") or record.get("negotiation_id") or "")
    return [
        {
            "turn": record.get("turn"),
            "type": raw_decision.get("action") or "decision",
            "from_agent_id": actor or None,
            "to_agent_id": raw_decision.get("target_agent_id") or _counterparty(edges, negotiation_id, actor) or None,
            "negotiation_id": negotiation_id or None,
            "message": raw_decision.get("body") or raw_decision.get("reason") or _proposal_summary(raw_decision.get("proposal")),
            "topic_party_ids": sorted(_topic_party_ids(subject)),
            "payload": raw_decision,
        }
    ]


def _signal_from_event(event: dict[str, object], *, edges: list[dict[str, object]], subject: object) -> dict[str, object]:
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    negotiation_id = str(event.get("negotiation_id") or "")
    actor = str(event.get("actor_agent_id") or "")
    return {
        "type": event.get("type"),
        "from_agent_id": actor or None,
        "to_agent_id": payload.get("target_agent_id") or _counterparty(edges, negotiation_id, actor) or None,
        "negotiation_id": negotiation_id or None,
        "message": payload.get("body") or payload.get("reason") or _proposal_summary(payload.get("proposal")),
        "topic_party_ids": sorted(_topic_party_ids(subject)),
        "payload": payload,
    }


def _object_timelines(*, nodes: list[dict[str, object]], edges: list[dict[str, object]], turns: list[dict[str, object]]) -> dict[str, object]:
    node_timelines: dict[str, list[int]] = {str(node["id"]): [] for node in nodes if "id" in node}
    edge_timelines: dict[str, list[int]] = {str(edge["id"]): [] for edge in edges if "id" in edge}
    negotiation_edges = {edge.get("details", {}).get("negotiation_id"): edge.get("id") for edge in edges if edge.get("kind") == "negotiation"}
    agent_connection_edges = {(edge.get("source"), edge.get("target")): edge.get("id") for edge in edges if edge.get("kind") == "agent_connection"}
    for index, turn in enumerate(turns):
        touched_nodes = set(turn.get("topic_party_ids", []))
        for signal in turn.get("protocol_signals", []):
            if not isinstance(signal, dict):
                continue
            for key in ["from_agent_id", "to_agent_id"]:
                if signal.get(key):
                    touched_nodes.add(str(signal[key]))
            edge_id = negotiation_edges.get(signal.get("negotiation_id"))
            if edge_id:
                edge_timelines.setdefault(str(edge_id), []).append(index)
            pair_edge_id = agent_connection_edges.get((signal.get("from_agent_id"), signal.get("to_agent_id")))
            if pair_edge_id:
                edge_timelines.setdefault(str(pair_edge_id), []).append(index)
        for node_id in touched_nodes:
            node_timelines.setdefault(str(node_id), []).append(index)
    return {
        "nodes": {key: sorted(set(value)) for key, value in sorted(node_timelines.items())},
        "edges": {key: sorted(set(value)) for key, value in sorted(edge_timelines.items())},
    }


def _merge_records_by_id(*record_lists: object) -> list[dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for value in record_lists:
        if not isinstance(value, list):
            continue
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                records[item["id"]] = item
    return [records[key] for key in sorted(records)]


def _negotiation_subject(edges: list[dict[str, object]], negotiation_id: str) -> object:
    for edge in edges:
        details = edge.get("details", {}) if isinstance(edge.get("details"), dict) else {}
        if details.get("negotiation_id") == negotiation_id:
            return details.get("subject", {})
    return {}


def _topic_party_ids(value: object) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, dict):
        for key in ["client_id", "principal_id", "represented_party_id"]:
            if isinstance(value.get(key), str):
                ids.add(value[key])
        for item in value.values():
            ids.update(_topic_party_ids(item))
    elif isinstance(value, list):
        for item in value:
            ids.update(_topic_party_ids(item))
    return ids


def _counterparty(edges: list[dict[str, object]], negotiation_id: str, actor: str) -> str | None:
    for edge in edges:
        details = edge.get("details", {}) if isinstance(edge.get("details"), dict) else {}
        if details.get("negotiation_id") != negotiation_id:
            continue
        source = str(edge.get("source") or details.get("from_agent_id") or "")
        target = str(edge.get("target") or details.get("to_agent_id") or "")
        if actor == source:
            return target
        if actor == target:
            return source
        return target or source or None
    return None


def _proposal_summary(value: object) -> object:
    if isinstance(value, dict):
        return value.get("summary") or value.get("details")
    return None


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
