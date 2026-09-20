from __future__ import annotations

from collections.abc import Iterable


def render_graph_snapshot_mermaid(snapshot: dict[str, object]) -> str:
    """Render a graph snapshot as a Mermaid flowchart.

    Protects INV-H-005 by rendering the read-only snapshot shape rather than
    querying storage or mutating graph state.
    """
    nodes = _records(snapshot.get("nodes"))
    edges = _records(snapshot.get("edges"))
    lines = ["flowchart LR"]

    for node in nodes:
        lines.append(f"  {_mermaid_id(str(node['id']))}[\"{_escape_label(str(node['label']))}\"]")

    if nodes and edges:
        lines.append("")

    for edge in edges:
        source = _mermaid_id(str(edge["source"]))
        target = _mermaid_id(str(edge["target"]))
        label = _escape_label(str(edge["label"]))
        connector = _connector_for_kind(str(edge["kind"]))
        lines.append(f"  {source} {connector}|\"{label}\"| {target}")

    return "\n".join(lines) + "\n"


def _records(value: object) -> list[dict[str, object]]:
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        return []
    return [item for item in value if isinstance(item, dict)]


def _connector_for_kind(kind: str) -> str:
    if kind == "representation":
        return "-.->"
    if kind == "negotiation":
        return "==>"
    return "-->"


def _mermaid_id(value: str) -> str:
    sanitized = "".join(character if character.isalnum() else "_" for character in value)
    if not sanitized or sanitized[0].isdigit():
        return f"node_{sanitized}"
    return sanitized


def _escape_label(value: str) -> str:
    return value.replace('"', "'")
