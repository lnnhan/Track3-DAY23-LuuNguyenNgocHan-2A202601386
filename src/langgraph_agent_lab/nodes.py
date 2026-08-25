"""Node functions for the LangGraph workflow.

Each function receives AgentState and returns a partial state update dict.
Do NOT mutate input state — return new values only.

LLM REQUIREMENT:
- classify_node MUST use a real LLM call (structured output for intent classification)
- answer_node MUST use a real LLM call (grounded response generation)
- evaluate_node SHOULD use LLM-as-judge (bonus points; heuristic acceptable for base score)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .llm import get_llm
from .state import AgentState, ApprovalDecision, make_event


# ─── Classification Schema for Structured Output ──────────────────────
class ClassificationResult(BaseModel):
    """Structured output for classify_node."""

    route: Literal["simple", "tool", "missing_info", "risky", "error"]
    risk_level: Literal["low", "high"]
    reasoning: str


# ─── EXAMPLE: working node (provided for reference) ──────────────────
def intake_node(state: AgentState) -> dict:
    """Normalize raw query. This node is provided as a working example."""
    query = state.get("query", "").strip()
    return {
        "query": query,
        "messages": [f"intake:{query[:40]}"],
        "events": [make_event("intake", "completed", "query normalized")],
    }


# ─── Classification Node ──────────────────────────────────────────────
def classify_node(state: AgentState) -> dict:
    """Classify the query into a route using an LLM.

    Uses structured output for reliable classification into:
    - simple: general questions answerable without tools or actions
    - tool: information lookups (order status, tracking, search)
    - missing_info: vague/incomplete queries lacking actionable context
    - risky: actions with side effects (refunds, deletions, emails)
    - error: system failures (timeouts, crashes, service unavailable)

    Priority: risky > tool > missing_info > error > simple
    """
    query = state.get("query", "")

    # Prompt for classification with priority awareness
    classification_prompt = f"""Classify the following support ticket query into exactly one category.

Categories (choose the FIRST matching one based on priority):
1. risky: Actions with side effects - refunds, deletions, cancellations, sending emails, account changes
2. tool: Information lookups - order status, tracking, search queries, account lookups
3. missing_info: Vague/incomplete queries that lack actionable context or key details
4. error: System failures - timeouts, crashes, service unavailable, exceptions
5. simple: General questions answerable directly without tools or actions

Query to classify:
"{query}"

Respond with a JSON object containing:
- route: the category (simple/tool/missing_info/risky/error)
- risk_level: "high" for risky, "low" for all others
- reasoning: brief explanation of why this category was chosen

IMPORTANT: If the query mentions system failures, timeouts, crashes, or errors → classify as "error".
If the query mentions actions like refunds, delete, cancel, send email → classify as "risky".
If the query is a simple question answerable directly → classify as "simple".
If the query is vague or lacks details → classify as "missing_info".
If the query asks for information lookup → classify as "tool"."""

    # Use LLM with structured output
    llm = get_llm(temperature=0.0)
    structured_llm = llm.with_structured_output(ClassificationResult)
    result = structured_llm.invoke(classification_prompt)

    return {
        "route": result.route,
        "risk_level": result.risk_level,
        "events": [
            make_event(
                "classify",
                "completed",
                f"classified as {result.route} (risk_level={result.risk_level})",
                reasoning=result.reasoning,
            )
        ],
    }


# ─── Tool Node ────────────────────────────────────────────────────────
def tool_node(state: AgentState) -> dict:
    """Execute a mock tool call.

    Simulate transient failures for error-route scenarios to test retry loops.
    - If route is "error" and attempt < 2: return error result
    - Otherwise: return a mock success result
    """
    route = state.get("route", "")
    attempt = state.get("attempt", 0)
    scenario_id = state.get("scenario_id", "unknown")

    # Simulate transient failure for error routes (first 2 attempts fail)
    if route == "error" and attempt < 2:
        result = f"ERROR: Timeout failure while processing request for {scenario_id}"

        return {
            "tool_results": [result],
            "events": [
                make_event(
                    "tool", "error", f"simulated error on attempt {attempt + 1}", attempt=attempt
                )
            ],
        }

    # Mock successful tool results based on query
    query = state.get("query", "").lower()
    scenario_id_clean = state.get("scenario_id", "unknown")

    if "order" in query and "status" in query:
        result = f"Order status for {scenario_id_clean}: Processing - Expected delivery in 3-5 business days"
    elif "track" in query:
        result = "Tracking info: Package in transit - Current location: Distribution Center"
    else:
        result = f"Tool execution completed for {scenario_id_clean}: Query processed successfully"

    return {
        "tool_results": [result],
        "events": [make_event("tool", "completed", "tool executed successfully")],
    }


# ─── Evaluate Node ────────────────────────────────────────────────────
def evaluate_node(state: AgentState) -> dict:
    """Evaluate tool results — the retry-loop gate.

    Check whether the latest tool result is satisfactory or needs retry.
    Uses heuristic check for "ERROR" substring (LLM-as-judge is bonus).
    """
    tool_results = state.get("tool_results", [])

    if not tool_results:
        evaluation = "needs_retry"
    else:
        latest_result = tool_results[-1]
        # Heuristic: check for error indicators
        if (
            "ERROR" in latest_result
            or "error" in latest_result
            or "failed" in latest_result.lower()
        ):
            evaluation = "needs_retry"
        else:
            evaluation = "success"

    return {
        "evaluation_result": evaluation,
        "events": [
            make_event(
                "evaluate",
                "completed",
                f"evaluation: {evaluation}",
                latest_result=tool_results[-1] if tool_results else None,
            )
        ],
    }


# ─── Answer Node ─────────────────────────────────────────────────────
def answer_node(state: AgentState) -> dict:
    """Generate a final response using an LLM.

    The LLM generates a helpful response grounded in available context:
    - tool_results (if any)
    - approval decision (if risky route)
    - pending_question (if clarification was requested)
    - original query
    """
    query = state.get("query", "")
    tool_results = state.get("tool_results", [])
    approval = state.get("approval")
    pending_question = state.get("pending_question")
    route = state.get("route", "")

    # Build context for the LLM
    context_parts = []

    if tool_results:
        context_parts.append("Tool results:\n" + "\n".join(f"- {r}" for r in tool_results))

    if approval and hasattr(approval, "approved"):
        if approval.approved:
            context_parts.append(f"Approval status: APPROVED by {approval.reviewer}")
            if approval.comment:
                context_parts.append(f"Reviewer comment: {approval.comment}")
        else:
            context_parts.append("Approval status: DENIED")
            if approval.comment:
                context_parts.append(f"Reviewer comment: {approval.comment}")

    if pending_question:
        context_parts.append(f"Clarification question was asked: {pending_question}")

    context_str = (
        "\n\n".join(context_parts) if context_parts else "No additional context available."
    )

    answer_prompt = f"""You are a helpful customer support agent. Generate a clear, concise response to the user's query based on the available context.

