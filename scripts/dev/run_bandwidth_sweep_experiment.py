from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from scripts.dev.run_unified_agent_lifecycle_experiment import run_unified_agent_lifecycle_experiment


def run_bandwidth_sweep_experiment(
    *,
    output_dir: Path,
    db_dir: Path,
    contact_limits: list[int],
    negotiation_limits: list[int],
    repetitions: int,
    turns: int,
    baseline_model: str = "gpt-4o-mini",
    scenario_name: str = "unified-lifecycle",
    seed_variant: str = "default",
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    db_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for contact_limit in contact_limits:
        for negotiation_limit in negotiation_limits:
            for repetition in range(1, repetitions + 1):
                run_name = f"contacts-{contact_limit}__negotiations-{negotiation_limit}__rep-{repetition}"
                run_output_dir = output_dir / run_name
                db_url = f"sqlite+pysqlite:///{db_dir / (run_name + '.db')}"
                summary = run_unified_agent_lifecycle_experiment(
                    db_url=db_url,
                    output_dir=run_output_dir,
                    turns=turns,
                    baseline_model=baseline_model,
                    reset_db=True,
                    contact_limit=contact_limit,
                    negotiation_limit=negotiation_limit,
                    scenario_name=scenario_name,
                    seed_variant=seed_variant,
                )
                runs.append(summary)
    aggregate = _aggregate_runs(runs)
    result = {
        "scenario": "bandwidth_sweep",
        "runner": "bandwidth_sweep_adapter",
        "runner_family": "adapter",
        "standard_runner": "unified-lifecycle",
        "seed_id": scenario_name,
        "seed_variant": seed_variant,
        "baseline_model": baseline_model,
        "turns": turns,
        "repetitions": repetitions,
        "contact_limits": contact_limits,
        "negotiation_limits": negotiation_limits,
        "runs": runs,
        "aggregate": aggregate,
    }
    (output_dir / "bandwidth_sweep_summary.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def _aggregate_runs(runs: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[int, int], list[dict[str, object]]] = {}
    for run in runs:
        limits = run["bandwidth_limits"]
        key = (int(limits["contact_limit"]), int(limits["negotiation_limit"]))
        grouped.setdefault(key, []).append(run)

    rows = []
    for (contact_limit, negotiation_limit), group in sorted(grouped.items()):
        rows.append(
            {
                "contact_limit": contact_limit,
                "negotiation_limit": negotiation_limit,
                "runs": len(group),
                "avg_contacts_created": _avg_metric(group, "contacts_created"),
                "avg_negotiations_created": _avg_metric(group, "negotiations_created"),
                "avg_matched": _avg_state(group, "matched"),
                "avg_closed": _avg_state(group, "closed"),
                "avg_open": _avg_state(group, "open"),
                "avg_proposal_pending": _avg_state(group, "proposal_pending"),
                "avg_requested": _avg_state(group, "requested"),
                "avg_errors": _avg_metric(group, "errors"),
            }
        )
    return rows


def _avg_metric(group: list[dict[str, object]], metric: str) -> float:
    return mean(float(run["metrics"].get(metric, 0)) for run in group)


def _avg_state(group: list[dict[str, object]], state: str) -> float:
    return mean(float(run["metrics"].get("negotiation_states", {}).get(state, 0)) for run in group)


def _parse_int_list(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a bandwidth sweep over unified lifecycle market parameters.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--db-dir", required=True, type=Path)
    parser.add_argument("--contact-limits", default="1,2,3")
    parser.add_argument("--negotiation-limits", default="1,2")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--turns", type=int, default=100)
    parser.add_argument("--baseline-model", default="gpt-4o-mini")
    parser.add_argument("--scenario", default="unified-lifecycle", choices=["unified-lifecycle", "viewer-showcase-llm"])
    parser.add_argument("--seed-variant", default="default")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            run_bandwidth_sweep_experiment(
                output_dir=args.output_dir,
                db_dir=args.db_dir,
                contact_limits=_parse_int_list(args.contact_limits),
                negotiation_limits=_parse_int_list(args.negotiation_limits),
                repetitions=args.repetitions,
                turns=args.turns,
                baseline_model=args.baseline_model,
                scenario_name=args.scenario,
                seed_variant=args.seed_variant,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
