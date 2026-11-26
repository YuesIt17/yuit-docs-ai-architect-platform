# Delivery Workflow: Roadmap, Specs, ADRs, Evidence

Keep all source-of-truth documents in the repository and review changes through Git. **A separate GitHub Wiki is not required.** The repository currently uses Markdown docs, ADRs and tests; formal OpenSpec integration is an **option**, not a claim of installation.

## What each artifact means

| Artifact | Purpose | Update when |
| --- | --- | --- |
| [Roadmap](./roadmap.md) | Strategy, sequence, milestones and non-goals | Priorities or major capability scope changes |
| [Capability map](./capabilities.md) | What exists, its evidence, gaps and replacements | When capability status or accepted architecture changes |
| [Engineering standards](./engineering/README.md) | How code is structured/tested in Python, TS and Go | When the quality contract evolves |
| Requirement/spec | What behavior must hold, including unhappy paths and acceptance tests | For a meaningful feature or change of external contract |
| ADR under `architecture/adr/` | Why a consequential architecture or security choice was made | Decision or trade-off changes; supersede rather than silently rewrite history |
| Tests, load data and traces | Evidence of observed behavior | Every change to verified claims |
| PR | Review scope, risk, rollout and sign-off | Every nontrivial change |

**ADRs are not feature specs.** They capture decisions and trade-offs, not a complete list of user scenarios and acceptance criteria.

## Lightweight specification-driven development

Prefer an **OpenSpec-compatible structure** if adopting the tool; do not require its CLI for the first iteration. Avoid duplicate truths.

Proposed structure (not necessarily present in the repository yet):

```text
openspec/
  specs/
    agent-registry/
    runtime-execution/
    model-gateway/
    agent-security/
    document-ingestion/
    evaluation/
  changes/
    <feature>/
      proposal.md
      specs/
      design.md
      tasks.md
    archive/
```

For small fixes, a PR description + tests is sufficient. For cross-component features or material policy/security/contract changes, use:

1. **Proposal:** problem, user, boundaries, explicit non-goals and alternatives.
2. **Requirements:** numbered MUST/SHOULD requirements, concrete normal/negative scenarios, latency and security acceptance conditions.
3. **Design:** component responsibilities and sequence, runtime policy and data handling; link relevant ADRs rather than copying them.
4. **Tasks:** dependency-ordered deliverable slices with evidence requirements; keep tool-specific implementation prompts out of canonical specs.
5. **Verification:** code/tests, live integration results, performance data and incident drills; clarify simulated vs measured.
6. **Closure:** update spec status, capability map, roadmap and appropriate presentation/docs in the same PR.

## Specification example: optional Google ADK

- **Requirement:** an approved manifest with `runtime: adk` invokes a local ADK reference agent through the same external platform API.
- **Security:** ADK cannot bypass the scoped tool authorization or closed local LiteLLM gateway.
- **Compatibility:** session IDs and platform events are normalized; **checkpoint migration between ADK and LangGraph is explicitly unsupported**.
- **Acceptance:** both runtimes pass shared auth-denial and gateway-failure tests; trace includes runtime and manifest version; no external request is observed by default.
- **ADR:** justify dispatcher/adapter abstraction; do not duplicate the behavior contract in the ADR.

## Definition of Ready / Done

**Ready:** a reason and scope, owner/priority, bounded interfaces, risk and negative cases, measurable acceptance conditions.

**Done:** shipped code (if relevant), CI, reproducible runtime/integration evidence, updated docs and diagrams, failure behavior and known limitations, no secrets committed. Mark `planned` → `implemented` → `verified` only when supported.

## Governance

- English-only repo documentation and code comments (existing exceptions in `AGENTS.md`).
- No commits directly to `main`; use a branch and pull request.
- No automatic merge; user decides.
- A spec requirement does not imply adding a dependency; prefer the current stack.
- Do not treat a local learning environment as healthcare-compliant or production-scale without separate evidence.
