from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


StrategyRole = Literal["client", "principal"]


@dataclass(frozen=True)
class AgentStrategy:
    id: str
    role: StrategyRole
    name: str
    represented_party_goal: str
    priority_order: tuple[str, ...]
    expected_behaviors: tuple[str, ...]
    failure_modes: tuple[str, ...]

    def to_prompt_record(self) -> dict[str, object]:
        return {
            "id": self.id,
            "role": self.role,
            "name": self.name,
            "represented_party_goal": self.represented_party_goal,
            "priority_order": list(self.priority_order),
            "expected_behaviors": list(self.expected_behaviors),
            "failure_modes": list(self.failure_modes),
        }


_STRATEGIES: tuple[AgentStrategy, ...] = (
    AgentStrategy(
        id="CLIENT-FAST-ANY",
        role="client",
        name="Fast Placement",
        represented_party_goal="Get any acceptable job as quickly as possible.",
        priority_order=(
            "Keep negotiations moving toward a concrete offer or match.",
            "Accept broad role fit if no hard blocker is visible.",
            "Avoid long evidence-gathering loops.",
            "Close or defer low-signal negotiations only when another path is clearly faster.",
        ),
        expected_behaviors=(
            "Accept plausible inbound negotiation requests quickly.",
            "Send concise availability and willingness messages.",
            "Propose or accept matches with minimal additional proof.",
            "Tolerate adjacent fields, lower prestige, and imperfect fit if the opportunity is actionable.",
        ),
        failure_modes=(
            "Accepts obviously incompatible roles.",
            "Ignores compensation or location blockers that are explicit in context.",
            "Proposes match before the counterpart has shown any real opportunity.",
        ),
    ),
    AgentStrategy(
        id="CLIENT-INCOME-FIELD",
        role="client",
        name="Maximize Income In Target Field",
        represented_party_goal="Maximize compensation within a target field, even if placement takes longer.",
        priority_order=(
            "Stay inside the client's target field.",
            "Seek compensation, seniority, and growth signals.",
            "Ask for role details before committing.",
            "Prefer deferring or continuing promising negotiations over fast but weak matches.",
        ),
        expected_behaviors=(
            "Ask about compensation bands, seniority, scope, and field alignment.",
            "Resist low-compensation or off-field proposals.",
            "Close negotiations that cannot satisfy the target field.",
            "Accept slower progress when upside is higher.",
        ),
        failure_modes=(
            "Stalls indefinitely without using close or defer.",
            "Over-optimizes compensation when a strong target-field match is available.",
            "Treats every missing compensation detail as a rejection rather than a question.",
        ),
    ),
    AgentStrategy(
        id="CLIENT-ADJACENT-PIVOT",
        role="client",
        name="Enter Target Field From Adjacent Experience",
        represented_party_goal="Get into a target field despite adjacent, non-identical experience.",
        priority_order=(
            "Emphasize transferable skills and proof of ability.",
            "Seek counterpart openness to adjacent backgrounds.",
            "Offer evidence, work samples, or trial signals.",
            "Avoid roles that trap the client in the old field unless they create a bridge.",
        ),
        expected_behaviors=(
            "Send messages explaining transferable experience.",
            "Ask whether adjacent skills are acceptable.",
            "Propose evidence-based next steps before final match.",
            "Prefer principals that value demonstrated ability over exact credentials.",
        ),
        failure_modes=(
            "Hides the experience mismatch.",
            "Accepts old-field roles inconsistent with the pivot goal.",
            "Fails to provide evidence when counterpart asks for proof.",
        ),
    ),
    AgentStrategy(
        id="PRINCIPAL-CREDENTIAL-MAX",
        role="principal",
        name="Most Credentialed Candidate, Cost Conscious",
        represented_party_goal="Find the strongest credentialed candidate while preserving negotiation leverage on compensation.",
        priority_order=(
            "Verify credentials and relevant seniority.",
            "Compare candidate strength before accepting.",
            "Avoid premature match acceptance without proof.",
            "Signal compensation constraints without making them the only criterion.",
        ),
        expected_behaviors=(
            "Ask for credentials, prior roles, education, certifications, or seniority evidence.",
            "Propose matches only after strong credential signals.",
            "Close weak or under-evidenced candidates.",
            "Negotiate cautiously rather than accepting fast.",
        ),
        failure_modes=(
            "Overweights credentials despite poor role fit.",
            "Never advances to match after receiving enough proof.",
            "Behaves like a central ranker rather than a representative of one principal.",
        ),
    ),
    AgentStrategy(
        id="PRINCIPAL-FAST-MINIMUMS",
        role="principal",
        name="Fill Quickly Subject To Hard Minimums",
        represented_party_goal="Fill the role quickly once hard requirements are met.",
        priority_order=(
            "Check hard blockers: must-have skills, location, availability, authorization, or credential minimums.",
            "If minimums are met, move toward match quickly.",
            "Avoid exhaustive comparison shopping.",
            "Close candidates who fail explicit minimums.",
        ),
        expected_behaviors=(
            "Ask only enough questions to validate hard requirements.",
            "Propose matches quickly when requirements are satisfied.",
            "Reject or close clear misses.",
            "Tolerate non-ideal but sufficient candidates.",
        ),
        failure_modes=(
            "Treats preferences as hard requirements.",
            "Proposes before checking stated minimums.",
            "Keeps too many negotiations open despite a sufficient candidate.",
        ),
    ),
    AgentStrategy(
        id="PRINCIPAL-EVIDENCE-ADJACENT",
        role="principal",
        name="Evidence-Based Openness To Adjacent Skills",
        represented_party_goal="Fill the role with someone who can perform, including adjacent-skill candidates with strong evidence.",
        priority_order=(
            "Ask for proof of ability relevant to the actual work.",
            "Accept adjacent backgrounds when evidence is strong.",
            "Prefer practical demonstrations over credential matching alone.",
            "Close negotiations with weak evidence or unclear work relevance.",
        ),
        expected_behaviors=(
            "Ask for projects, work samples, references, trial plans, or concrete examples.",
            "Keep promising adjacent candidates open longer than credential-max agents would.",
            "Propose matches after evidence supports ability.",
            "Distinguish lack of credentials from lack of evidence.",
        ),
        failure_modes=(
            "Accepts unsupported claims of ability.",
            "Ignores explicit hard constraints.",
            "Requests evidence repeatedly after sufficient proof has been supplied.",
        ),
    ),
)


def list_strategies() -> tuple[AgentStrategy, ...]:
    return _STRATEGIES


def get_strategy(strategy_id: str) -> AgentStrategy:
    for strategy in _STRATEGIES:
        if strategy.id == strategy_id:
            return strategy
    raise KeyError(f"unknown strategy: {strategy_id}")
