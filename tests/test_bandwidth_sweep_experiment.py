from __future__ import annotations

from scripts.dev.run_bandwidth_sweep_experiment import _aggregate_runs


def test_bandwidth_sweep_aggregate_groups_runs_by_limits() -> None:
    runs = [
        {
            "bandwidth_limits": {"contact_limit": 1, "negotiation_limit": 1},
            "metrics": {"contacts_created": 2, "negotiations_created": 3, "errors": 0, "negotiation_states": {"matched": 1}},
        },
        {
            "bandwidth_limits": {"contact_limit": 1, "negotiation_limit": 1},
            "metrics": {"contacts_created": 4, "negotiations_created": 5, "errors": 2, "negotiation_states": {"matched": 3, "open": 1}},
        },
        {
            "bandwidth_limits": {"contact_limit": 2, "negotiation_limit": 1},
            "metrics": {"contacts_created": 6, "negotiations_created": 7, "errors": 0, "negotiation_states": {"closed": 2}},
        },
    ]

    assert _aggregate_runs(runs) == [
        {
            "contact_limit": 1,
            "negotiation_limit": 1,
            "runs": 2,
            "avg_contacts_created": 3.0,
            "avg_negotiations_created": 4.0,
            "avg_matched": 2.0,
            "avg_closed": 0.0,
            "avg_open": 0.5,
            "avg_proposal_pending": 0.0,
            "avg_requested": 0.0,
            "avg_errors": 1.0,
        },
        {
            "contact_limit": 2,
            "negotiation_limit": 1,
            "runs": 1,
            "avg_contacts_created": 6.0,
            "avg_negotiations_created": 7.0,
            "avg_matched": 0.0,
            "avg_closed": 2.0,
            "avg_open": 0.0,
            "avg_proposal_pending": 0.0,
            "avg_requested": 0.0,
            "avg_errors": 0.0,
        },
    ]
