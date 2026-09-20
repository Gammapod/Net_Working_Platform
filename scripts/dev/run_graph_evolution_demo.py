from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine

from net_working_platform.application.graph_mermaid import render_graph_snapshot_mermaid
from net_working_platform.application.graph_snapshots import build_graph_snapshot
from net_working_platform.experiments.scenarios import seed_two_client_two_principal_scenario
from net_working_platform.storage.graph_snapshots import SqlGraphSnapshotReader
from net_working_platform.storage.services import create_sql_negotiation_service


def run_graph_evolution_demo(*, db_url: str, output_dir: Path) -> dict[str, object]:
    """Run a deterministic before/after graph demo over an existing seed scenario."""
    output_dir.mkdir(parents=True, exist_ok=True)
    scenario = seed_two_client_two_principal_scenario(db_url)
    engine = create_engine(db_url)

    with engine.begin() as connection:
        initial_snapshot = build_graph_snapshot(
            SqlGraphSnapshotReader(connection),
            now=lambda: datetime(2026, 1, 8, 12, 30, tzinfo=timezone.utc),
        )

        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: "unused",
            now=lambda: datetime(2026, 1, 8, 12, 45, tzinfo=timezone.utc),
        )
        service.propose_match(
            negotiation_id="negotiation_client1_principal1",
            actor_agent_id="client_agent_1",
            proposal={
                "summary": "Client 1 looks aligned with Principal 1",
                "details": "Deterministic demo proposal to show graph state evolution.",
            },
        )
        service.accept_match(
            negotiation_id="negotiation_client1_principal1",
            actor_agent_id="principal_agent_1",
        )
        service.close_negotiation(
            negotiation_id="negotiation_client1_principal2",
            actor_agent_id="client_agent_1",
            reason="Demo closure to make before/after graph visibly different.",
        )

        final_snapshot = build_graph_snapshot(
            SqlGraphSnapshotReader(connection),
            now=lambda: datetime(2026, 1, 8, 13, 0, tzinfo=timezone.utc),
        )

    initial_mermaid = render_graph_snapshot_mermaid(initial_snapshot)
    final_mermaid = render_graph_snapshot_mermaid(final_snapshot)
    summary = {
        "scenario": "two_client_two_principal",
        "db_url": db_url,
        "negotiation_ids": list(scenario.negotiation_ids),
        "rounds": [
            {
                "action": "propose_match",
                "negotiation_id": "negotiation_client1_principal1",
                "actor_agent_id": "client_agent_1",
            },
            {
                "action": "accept_match",
                "negotiation_id": "negotiation_client1_principal1",
                "actor_agent_id": "principal_agent_1",
            },
            {
                "action": "close_negotiation",
                "negotiation_id": "negotiation_client1_principal2",
                "actor_agent_id": "client_agent_1",
            },
        ],
        "outputs": {
            "initial_graph": str(output_dir / "initial_graph.mmd"),
            "final_graph": str(output_dir / "final_graph.mmd"),
            "summary": str(output_dir / "summary.json"),
        },
    }

    (output_dir / "initial_graph.mmd").write_text(initial_mermaid, encoding="utf-8")
    (output_dir / "final_graph.mmd").write_text(final_mermaid, encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate before/after graph Mermaid files for a deterministic demo.")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    print(json.dumps(run_graph_evolution_demo(db_url=args.db_url, output_dir=args.output_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
