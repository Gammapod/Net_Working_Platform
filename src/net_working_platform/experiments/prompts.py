from __future__ import annotations

import json

from net_working_platform.experiments.strategies import AgentStrategy


def build_platform_constitution_prompt() -> str:
    return """Platform constitution

You are a representative agent on Net Working Platform.
You represent a specific client or principal and must pursue that represented party's goals.

Protocol constraints:
- choose exactly one supported protocol action;
- optionally attach any currently available represented-party fact fields as disclose_fact_fields on a substantive protocol action;
- do not use fact disclosure as a standalone action;
- use only actions allowed by the current decision context;
- do not mutate state directly or invent tools;
- defer explicitly when no protocol-valid action is appropriate;
- Strategies are priorities, not permission to bypass protocol validation.

Market interpretation constraints:
- Do not invent a central platform match score;
- do not claim the platform has selected an objectively best match;
- explain fit, evidence, uncertainty, compensation, speed, or credentials only from observable context.
"""


def build_strategy_prompt_package(
    *,
    decision_context: dict[str, object],
    active_strategy: AgentStrategy,
    counterpart_strategy: AgentStrategy,
    represented_party_facts: dict[str, object],
    counterpart_facts: dict[str, object],
    scheduled_actor_agent_id: str,
    focus_negotiation_id: str,
) -> dict[str, object]:
    package = {
        "platform_constitution": build_platform_constitution_prompt(),
        "scheduled_actor_agent_id": scheduled_actor_agent_id,
        "focus_negotiation_id": focus_negotiation_id,
        "active_strategy": active_strategy.to_prompt_record(),
        "counterpart_strategy": counterpart_strategy.to_prompt_record(),
        "represented_party_facts": represented_party_facts,
        "counterpart_facts": counterpart_facts,
        "decision_context": decision_context,
    }
    package["prompt"] = _render_prompt(package)
    return package


def _render_prompt(package: dict[str, object]) -> str:
    return "\n".join(
        [
            str(package["platform_constitution"]),
            "Pairwise strategy experiment",
            f"Scheduled actor: {package['scheduled_actor_agent_id']}",
            f"Focus negotiation: {package['focus_negotiation_id']}",
            "Return exactly one JSON object matching the LLM decision contract.",
            "Strategy and state package:",
            json.dumps(
                {
                    "active_strategy": package["active_strategy"],
                    "counterpart_strategy": package["counterpart_strategy"],
                    "represented_party_facts": package["represented_party_facts"],
                    "counterpart_facts": package["counterpart_facts"],
                    "decision_context": package["decision_context"],
                },
                sort_keys=True,
            ),
        ]
    )
