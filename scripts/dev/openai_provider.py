from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable
from typing import Any

from net_working_platform.application.llm_decisions import LlmDecision, parse_llm_decision


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

OPENAI_EXECUTABLE_DECISION_JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "actor_agent_id", "negotiation_id", "reason", "body", "proposal"],
    "properties": {
        "action": {
            "type": "string",
            "enum": [
                "accept_negotiation",
                "reject_negotiation",
                "send_message",
                "propose_match",
                "accept_match",
                "close_negotiation",
                "defer",
            ],
        },
        "actor_agent_id": {"type": "string"},
        "negotiation_id": {"type": "string"},
        "reason": {"type": "string"},
        "body": {"type": "string"},
        "proposal": {
            "type": "object",
            "additionalProperties": False,
            "required": ["summary", "details"],
            "properties": {
                "summary": {"type": "string"},
                "details": {"type": "string"},
            },
        },
    },
}


def request_openai_decision(
    *,
    prompt: str,
    api_key: str | None = None,
    model: str = "gpt-4o-mini",
    opener: Callable[[urllib.request.Request, int], object] = urllib.request.urlopen,
    timeout: int = 120,
) -> LlmDecision:
    """Request one schema-constrained LLM decision from OpenAI.

    This is a dev-only adapter. It reads credentials from `OPENAI_API_KEY` when
    an explicit `api_key` is not provided and parses the returned JSON text
    through the local LLM decision validator before returning.
    """
    resolved_api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not resolved_api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI decision requests")

    payload = {
        "model": model,
        "input": prompt,
        "max_output_tokens": 500,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "llm_decision",
                "schema": OPENAI_EXECUTABLE_DECISION_JSON_SCHEMA,
                "strict": True,
            }
        },
    }
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {resolved_api_key}",
            "Content-Type": "application/json",
        },
    )

    with opener(request, timeout=timeout) as response:
        response_payload = json.loads(response.read().decode("utf-8"))

    return parse_llm_decision(_to_contract_decision(json.loads(_extract_output_text(response_payload))))


def _extract_output_text(response_payload: dict[str, Any]) -> str:
    text_parts: list[str] = []
    for item in response_payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text_parts.append(content.get("text", ""))
    return "".join(text_parts).strip()


def _to_contract_decision(value: dict[str, Any]) -> dict[str, Any]:
    action = value.get("action")
    if action == "accept_negotiation":
        return {
            "action": value["action"],
            "negotiation_id": value["negotiation_id"],
            "actor_agent_id": value["actor_agent_id"],
        }
    if action == "reject_negotiation":
        return {
            "action": value["action"],
            "negotiation_id": value["negotiation_id"],
            "actor_agent_id": value["actor_agent_id"],
            "reason": value["reason"],
        }
    if action == "send_message":
        return {
            "action": value["action"],
            "negotiation_id": value["negotiation_id"],
            "actor_agent_id": value["actor_agent_id"],
            "body": value["body"],
        }
    if action == "propose_match":
        return {
            "action": value["action"],
            "negotiation_id": value["negotiation_id"],
            "actor_agent_id": value["actor_agent_id"],
            "proposal": value["proposal"],
        }
    if action == "accept_match":
        return {
            "action": value["action"],
            "negotiation_id": value["negotiation_id"],
            "actor_agent_id": value["actor_agent_id"],
        }
    if action == "close_negotiation":
        return {
            "action": value["action"],
            "negotiation_id": value["negotiation_id"],
            "actor_agent_id": value["actor_agent_id"],
            "reason": value["reason"],
        }
    if action == "defer":
        return {
            "action": value["action"],
            "actor_agent_id": value["actor_agent_id"],
            "reason": value["reason"],
        }
    return value
