"""Contextual Signoff agents and their least-privilege tool plans.

The agent layer deliberately separates intent selection from tool execution. A
real model may choose the same plans later, but every call still passes through
the allowlisted tools in the API and produces an auditable trace.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AgentId = Literal[
    "delivery-analyst",
    "requirements-coach",
    "verification-planner",
    "change-radar",
    "agreement-analyst",
    "qa-explorer",
    "evidence-curator",
    "acceptance-assistant",
]


@dataclass(frozen=True)
class AgentDefinition:
    id: AgentId
    name: str
    description: str
    tools: tuple[str, ...]
    accent: str


AGENTS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        id="delivery-analyst",
        name="Delivery analyst",
        description="Explains what is blocking the active release and the next decision to make.",
        tools=("get_delivery_readiness", "list_attention_items", "summarize_delivery"),
        accent="indigo",
    ),
    AgentDefinition(
        id="requirements-coach",
        name="Requirements coach",
        description="Reviews one requirement and proposes atomic, testable acceptance criteria.",
        tools=("inspect_requirement", "analyze_requirement", "generate_acceptance_criteria"),
        accent="violet",
    ),
    AgentDefinition(
        id="verification-planner",
        name="Verification planner",
        description="Turns a requirement into a bounded verification plan with the right provider.",
        tools=("inspect_requirement", "plan_verification"),
        accent="blue",
    ),
    AgentDefinition(
        id="change-radar",
        name="Change radar",
        description="Reads the active change signals and explains which ones need human review.",
        tools=("list_attention_items", "classify_change"),
        accent="amber",
    ),
    AgentDefinition(
        id="agreement-analyst",
        name="Agreement analyst",
        description="Finds commitments, ambiguities and missing acceptance criteria in the active baseline.",
        tools=("inspect_scope", "list_requirements", "analyze_requirement"),
        accent="violet",
    ),
    AgentDefinition(
        id="qa-explorer",
        name="QA explorer",
        description="Checks the running application against selected requirements and captures observations.",
        tools=("inspect_requirement", "plan_verification", "discover_routes", "run_smoke_check"),
        accent="blue",
    ),
    AgentDefinition(
        id="evidence-curator",
        name="Evidence curator",
        description="Finds missing, stale or weak evidence in the delivery graph.",
        tools=("list_evidence", "get_delivery_readiness", "list_attention_items"),
        accent="indigo",
    ),
    AgentDefinition(
        id="acceptance-assistant",
        name="Acceptance assistant",
        description="Prepares a client-ready acceptance summary without making the decision for them.",
        tools=("get_delivery_readiness", "list_evidence", "summarize_delivery"),
        accent="amber",
    ),
)


def agent_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": agent.id,
            "name": agent.name,
            "description": agent.description,
            "tools": list(agent.tools),
            "accent": agent.accent,
        }
        for agent in AGENTS
    ]


def get_agent(agent_id: str) -> AgentDefinition:
    for agent in AGENTS:
        if agent.id == agent_id:
            return agent
    raise ValueError(f"Unknown agent: {agent_id}")


def build_plan(agent_id: AgentId, user_input: str, requirement_id: str | None = None) -> list[dict[str, Any]]:
    """Return a bounded tool plan; this is intentionally finite and inspectable."""
    agent = get_agent(agent_id)
    if agent_id == "delivery-analyst":
        return [
            {"tool": "get_delivery_readiness", "input": {}},
            {"tool": "list_attention_items", "input": {}},
            {"tool": "summarize_delivery", "input": {"question": user_input}},
        ]
    if agent_id == "requirements-coach":
        return [
            {"tool": "inspect_requirement", "input": {"requirement_id": requirement_id}},
            {"tool": "analyze_requirement", "input": {"requirement_id": requirement_id}},
            {"tool": "generate_acceptance_criteria", "input": {"requirement_id": requirement_id}},
        ]
    if agent_id == "verification-planner":
        return [
            {"tool": "inspect_requirement", "input": {"requirement_id": requirement_id}},
            {"tool": "plan_verification", "input": {"requirement_id": requirement_id}},
        ]
    if agent_id == "agreement-analyst":
        return [
            {"tool": "inspect_scope", "input": {}},
            {"tool": "list_requirements", "input": {}},
            {"tool": "analyze_requirement", "input": {"requirement_id": requirement_id}},
        ]
    if agent_id == "qa-explorer":
        return [
            {"tool": "inspect_requirement", "input": {"requirement_id": requirement_id}},
            {"tool": "plan_verification", "input": {"requirement_id": requirement_id}},
            {"tool": "discover_routes", "input": {}},
            {"tool": "run_smoke_check", "input": {"requirement_id": requirement_id}},
        ]
    if agent_id == "evidence-curator":
        return [
            {"tool": "list_evidence", "input": {}},
            {"tool": "get_delivery_readiness", "input": {}},
            {"tool": "list_attention_items", "input": {}},
        ]
    if agent_id == "acceptance-assistant":
        return [
            {"tool": "get_delivery_readiness", "input": {}},
            {"tool": "list_evidence", "input": {}},
            {"tool": "summarize_delivery", "input": {"question": user_input}},
        ]
    return [
        {"tool": "list_attention_items", "input": {}},
        {"tool": "classify_change", "input": {"request": user_input}},
    ]
