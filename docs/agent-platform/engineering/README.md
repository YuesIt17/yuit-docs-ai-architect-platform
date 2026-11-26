# Engineering Excellence Standards

These rules apply to **new or materially changed** code in RetailPartnerX. Do not undertake a repo-wide rewrite for cosmetic purity. Prioritize correctness, production operability, security, readable decomposition, and demonstrable algorithmic reasoning.

Related: [capability map](../capabilities.md), [delivery workflow](../delivery-workflow.md), [roadmap](../roadmap.md), repository [AGENTS.md](../../../AGENTS.md).

## Cross-language quality bar

1. **Design by responsibility.** Modules, packages and functions should have cohesive responsibilities. Decompose god modules and long business flows as touched; avoid artificial one-file-per-function structures or blanket line limits.
2. **Contracts first.** State input/output types, invariants, error semantics, timeouts, cancellation, idempotency, privacy boundaries and compatibility. Use clear dependency boundaries. Share OpenAPI-derived types where practical.
3. **Explicit failure behavior.** Network calls have bounded deadlines; retries require backoff + jitter and retryable classification; side-effecting calls require deduplication/idempotency.
4. **Secure defaults.** No secrets in source, manifests, tracing or error messages; safe permissions, tool allowlists, input validation and no implicit external model access. Treat OCR documents and tool responses as untrusted input.
5. **Testing pyramid.** Unit tests for logic, contract tests at API/runtime boundaries, integration tests for real infrastructure where feasible, failure injection for critical paths, and baseline load/latency for hotspots.
6. **Documentation with signal.** Public contract docs, non-obvious invariants and decision trade-offs; no comments that merely paraphrase code. Documentation must stay in English.
7. **Observability.** Trace/correlation IDs and meaningful measurements, but bounded metric cardinality; do not embed raw sensitive content in spans.
8. **Refactor safely.** Establish behavior with tests before altering boundaries, preserve existing course functionality and generated diagram workflow.
9. **Dependency hygiene.** Lock dependencies, review changes, use vulnerability/secret scanning; optional SBOM when supply-chain risk warrants it. Avoid importing frameworks for one helper.
10. **Evidence-first.** Record executed commands and environment; never conflate tests of stubs/mocks with live integrations.

## Python / FastAPI

- Keep layers coherent: **API adapters → application use cases → domain entities/policies**, with infrastructure implementing inner-facing ports. Do not make domain types depend on FastAPI, databases or LangGraph.
- Use Pydantic at transport/config boundaries, meaningful type hints on public interfaces, `Protocol` when substitutable implementations have actual consumers, dependency injection and async-safe state.
- Prefer small functions with named intent, early returns and explicit errors; avoid mutable singleton request routing and monolithic handlers.
- Document public APIs and complex business operations with **Google-style Python docstrings** (`Args`, `Returns`, `Raises` when informative); choose one consistent style, not JSDoc syntax.
- Keep existing **Ruff + pytest**. Consider Pyright or mypy incrementally; raise type coverage on edited modules. Use pytest-asyncio, fixtures and integration tests; track meaningful branch coverage, not vanity percentage.
- Differentiate domain-specific services, orchestration and infrastructure clients; never hide remote I/O in harmless-looking domain methods.

## TypeScript / React / Vite

- Keep **React + strict TypeScript + Vite**. Prefer *pragmatic* Feature-Sliced Design: `app/`, `pages/`, `features/`, `entities/`, `shared/`; create `widgets/` only when it improves composition.
- Expose slice public APIs; avoid cross-feature private imports, cyclic dependencies and giant page components. Keep UI, state/data fetching, validation and domain transformations separate.
- Use typed API contracts (ideally OpenAPI generated when worthwhile), discriminated unions for status/events, explicit loading/error/cancel states, stable event typing for SSE.
- Add **ESLint, Prettier** and appropriately scoped tests (unit + component; end-to-end for critical auth/agent flows) when the frontend baseline is ready. Do not add competing state managers without a need.
- Use **TSDoc/JSDoc** for exported SDK and complex public contracts; avoid boilerplate comments for private obvious functions. Apply accessibility and error-state checks.

## Go BFF

- Follow idiomatic Go rather than importing Python/Java layered class patterns. Prefer cohesive packages, small consumer-defined interfaces, constructors for non-trivial dependencies, `context.Context` and explicit timeouts.
- Secure browser session/OIDC/CSRF boundaries; avoid leaking tokens into the browser, logging or telemetry.
- Wrap errors with context, validate external inputs, use proper HTTP status mapping; guard shared state and race test concurrent refresh/rotate/session operations.
- Keep **gofmt, go vet, go test -race, golangci-lint** gates; add integration/contract tests for BFF ↔ API, session refresh, auth denial, timeout and cancellation.
- Use Go doc comments on exported package symbols and non-obvious security or concurrency contracts.

## Algorithmic engineering (LeetCode knowledge applied to production)

**Goal:** choose correct data structures and algorithms for actual platform problems, not write puzzle-looking production code.

| Technique | Meaningful platform application | Important production constraint |
| --- | --- | --- |
| Hash maps/sets and hashing | Registry, deduplication, content identity, cache invalidation | Collision assumptions, versioning and bounded memory |
| Graph traversal/DAG/topological sort | GraphRAG, agent workflow dependencies | ACL filtering, cycles, termination |
| Heaps/priority queues | Queue scheduling, retry deadlines | Fairness, starvation, durable state |
| TTL/LRU caches | Model metadata, retrieval cache | Isolation, invalidation, stale security decisions |
| Token bucket/sliding window | Tenant/agent rate limiting | Distributed consistency, burst policies |
| Exponential backoff + jitter | Model/tool retry | Retry budget, idempotency, circuit breaking |
| State machines | Agent run lifecycle and approval | Valid transitions and recovery |
| Binary search/optimization | Monotonic threshold tuning/capacity trade-offs | Verified monotonicity and real workloads |

For each non-trivial optimization: write invariants, asymptotic time/space cost, failure conditions, and a focused benchmark when performance matters. Prefer battle-tested libraries and databases to custom infrastructure. Do not force dynamic programming, linked lists or other interview patterns into unrelated features.

## Engineering review checklist

- [ ] Code boundaries and public contracts are understandable without a long explanation
- [ ] Correct permissions, secrets, privacy and error-handling boundaries
- [ ] Concurrent requests do not share mutable per-request state
- [ ] Tests cover normal, denied and failure/retry paths; real vs mocked evidence clear
- [ ] API/schema changes preserve or version contracts between Python, TypeScript and Go
- [ ] Observability, timeouts, performance and resource budgets considered
- [ ] Code/docstrings and specs updated without duplication
- [ ] Architecture diagrams and presentation refreshed when applicable
