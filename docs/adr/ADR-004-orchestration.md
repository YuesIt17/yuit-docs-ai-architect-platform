# ADR-004: Orchestration

## Decision
**LangGraph** state machine (not linear chains): guard_input → route → retrieve/label → synthesize → guard_output with ReAct-style tool nodes.

Inherits multi-agent SRP ideas from hw-3 (Policy Analyst as policy_check tool).