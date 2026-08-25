# Day 08 Lab Report

## 1. Team / Student

- **Name:** Luu Nguyen Ngoc Han
- **Date:** 2026-08-26

## 2. Architecture

### Graph Nodes (11 total)

| Node | Purpose | LLM Used? |
|---|---|---|
| intake | Normalize raw query | No |
| classify | Classify query into route (simple/tool/missing_info/risky/error) | **Yes** |
| tool | Execute mock tool with error simulation | No |
| evaluate | Gate retry loop - check if tool result is satisfactory | Heuristic |
| answer | Generate final LLM response grounded in context | **Yes** |
| clarify | Ask clarification question for missing_info routes | **Yes** |
| risky_action | Prepare risky action for human approval | **Yes** |
| approval | Human-in-the-loop approval (mock or interrupt) | No |
| retry | Increment attempt counter, log transient failure | No |
| dead_letter | Handle max retry exhaustion | **Yes** |
| finalize | Emit final audit event | No |

### Graph Flow

```
START -> intake -> classify -> [conditional]
                           |
        +------------------+------------------+------------+--------+
        |                  |                  |            |        |
     simple            tool           missing_info    risky     error
        |                  |                  |            |        |
     answer            tool              clarify   risky_action  retry
        |                  |                  |            |        |
     finalize         evaluate            finalize    approval    |
                       |                                  |    [conditional]
                [needs_retry?]                     [approved?]   |
                    |                                    |        |
                 retry                              tool    dead_letter
                    |                                    |        |
             [bounded?]                          evaluate      finalize
                    |                                    |        |
        +------------+                          answer        END
        |            |                              |
     tool     dead_letter                       finalize
        |                                              |
    evaluate                                            END
        |
     answer
        |
    finalize
        |
        END
```

## 3. State Schema

| Field | Reducer | Purpose |
|---|---|---|
| thread_id | overwrite | Unique identifier per run |
| scenario_id | overwrite | Scenario identifier |
| query | overwrite | Original user query |
| route | overwrite | Current classification route |
| risk_level | overwrite | 'low' or 'high' |
| attempt | overwrite | Current retry attempt |
| max_attempts | overwrite | Maximum retries allowed |
| final_answer | overwrite | Final LLM response |
| pending_question | overwrite | Clarification question |
| proposed_action | overwrite | Risky action description |
| approval | overwrite | ApprovalDecision object |
| evaluation_result | overwrite | 'success' or 'needs_retry' |
| messages | append | Audit log of messages |
| tool_results | append | Tool execution results |
| errors | append | Error messages |
| events | append | Audit events with node, type, timestamp |

## 4. Metrics Summary

- **Total Scenarios:** 7
- **Success Rate:** 100.0%
- **Average Nodes Visited:** 6.6
- **Total Retries:** 4
- **Total Interrupts (Approval):** 2
- **Resume Success:** False

## 5. Scenario Results

| Scenario | Expected | Actual | Success | Retries | Interrupts |
|---|---|---|:---:|:---:|:---:|
| S01_simple | simple | simple | Y | 0 | 0 |
| S02_tool | tool | tool | Y | 0 | 0 |
| S03_missing | missing_info | missing_info | Y | 0 | 0 |
| S04_risky | risky | risky | Y | 0 | 1 |
| S05_error | error | error | Y | 3 | 0 |
| S06_delete | risky | risky | Y | 0 | 1 |
| S07_dead_letter | error | error | Y | 1 | 0 |

## 6. Failure Analysis

### Considered Failure Modes:

#### 1. Retry / Tool Failure
- **Scenario:** Error routes (S05, S07) simulate transient tool failures
- **Mechanism:** `evaluate_node` checks for 'ERROR' substring in tool results
- **Behavior:** If error detected, `route_after_evaluate` returns 'retry'
- **Bounded:** `route_after_retry` checks `attempt < max_attempts` before retry
- **Fallback:** After max attempts, routes to `dead_letter_node`
- **Example:** S07_dead_letter has max_attempts=1, exhausts retries immediately

#### 2. Risky Action Without Approval
- **Scenario:** Risky routes (S04, S06) require human approval
- **Mechanism:** `risky_action_node` identifies risky action, routes to `approval_node`
- **Behavior:** `approval_node` returns mock approval by default (approved=True)
- **Extension:** Set `LANGGRAPH_INTERRUPT=true` for real human-in-the-loop approval
- **Fallback:** If rejected, routes to `clarify` for user alternative

## 7. Persistence / Recovery Evidence

### Checkpointer Implementation
- **Memory:** `MemorySaver` for stateless testing (default)
- **SQLite:** `SqliteSaver` with WAL mode for persistence across restarts
- **Postgres:** `PostgresSaver` available for production deployments

### State Management
- **thread_id:** Unique per scenario (`thread-{scenario_id}`)
- **State History:** Available via `graph.get_state_history(config)`
- **Crash Recovery:** Can resume from checkpoint via `graph.get_state()` + `invoke()`

### Configuration
```yaml
checkpointer: sqlite  # or memory, postgres
```

## 8. Extension Work

### Implemented Extensions:

#### SQLite Persistence
- Implemented `build_checkpointer('sqlite')` in `persistence.py`
- Uses `SqliteSaver` with WAL mode for concurrent access
- Thread-safe connection with `check_same_thread=False`
- State history and crash-resume capabilities

#### LLM Integration
- **classify_node:** Uses `.with_structured_output()` for reliable intent classification
- **answer_node:** LLM generates grounded responses from context
- **ask_clarification_node:** LLM generates specific clarification questions
- **risky_action_node:** LLM describes proposed action and risks
- **dead_letter_node:** LLM generates empathetic escalation response

#### HITL (Human-in-the-Loop)
- Mock approval by default for testing/CI
- Real interrupt available via `LANGGRAPH_INTERRUPT=true`

## 9. Improvement Plan

### If I had one more day, I would productionize:

1. **Real Tool Integration**
   - Replace mock tool with actual API calls (order status, customer lookup)
   - Add proper error handling and retry with exponential backoff

2. **Streaming Response**
   - Use LangGraph streaming for real-time user feedback
   - Show intermediate steps in UI

3. **Evaluation Node LLM-as-Judge**
   - Upgrade heuristic check to LLM evaluation
   - Judge tool result quality, relevance, and completeness

4. **Streaming UI**
   - Build Streamlit interface for human approval/rejection
   - Show graph execution progress in real-time
