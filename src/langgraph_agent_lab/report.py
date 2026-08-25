"""Report generation helper.

Generates a complete lab report from metrics data.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .metrics import MetricsReport


def render_report(metrics: MetricsReport) -> str:
    """Render a complete lab report from metrics data.

    Generates a report that includes:
    1. Team/student info
    2. Architecture explanation
    3. State schema table
    4. Metrics summary table
    5. Per-scenario results table
    6. Failure analysis
    7. Persistence/recovery evidence
    8. Extension work
    9. Improvement plan

    Return: formatted markdown string
    """
    report = []

    # Header
    report.append("# Day 08 Lab Report")
    report.append("")
    report.append("## 1. Team / Student")
    report.append("")
    report.append("- **Name:** Luu Nguyen Ngoc Han")
    report.append(f"- **Date:** {datetime.now().strftime('%Y-%m-%d')}")
    report.append("")

    # Architecture
    report.append("## 2. Architecture")
    report.append("")
    report.append("### Graph Nodes (11 total)")
    report.append("")
    report.append("| Node | Purpose | LLM Used? |")
    report.append("|---|---|---|")
    report.append("| intake | Normalize raw query | No |")
    report.append(
        "| classify | Classify query into route (simple/tool/missing_info/risky/error) | **Yes** |"
    )
    report.append("| tool | Execute mock tool with error simulation | No |")
    report.append(
        "| evaluate | Gate retry loop - check if tool result is satisfactory | Heuristic |"
    )
    report.append("| answer | Generate final LLM response grounded in context | **Yes** |")
    report.append("| clarify | Ask clarification question for missing_info routes | **Yes** |")
    report.append("| risky_action | Prepare risky action for human approval | **Yes** |")
    report.append("| approval | Human-in-the-loop approval (mock or interrupt) | No |")
    report.append("| retry | Increment attempt counter, log transient failure | No |")
    report.append("| dead_letter | Handle max retry exhaustion | **Yes** |")
    report.append("| finalize | Emit final audit event | No |")
    report.append("")
    report.append("### Graph Flow")
    report.append("")
    report.append("```")
    report.append("START -> intake -> classify -> [conditional]")
    report.append("                           |")
    report.append("        +------------------+------------------+------------+--------+")
    report.append("        |                  |                  |            |        |")
    report.append("     simple            tool           missing_info    risky     error")
    report.append("        |                  |                  |            |        |")
    report.append("     answer            tool              clarify   risky_action  retry")
    report.append("        |                  |                  |            |        |")
    report.append("     finalize         evaluate            finalize    approval    |")
    report.append("                       |                                  |    [conditional]")
    report.append("                [needs_retry?]                     [approved?]   |")
    report.append("                    |                                    |        |")
    report.append("                 retry                              tool    dead_letter")
    report.append("                    |                                    |        |")
    report.append("             [bounded?]                          evaluate      finalize")
    report.append("                    |                                    |        |")
    report.append("        +------------+                          answer        END")
    report.append("        |            |                              |")
    report.append("     tool     dead_letter                       finalize")
    report.append("        |                                              |")
    report.append("    evaluate                                            END")
    report.append("        |")
    report.append("     answer")
    report.append("        |")
    report.append("    finalize")
    report.append("        |")
    report.append("        END")
    report.append("```")
    report.append("")

    # State Schema
    report.append("## 3. State Schema")
    report.append("")
    report.append("| Field | Reducer | Purpose |")
    report.append("|---|---|---|")
    report.append("| thread_id | overwrite | Unique identifier per run |")
    report.append("| scenario_id | overwrite | Scenario identifier |")
    report.append("| query | overwrite | Original user query |")
    report.append("| route | overwrite | Current classification route |")
    report.append("| risk_level | overwrite | 'low' or 'high' |")
    report.append("| attempt | overwrite | Current retry attempt |")
    report.append("| max_attempts | overwrite | Maximum retries allowed |")
    report.append("| final_answer | overwrite | Final LLM response |")
    report.append("| pending_question | overwrite | Clarification question |")
    report.append("| proposed_action | overwrite | Risky action description |")
    report.append("| approval | overwrite | ApprovalDecision object |")
    report.append("| evaluation_result | overwrite | 'success' or 'needs_retry' |")
    report.append("| messages | append | Audit log of messages |")
    report.append("| tool_results | append | Tool execution results |")
    report.append("| errors | append | Error messages |")
    report.append("| events | append | Audit events with node, type, timestamp |")
    report.append("")

    # Metrics Summary
    report.append("## 4. Metrics Summary")
    report.append("")
    report.append(f"- **Total Scenarios:** {metrics.total_scenarios}")
    report.append(f"- **Success Rate:** {metrics.success_rate:.1%}")
    report.append(f"- **Average Nodes Visited:** {metrics.avg_nodes_visited:.1f}")
    report.append(f"- **Total Retries:** {metrics.total_retries}")
    report.append(f"- **Total Interrupts (Approval):** {metrics.total_interrupts}")
    report.append(f"- **Resume Success:** {metrics.resume_success}")
    report.append("")

    # Scenario Results Table
    report.append("## 5. Scenario Results")
    report.append("")
    report.append("| Scenario | Expected | Actual | Success | Retries | Interrupts |")
    report.append("|---|---|---|:---:|:---:|:---:|")

    for metric in metrics.scenario_metrics:
        success_icon = "Y" if metric.success else "N"
        report.append(
            f"| {metric.scenario_id} | {metric.expected_route} | {metric.actual_route or 'N/A'} | "
            f"{success_icon} | {metric.retry_count} | {metric.interrupt_count} |"
        )

    report.append("")

    # Failure Analysis
    report.append("## 6. Failure Analysis")
    report.append("")
    report.append("### Considered Failure Modes:")
    report.append("")
    report.append("#### 1. Retry / Tool Failure")
    report.append("- **Scenario:** Error routes (S05, S07) simulate transient tool failures")
    report.append("- **Mechanism:** `evaluate_node` checks for 'ERROR' substring in tool results")
    report.append("- **Behavior:** If error detected, `route_after_evaluate` returns 'retry'")
    report.append("- **Bounded:** `route_after_retry` checks `attempt < max_attempts` before retry")
    report.append("- **Fallback:** After max attempts, routes to `dead_letter_node`")
    report.append("- **Example:** S07_dead_letter has max_attempts=1, exhausts retries immediately")
    report.append("")
    report.append("#### 2. Risky Action Without Approval")
    report.append("- **Scenario:** Risky routes (S04, S06) require human approval")
    report.append(
        "- **Mechanism:** `risky_action_node` identifies risky action, routes to `approval_node`"
    )
    report.append(
        "- **Behavior:** `approval_node` returns mock approval by default (approved=True)"
    )
    report.append(
        "- **Extension:** Set `LANGGRAPH_INTERRUPT=true` for real human-in-the-loop approval"
    )
    report.append("- **Fallback:** If rejected, routes to `clarify` for user alternative")
    report.append("")

    # Persistence / Recovery
    report.append("## 7. Persistence / Recovery Evidence")
    report.append("")
    report.append("### Checkpointer Implementation")
    report.append("- **Memory:** `MemorySaver` for stateless testing (default)")
    report.append("- **SQLite:** `SqliteSaver` with WAL mode for persistence across restarts")
    report.append("- **Postgres:** `PostgresSaver` available for production deployments")
    report.append("")
    report.append("### State Management")
    report.append("- **thread_id:** Unique per scenario (`thread-{scenario_id}`)")
    report.append("- **State History:** Available via `graph.get_state_history(config)`")
    report.append(
        "- **Crash Recovery:** Can resume from checkpoint via `graph.get_state()` + `invoke()`"
    )
    report.append("")
    report.append("### Configuration")
    report.append("```yaml")
    report.append("checkpointer: sqlite  # or memory, postgres")
    report.append("```")
    report.append("")

    # Extension Work
    report.append("## 8. Extension Work")
    report.append("")
    report.append("### Implemented Extensions:")
    report.append("")
    report.append("#### SQLite Persistence")
    report.append("- Implemented `build_checkpointer('sqlite')` in `persistence.py`")
    report.append("- Uses `SqliteSaver` with WAL mode for concurrent access")
    report.append("- Thread-safe connection with `check_same_thread=False`")
    report.append("- State history and crash-resume capabilities")
    report.append("")
    report.append("#### LLM Integration")
    report.append(
        "- **classify_node:** Uses `.with_structured_output()` for reliable intent classification"
    )
    report.append("- **answer_node:** LLM generates grounded responses from context")
    report.append("- **ask_clarification_node:** LLM generates specific clarification questions")
    report.append("- **risky_action_node:** LLM describes proposed action and risks")
    report.append("- **dead_letter_node:** LLM generates empathetic escalation response")
    report.append("")
    report.append("#### HITL (Human-in-the-Loop)")
    report.append("- Mock approval by default for testing/CI")
    report.append("- Real interrupt available via `LANGGRAPH_INTERRUPT=true`")
    report.append("")

    # Improvement Plan
    report.append("## 9. Improvement Plan")
    report.append("")
    report.append("### If I had one more day, I would productionize:")
    report.append("")
    report.append("1. **Real Tool Integration**")
    report.append("   - Replace mock tool with actual API calls (order status, customer lookup)")
    report.append("   - Add proper error handling and retry with exponential backoff")
    report.append("")
    report.append("2. **Streaming Response**")
    report.append("   - Use LangGraph streaming for real-time user feedback")
    report.append("   - Show intermediate steps in UI")
    report.append("")
    report.append("3. **Evaluation Node LLM-as-Judge**")
    report.append("   - Upgrade heuristic check to LLM evaluation")
    report.append("   - Judge tool result quality, relevance, and completeness")
    report.append("")
    report.append("4. **Streaming UI**")
    report.append("   - Build Streamlit interface for human approval/rejection")
    report.append("   - Show graph execution progress in real-time")
    report.append("")

    return "\n".join(report)


def write_report(metrics: MetricsReport, output_path: str | Path) -> None:
    """Write the rendered report to a file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(metrics), encoding="utf-8")
