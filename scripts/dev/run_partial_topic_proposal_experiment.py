from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url

from net_working_platform.experiments.scenarios import (
    MultiPartyContactScenario,
    seed_ambiguous_multi_party_contact_scenario,
    seed_bad_fit_multi_party_contact_scenario,
    seed_multi_party_contact_scenario,
)
from net_working_platform.storage.schema import negotiations, protocol_events
from net_working_platform.storage.services import create_sql_negotiation_service
from scripts.dev.run_unified_agent_lifecycle_experiment import _jsonable, _request_openai_json

DecisionProvider = Callable[[dict[str, object], str], dict[str, Any]]


def run_partial_topic_proposal_experiment(
    *,
    db_url: str,
    output_dir: Path,
    baseline_model: str = "gpt-4o-mini",
    reset_db: bool = False,
    scenario_kind: str = "ambiguous",
    decision_provider: DecisionProvider | None = None,
) -> dict[str, object]:
    """Run candidate-only proposal, then responder fill-or-reject."""
    output_dir.mkdir(parents=True, exist_ok=True)
    if reset_db:
        _reset_sqlite_database(db_url)
    scenario = _seed_scenario(db_url, scenario_kind)

    proposal_context = _proposal_context(scenario)
    proposal = decision_provider(proposal_context, "proposal") if decision_provider else _request_openai_json(
        prompt=_proposal_prompt(proposal_context),
        model=baseline_model,
        json_schema=_proposal_schema(scenario),
    )
    client_topic_id = _validate_proposal(scenario, proposal)

    response_context = _response_context(scenario, client_topic_id, str(proposal["reason"]))
    response = decision_provider(response_context, "response") if decision_provider else _request_openai_json(
        prompt=_response_prompt(response_context),
        model=baseline_model,
        json_schema=_response_schema(scenario),
    )
    execution = _execute_response(db_url, scenario, client_topic_id, response, proposal_reason=str(proposal["reason"]))
    summary = _summary(db_url, output_dir, scenario, proposal_context, proposal, response_context, response, execution, baseline_model, reset_db, scenario_kind)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def _proposal_context(scenario: MultiPartyContactScenario) -> dict[str, object]:
    return {
        "mode": "partial_topic_proposal",
        "scenario_id": scenario.scenario_id,
        "actor_agent_id": scenario.client_agent_id,
        "contact_agent_id": scenario.principal_agent_id,
        "known_own_client_topics": list(scenario.client_summaries.values()),
        "known_contact_summary": "Contact represents principal topics, but proposer should choose only its own candidate topic.",
        "instruction": "Choose exactly one of your client topics to propose to this contact.",
    }


def _response_context(scenario: MultiPartyContactScenario, client_topic_id: str, proposal_reason: str) -> dict[str, object]:
    return {
        "mode": "partial_topic_response",
        "scenario_id": scenario.scenario_id,
        "actor_agent_id": scenario.principal_agent_id,
        "requesting_agent_id": scenario.client_agent_id,
        "proposed_client_topic": scenario.client_summaries[client_topic_id],
        "proposal_reason": proposal_reason,
        "own_principal_topics": list(scenario.principal_summaries.values()),
        "instruction": "Accept by selecting exactly one principal topic if one is appropriate, otherwise reject.",
    }


def _proposal_schema(scenario: MultiPartyContactScenario) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "actor_agent_id", "target_agent_id", "client_topic_id", "reason"],
        "properties": {
            "action": {"type": "string", "enum": ["propose_client_topic"]},
            "actor_agent_id": {"type": "string", "enum": [scenario.client_agent_id]},
            "target_agent_id": {"type": "string", "enum": [scenario.principal_agent_id]},
            "client_topic_id": {"type": "string", "enum": sorted(scenario.client_ids)},
            "reason": {"type": "string"},
        },
    }


def _response_schema(scenario: MultiPartyContactScenario) -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["action", "actor_agent_id", "requesting_agent_id", "principal_topic_id", "reason"],
        "properties": {
            "action": {"type": "string", "enum": ["accept_with_principal_topic", "reject_client_topic"]},
            "actor_agent_id": {"type": "string", "enum": [scenario.principal_agent_id]},
            "requesting_agent_id": {"type": "string", "enum": [scenario.client_agent_id]},
            "principal_topic_id": {"type": "string", "enum": sorted(scenario.principal_ids) + [""]},
            "reason": {"type": "string"},
        },
    }


def _proposal_prompt(context: dict[str, object]) -> str:
    return "\n".join([
        "You are a client-side portfolio agent in networking mode.",
        "You do not know enough to choose the contact's principal topic. Propose exactly one of your client topics.",
        json.dumps(context, sort_keys=True),
    ])


def _response_prompt(context: dict[str, object]) -> str:
    return "\n".join([
        "You are a principal-side portfolio agent responding to a proposed client topic.",
        "If one of your principal topics is appropriate, accept with that principal topic. Otherwise reject.",
        json.dumps(context, sort_keys=True),
    ])