Original Query: {query}

Context Information:
{context_str}

Requirements:
- Be helpful and professional
- If tool results are available, incorporate them into your answer
- If approval was obtained for a risky action, confirm this in your response
- If clarification was needed, acknowledge what was asked
- Keep the response focused and actionable
- Do not mention the internal routing or classification process"""

    # Use LLM to generate answer
    llm = get_llm(temperature=0.3)
    response = llm.invoke(answer_prompt)
    final_answer = response.content if hasattr(response, "content") else str(response)

    return {
        "final_answer": final_answer,
        "events": [
            make_event(
                "answer",
                "completed",
                f"generated answer for {route} route",
                has_tool_results=bool(tool_results),
                has_approval=bool(approval and hasattr(approval, "approved")),
            )
        ],
    }


# ─── Ask Clarification Node ──────────────────────────────────────────
def ask_clarification_node(state: AgentState) -> dict:
    """Ask for missing information instead of hallucinating.

    Generate a specific clarification question based on the vague/incomplete query.
    """
    query = state.get("query", "")

    clarification_prompt = f"""The following support query is vague or incomplete. Generate a specific clarification question that would help resolve the user's issue.

Vague Query: "{query}"

Generate a polite, specific question that:
1. Acknowledges the user's request briefly
2. Asks for the specific information needed to help them
3. Is actionable and clear

Respond with just the clarification question, nothing else."""

    llm = get_llm(temperature=0.3)
    response = llm.invoke(clarification_prompt)
    pending_question = response.content if hasattr(response, "content") else str(response)

    # Also generate a preliminary response acknowledging the need for clarification
    acknowledgment_prompt = f"""Acknowledge this support request and indicate that more information is needed.

Query: "{query}"

Write a brief, polite acknowledgment that:
1. Thanks the user for their message
2. Indicates we need a bit more information
3. Includes the clarification question naturally

Keep it under 3 sentences."""

    ack_response = llm.invoke(acknowledgment_prompt)
    final_answer = ack_response.content if hasattr(ack_response, "content") else str(ack_response)

    return {
        "pending_question": pending_question,
        "final_answer": final_answer,
        "events": [
            make_event(
                "ask_clarification",
                "completed",
                "clarification question generated",
                original_query=query,
            )
        ],
    }


# ─── Risky Action Node ───────────────────────────────────────────────
def risky_action_node(state: AgentState) -> dict:
    """Prepare a risky action for human approval.

    Describe the proposed action and why it requires approval.
    """
    query = state.get("query", "")
    scenario_id = state.get("scenario_id", "unknown")

    # Analyze the risky action requested
    action_analysis_prompt = f"""Analyze this support request and describe:
1. What action is being requested (be specific)
2. Why this action requires human approval (potential risks, side effects)

Request: "{query}"

