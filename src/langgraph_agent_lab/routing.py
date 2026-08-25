"""Routing functions for conditional edges.

Each function takes AgentState and returns a string — the name of the next node.
These strings MUST match node names registered in graph.py.
"""

from __future__ import annotations

from .state import AgentState


def route_after_classify(state: AgentState) -> str:
    """Map classified route to the next graph node.

    The routing function returns the NEXT NODE NAME (not the route type).
    Dict mapping in add_conditional_edges maps route -> next node.

    Returns node names: "answer", "tool", "clarify", "risky_action", "retry"
    """
    route = state.get("route", "")

    # Route name -> next node name mapping
    route_to_node = {
        "simple": "answer",
        "tool": "tool",
        "missing_info": "clarify",
        "risky": "risky_action",
        "error": "retry",
    }

    return route_to_node.get(route, "answer")


def route_after_evaluate(state: AgentState) -> str:
    """Decide if tool result is satisfactory or needs retry.

    This is the 'done?' check that creates the retry loop —
    a key LangGraph advantage over linear LCEL chains.

    Returns node names: "answer" (success) or "retry" (needs_retry)
    """
    evaluation_result = state.get("evaluation_result", "")

    if evaluation_result == "needs_retry":
        return "retry"
    return "answer"


def route_after_retry(state: AgentState) -> str:
    """Decide whether to retry the tool or give up.

    MUST be bounded — unbounded retry loops will fail grading.

    Returns node names: "tool" (retry) or "dead_letter" (give up)
    """
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)

    if attempt < max_attempts:
        return "tool"
    return "dead_letter"


def route_after_approval(state: AgentState) -> str:
    """Route based on human approval decision.

    Returns node names: "tool" (approved) or "clarify" (rejected)
    """
    approval = state.get("approval")

    if approval:
        # Handle both dict (from test) and object (from ApprovalDecision)
        if hasattr(approval, "approved"):
            if approval.approved:
                return "tool"
        elif isinstance(approval, dict) and approval.get("approved"):
            return "tool"

    return "clarify"