def _validate_proposal(scenario: MultiPartyContactScenario, proposal: dict[str, Any]) -> str:
    if proposal.get("action") != "propose_client_topic":
        raise ValueError("proposal must use propose_client_topic")
    if proposal.get("actor_agent_id") != scenario.client_agent_id or proposal.get("target_agent_id") != scenario.principal_agent_id:
        raise ValueError("proposal selected agents outside the scenario")
    client_topic_id = str(proposal["client_topic_id"])
    if client_topic_id not in scenario.client_ids:
        raise ValueError("proposal selected a client topic not represented by the actor")
    return client_topic_id


def _execute_response(
    db_url: str,
    scenario: MultiPartyContactScenario,
    client_topic_id: str,
    response: dict[str, Any],
    *,
    proposal_reason: str,
) -> dict[str, object]:
    if response.get("actor_agent_id") != scenario.principal_agent_id or response.get("requesting_agent_id") != scenario.client_agent_id:
        raise ValueError("response selected agents outside the scenario")
    action = response.get("action")
    if action == "reject_client_topic":
        if response.get("principal_topic_id") not in ["", None]:
            raise ValueError("reject_client_topic must not select a principal topic")
        return {"accepted": False, "reason": str(response["reason"])}
    if action != "accept_with_principal_topic":
        raise ValueError("unsupported response action")
    principal_topic_id = str(response["principal_topic_id"])
    if principal_topic_id not in scenario.principal_ids:
        raise ValueError("accepted response selected a principal topic not represented by responder")
    subject = {
        "topic_type": "client_topic_filled_by_responder",
        "client_id": client_topic_id,
        "principal_id": principal_topic_id,
        "client_topic": scenario.client_summaries[client_topic_id],
        "principal_topic": scenario.principal_summaries[principal_topic_id],
        "proposal_reason": proposal_reason,
        "response_reason": str(response["reason"]),
    }
    engine = create_engine(db_url)
    with engine.begin() as connection:
        service = create_sql_negotiation_service(
            connection,
            new_id=lambda: f"partial_topic_negotiation_{client_topic_id}_{principal_topic_id}",
            now=lambda: datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        )
        negotiation = service.request_negotiation(
            from_agent_id=scenario.client_agent_id,
            to_agent_id=scenario.principal_agent_id,
            subject=subject,
            max_open_negotiations=5,
        )
    result = _jsonable(negotiation)
    result["accepted"] = True
    result["subject"] = subject
    return result


def _summary(
    db_url: str,
    output_dir: Path,
    scenario: MultiPartyContactScenario,
    proposal_context: dict[str, object],
    proposal: dict[str, Any],
    response_context: dict[str, object],
    response: dict[str, Any],
    execution: dict[str, object],
    baseline_model: str,
    reset_db: bool,
    scenario_kind: str,
) -> dict[str, object]:
    engine = create_engine(db_url)
    with engine.begin() as connection:
        negotiation_rows = connection.execute(select(negotiations)).all()
        event_rows = connection.execute(select(protocol_events)).all()
    subject = execution.get("subject") if isinstance(execution.get("subject"), dict) else {}
    return {
        "scenario": "partial_topic_proposal",
        "scenario_kind": scenario_kind,
        "scenario_id": scenario.scenario_id,
        "baseline_model": baseline_model,
        "reset_db": reset_db,
        "proposal_context": proposal_context,
        "raw_proposal": proposal,
        "response_context": response_context,
        "raw_response": response,
        "execution": execution,
        "metrics": {
            "accepted": execution.get("accepted") is True,
            "negotiations_requested": len(negotiation_rows),
            "open_negotiation_request_events": sum(1 for row in event_rows if row._mapping["type"] == "open_negotiation_request"),
            "selected_client_topic_id": proposal.get("client_topic_id"),
            "selected_principal_topic_id": subject.get("principal_id"),
        },
        "outputs": {"summary": str(output_dir / "summary.json")},
    }


def _seed_scenario(db_url: str, scenario_kind: str) -> MultiPartyContactScenario:
    if scenario_kind == "clear":
        return seed_multi_party_contact_scenario(db_url)
    if scenario_kind == "ambiguous":
        return seed_ambiguous_multi_party_contact_scenario(db_url)
    if scenario_kind == "bad-fit":
        return seed_bad_fit_multi_party_contact_scenario(db_url)
    raise ValueError("scenario_kind must be 'clear', 'ambiguous', or 'bad-fit'")


def _reset_sqlite_database(db_url: str) -> None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return
    database_path = Path(url.database)
    for path in [database_path, Path(f"{database_path}-wal"), Path(f"{database_path}-shm")]:
        if path.exists():
            path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run partial topic proposal/fill networking experiment.")
    parser.add_argument("--db-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--baseline-model", default="gpt-4o-mini")
    parser.add_argument("--scenario-kind", choices=["clear", "ambiguous", "bad-fit"], default="ambiguous")
    parser.add_argument("--reset-db", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(run_partial_topic_proposal_experiment(
        db_url=args.db_url,
        output_dir=args.output_dir,
        baseline_model=args.baseline_model,
        reset_db=args.reset_db,
        scenario_kind=args.scenario_kind,
    ), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
