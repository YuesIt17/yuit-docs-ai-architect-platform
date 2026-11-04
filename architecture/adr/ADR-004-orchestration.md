# ADR-004: Orchestration (LangGraph)

## Status

Accepted

## Context

The course rules out linear chains (a script of LLM calls). The platform needs a stateful agent with branching: guard → route → retrieve/label → synthesize → output guard. This is a **fixed state machine**, not autonomous ReAct / Plan-and-Solve.

## Selection criteria

- Explicit state machine / state graph
- Chat / label / blocked branching
- Step observability (tracing)
- Continuity with hw-3 (Supervisor / Policy Analyst)

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| **LangGraph** | Stateful graph, checkpointing ecosystem | Learning curve |
| LlamaIndex Workflows | Convenient for RAG | Weaker agent loop for this case |
| Linear LangChain LCEL | Simple | **Rejected** by the course criterion |
| CrewAI multi-agent | Roles out of the box | Too heavy for the MVP ACL path |

## Decision

**LangGraph** state machine:

`guard_input → route → (contextualize → graph_retrieve → vector_retrieve [→ optional refine] | label_recognize → policy_check) → synthesize → guard_output → commit_turn`

`graph_retrieve` passes `graph_doc_ids` to `vector_retrieve`, so there is no redundant second resolve. Refinement is optional and bounded (`RETRIEVAL_REFINE_MAX`).

**Session memory** uses a LangGraph checkpointer: PostgreSQL in `live` mode, in-process otherwise.

- A thread is keyed by `role:user:session`, so reusing a session id cannot read another user's or role's history.
- Each turn stores its source document ids. Turns whose sources are gone or no longer accessible are dropped before they reach the LLM.
- A short question or one with a pronoun is searched together with the previous question.
- Dialog turns skip the semantic cache, because the question alone no longer identifies the answer.
- Only the dialog persists: chunk text is cleared at the end of the turn, and all other state resets at the start of the next one.

## Consequences

- (+) Meets the "not a linear script" criterion; explicit ACL/guard points
- (−) Harder graph debugging; checkpoints have no retention policy yet, so old threads must be purged by an operator

## References

- `app/backend/kp/agent/graph.py`, `app/backend/kp/agent/state.py`
- Sequence: [sequence-chat.md](../docs/sequence-chat.md)
