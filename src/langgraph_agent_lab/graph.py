"""Graph construction.

This module is intentionally import-safe. It imports LangGraph only inside the builder so unit tests
that check schema/metrics can run even if students are still debugging graph wiring.
"""

from __future__ import annotations

from typing import Any

from .state import AgentState


def build_graph(checkpointer: Any | None = None):
    """Build and compile the LangGraph workflow.

    TODO(student): Build the complete graph with this architecture:

    START → intake → classify → [conditional: route_after_classify]
      simple       → answer → finalize → END
      tool         → tool → evaluate → [conditional: route_after_evaluate]
                                          success → answer → finalize → END
                                          needs_retry → retry → [conditional: route_after_retry]
                                                                  tool (retry)
                                                                  dead_letter → finalize → END
      missing_info → clarify → finalize → END
      risky        → risky_action → approval → [conditional: route_after_approval]
                                                  approved → tool → evaluate → ...
                                                  rejected → clarify → finalize → END
      error        → retry → [conditional: route_after_retry] → ...

    Steps:
    1. Import StateGraph, START, END from langgraph.graph
    2. Create StateGraph(AgentState)
    3. Import and add all nodes from nodes.py (11 nodes total)
    4. Import and use routing functions from routing.py for conditional edges
    5. Add fixed edges (e.g., START→intake, intake→classify, tool→evaluate, etc.)
    6. Add conditional edges using add_conditional_edges()
    7. Compile with checkpointer: graph.compile(checkpointer=checkpointer)

    Reference: https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/
    """
    raise NotImplementedError("TODO(student): build and compile the LangGraph StateGraph")