Format your response as:
ACTION: [specific description of the action]
REASON: [why this requires approval]
RISK_FACTORS: [potential risks or concerns]"""

    llm = get_llm(temperature=0.0)
    response = llm.invoke(action_analysis_prompt)
    proposed_action = response.content if hasattr(response, "content") else str(response)

    return {
        "proposed_action": proposed_action,
        "events": [
            make_event(
                "risky_action",
                "pending_approval",
                "risky action identified, human approval required",
                scenario_id=scenario_id,
            )
        ],
    }


# ─── Approval Node ────────────────────────────────────────────────────
def approval_node(state: AgentState) -> dict:
    """Human-in-the-loop approval step.

    Default behavior: mock approval (approved=True) so tests and CI run offline.
    Extension: if env LANGGRAPH_INTERRUPT=true, use interrupt() for real HITL.
    """
    import os

    proposed_action = state.get("proposed_action", "")

    # Check for real HITL mode
    if os.getenv("LANGGRAPH_INTERRUPT", "").lower() == "true":
        try:
            from langgraph.types import interrupt

            # Real human approval via interrupt
            interrupt_value = interrupt(
                {
                    "proposed_action": proposed_action,
                    "message": "Approval required for risky action",
                }
            )
            # If we get here after interrupt, use the approved value
            if isinstance(interrupt_value, dict):
                return {
                    "approval": ApprovalDecision(
                        approved=interrupt_value.get("approved", False),
                        reviewer="human",
                        comment=interrupt_value.get("comment", ""),
                    ),
                    "events": [
                        make_event(
                            "approval",
                            "approved" if interrupt_value.get("approved") else "denied",
                            "human approval received via interrupt",
                            reviewer="human",
                        )
                    ],
                }
        except Exception:
            pass  # Fall back to mock approval

    # Mock approval for testing (approved=True)
    # In production, this would be replaced with actual human approval
    mock_approval = ApprovalDecision(
        approved=True,
        reviewer="mock-reviewer",
        comment="Auto-approved for testing (set LANGGRAPH_INTERRUPT=true for real HITL)",
    )

    return {
        "approval": mock_approval,
        "events": [
            make_event(
                "approval",
                "approved",
                "mock approval (override available)",
                reviewer="mock-reviewer",
            )
        ],
    }


# ─── Retry/Fallback Node ──────────────────────────────────────────────
def retry_or_fallback_node(state: AgentState) -> dict:
    """Record a retry attempt.

    Increment the attempt counter and log the transient failure.
    """
    current_attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    route = state.get("route", "")
    tool_results = state.get("tool_results", [])

    new_attempt = current_attempt + 1

    # Get error message from latest tool result
    error_msg = tool_results[-1] if tool_results else "Unknown error"

    return {
        "attempt": new_attempt,
        "errors": [f"Attempt {new_attempt}/{max_attempts}: {error_msg}"],
        "events": [
            make_event(
                "retry",
                "attempt_incremented",
                f"retry attempt {new_attempt} of {max_attempts}",
                current_attempt=new_attempt,
                max_attempts=max_attempts,
                route=route,
            )
        ],
    }


# ─── Dead Letter Node ─────────────────────────────────────────────────
def dead_letter_node(state: AgentState) -> dict:
    """Handle unresolvable failures after max retries exceeded.

    This is the third layer: retry → fallback → dead letter.
    Log the failure and set a final_answer explaining that the request could not be completed.
    """
    attempt = state.get("attempt", 0)
    max_attempts = state.get("max_attempts", 3)
    route = state.get("route", "")
    query = state.get("query", "")
    errors = state.get("errors", [])

    # Generate a helpful dead letter response
    dead_letter_prompt = f"""Generate a helpful response for a support ticket that could not be resolved after multiple attempts.

Original Query: "{query}"
Attempts Made: {attempt}
Max Attempts: {max_attempts}

Generate a response that:
1. Apologizes for the inconvenience
2. Explains that the issue could not be resolved automatically
3. Indicates that the ticket has been escalated to a human agent
4. Provides reassurance that someone will follow up

Keep it professional and empathetic. Do not mention specific error codes or technical details."""

    llm = get_llm(temperature=0.3)
    response = llm.invoke(dead_letter_prompt)
    final_answer = response.content if hasattr(response, "content") else str(response)

    return {
        "final_answer": final_answer,
        "events": [
            make_event(
                "dead_letter",
                "max_retries_exceeded",
                f"ticket escalated after {attempt} failed attempts",
                route=route,
                errors=errors,
            )
        ],
    }


# ─── Finalize Node ────────────────────────────────────────────────────
def finalize_node(state: AgentState) -> dict:
    """Emit a final audit event. All routes must pass through here before END.

    This node ensures all workflows have a consistent termination point
    for logging and audit purposes.
    """
    scenario_id = state.get("scenario_id", "unknown")
    route = state.get("route", "")
    attempt = state.get("attempt", 0)
    final_answer = state.get("final_answer")

    return {
        "events": [
            make_event(
                "finalize",
                "completed",
                f"workflow finished for scenario {scenario_id}",
                route=route,
                attempt=attempt,
                has_answer=final_answer is not None,
            )
        ],
    }
