"""Graph construction.

This module builds the LangGraph workflow with all nodes and routing logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver

from langgraph.graph import END, START, StateGraph

from .nodes import (
    answer_node,
    approval_node,
    ask_clarification_node,
    classify_node,
    dead_letter_node,
    evaluate_node,
    finalize_node,
    intake_node,
    retry_or_fallback_node,
    risky_action_node,
    tool_node,
)
from .routing import (
    route_after_approval,
    route_after_classify,
    route_after_evaluate,
    route_after_retry,
)
from .state import AgentState


def build_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> StateGraph:
    """Build and compile the LangGraph workflow.

    Architecture:
    START -> intake -> classify -> [conditional: route_after_classify]
      simple       -> answer -> finalize -> END
      tool         -> tool -> evaluate -> [conditional: route_after_evaluate]
                                          success -> answer -> finalize -> END
                                          needs_retry -> retry -> [conditional]
                                                  bounded -> tool (retry)
                                                  exhausted -> dead_letter -> finalize -> END
      missing_info -> clarify -> finalize -> END
      risky        -> risky_action -> approval -> [conditional: route_after_approval]
                                                  approved -> tool -> ...
                                                  rejected -> clarify -> finalize -> END
      error        -> retry -> [conditional] -> ...

    Routing functions return the NEXT NODE NAME directly.
    """
    # Create the graph
    builder = StateGraph(AgentState)

    # ─── Add all nodes ───────────────────────────────────────────────
    builder.add_node("intake", intake_node)
    builder.add_node("classify", classify_node)
    builder.add_node("tool", tool_node)
    builder.add_node("evaluate", evaluate_node)
    builder.add_node("answer", answer_node)
    builder.add_node("clarify", ask_clarification_node)
    builder.add_node("risky_action", risky_action_node)
    builder.add_node("approval", approval_node)
    builder.add_node("retry", retry_or_fallback_node)
    builder.add_node("dead_letter", dead_letter_node)
    builder.add_node("finalize", finalize_node)

    # ─── Fixed edges ─────────────────────────────────────────────────
    # Start -> intake
    builder.add_edge(START, "intake")

    # intake -> classify
    builder.add_edge("intake", "classify")

    # ─── Conditional edges ────────────────────────────────────────────
    # classify: routing function returns next node name directly
    builder.add_conditional_edges(
        source="classify",
        path=route_after_classify,
    )

    # tool -> evaluate (fixed edge)
    builder.add_edge("tool", "evaluate")

    # evaluate: routing function returns next node name directly
    builder.add_conditional_edges(
        source="evaluate",
        path=route_after_evaluate,
    )

    # retry: routing function returns next node name directly
    builder.add_conditional_edges(
        source="retry",
        path=route_after_retry,
    )

    # risky_action -> approval (fixed edge)
    builder.add_edge("risky_action", "approval")

    # approval: routing function returns next node name directly
    builder.add_conditional_edges(
        source="approval",
        path=route_after_approval,
    )

    # ─── Fixed edges to finalize ──────────────────────────────────────
    builder.add_edge("answer", "finalize")
    builder.add_edge("clarify", "finalize")
    builder.add_edge("dead_letter", "finalize")

    # finalize -> END
    builder.add_edge("finalize", END)

    # ─── Compile the graph ───────────────────────────────────────────
    graph = builder.compile(checkpointer=checkpointer)

    return graph
