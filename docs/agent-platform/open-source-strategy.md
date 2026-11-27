# Coraium Agent Platform — Open-Source and Community Strategy

> **Strategy, not a release announcement.** Do not describe planned runtime, A2A, cloud, or healthcare features as shipped. The first working reference implementation remains RetailPartnerX GraphRAG.

## Positioning

**Name:** Coraium Agent Platform  
**One-liner:** Secure, self-hosted infrastructure for domain-aware AI agents.  
**Extended positioning:** An evidence-first agent platform focused on access-controlled knowledge retrieval, runtime independence, traceability, reliable execution and interoperable agent systems. Current code uses LangGraph; Google ADK and cross-runtime A2A are roadmap items.

**Brand architecture:** Coraium = overarching brand; Coraium Agent Platform = infrastructure; RetailPartnerX = first working retail reference application; Food/Nutrition/Fitness, Health Evidence and DevSecOps = proposed domain reference applications. Avoid presenting all domains as current products.

**Audience:** AI/platform engineers, software architects, enterprise engineering teams, security-minded developers, and engineers who need reproducible local experiments with agent reliability.

**Distinction from agent frameworks:** This project is not a new orchestrator or a clone of LangGraph/ADK. It demonstrates reusable *platform contracts and operational evidence* around identity, tools, model gateway, audits, tests and deployment. Multi-runtime and A2A will be demonstrated only when real integration tests exist.

## Open-source release milestones

| Milestone | Candidate scope | Readiness condition |
| --- | --- | --- |
| **v0.1 — Foundation** | Existing LangGraph Retail GraphRAG, ACL-aware retrieval, registry, local model/gateway options, security baseline and observability | Public README, permissive-data audit, dependency/license review, reproducible local quickstart, tests and recorded limitations. Version tag only after verification |
| **v0.2 — Independent runtimes** | Local Google ADK read-only Policy/DevSecOps reference agent and real LangGraph ↔ ADK A2A example | Separate runnable services, scoped Agent Cards/tasks, failure/permission tests and traces |
| **v0.3 — Domain examples** | Synthetic Food/Nutrition/Fitness workflows, source-grounded Health Evidence examples and governance use cases | Documented non-clinical scope, isolation and evaluation evidence; no patient-data claims |

These are **planning labels, not released versions**. Prefer shipping a small trustworthy release to indefinitely delaying for optional domain features.

## Repository and release readiness

1. **Rights and privacy review:** ensure all source code, documents, illustrations and datasets are publishable; remove internal/company-specific details, secrets and identifiers. Confirm ownership before adopting an open-source license.
2. **License decision:** choose an OSI-approved license after checking dependencies, trademarks and third-party content. Do not assume public visibility grants reuse rights.
3. **Contributor experience:** add `CONTRIBUTING.md`, `SECURITY.md`, code of conduct as community participation warrants, issue/PR templates and clearly marked good-first-issues only when maintainable.
4. **Quickstart:** one tested local path, precise hardware/dependency notes, sample data, documented cleanup, common failures and source-controlled config examples without secrets.
5. **Security:** vulnerability-reporting channel, secret scans, least-privilege defaults, safe demo credentials and no real health/customer data in test artifacts or traces.
6. **Evidence:** badges/claims must point to actual CI, integration logs, performance measurements and repeatable examples. No fabricated benchmark numbers or healthcare compliance claims.
7. **Brand artifacts:** repository logo/banner, clear tagline, screenshots and diagrams with `implemented` vs `planned` labels. Avoid copying proprietary logos or images.

## Marketing and developer adoption

**Narrative:** Engineering trustworthy agents is more than chaining LLM calls. Show working security boundaries, meaningful architecture trade-offs, and failure handling rather than promising an all-in-one assistant.

**Distribution:** GitHub README and Releases; technical articles, short practical demo videos, the `Systems, Visually` LinkedIn series, optional YouTube demonstrations, and constructive participation in developer communities. Do not spam or promise features that are not tested.

**Suggested first content series:**
1. "Beyond the agent demo: what a secure self-hosted platform actually needs" — shipped LangGraph/ACL/observability evidence.
2. "Why your agent manifest is not yet a security boundary" — manifest declarations vs enforcement.
3. "Agent-to-agent interoperability without sharing internal state" — publish only when the A2A demo is working.
4. "LangGraph and ADK as independent systems: the trade-offs" — actual measurements, not framework hype.
5. "From product labels to source-grounded food and wellness workflows" — synthetic, non-medical reference data only.

**Adoption signals:** reproducible successful setups, useful issues/PRs, returning contributors, and validated use cases matter more than vanity stars. Track docs gaps, time-to-first-demo, test outcomes and relevant user feedback without collecting personal data unnecessarily.

## Scope and maintenance

Start with **one maintainer-friendly development workflow** and one reliable release path. Do not prematurely create a full suite of paid services, package registries, cloud providers, CRDs/operators, or a separate ecosystem of agent frameworks. Any future monetization or hosted offering is a separate product/security/legal decision.

## Launch checklist (not yet satisfied)

- [ ] Confirm ownership and review proprietary or sensitive content
- [ ] Choose and add an appropriate LICENSE
- [ ] Verify local quickstart and run tests in a fresh environment
- [ ] Publish CONTRIBUTING, SECURITY and disclosure instructions
- [ ] Verify demo data and no-secret logging/traces
- [ ] Confirm logo/diagram copyright and GitHub rendering
- [ ] Tag first actual release with changelog and known limitations
- [ ] Publish demo and invite targeted technical feedback

Related: [roadmap](./roadmap.md), [multi-domain architecture](./multi-domain-architecture.md), [capability map](./capabilities.md), and [public architecture diagrams](./public-architecture.md).
