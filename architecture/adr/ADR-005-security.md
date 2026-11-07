# ADR-005: Security and RBAC

## Status

Accepted

## Context

Critical criterion: **User B must not receive an answer based on a secret document**. The security layer evolves from hw-6: PII handling, prompt injection defense, output guardrails and ACL at retrieval.

## Selection criteria

- Filtering **before** the LLM (not only post hoc)
- Document and role classification
- Demo without a full IdP (learning MVP)
- Protection of the vision path (MIME / size)

## Options

| Option | Pros | Cons |
| ------ | ---- | ---- |
| ACL in the prompt only | Simple | Easy to bypass; leaks through citations |
| **Chunk-level ACL + output guard** | Defense in depth | Policy lives in two places |
| Full OIDC + ABAC | Production grade | Out of MVP scope |

## Decision

- Roles: `guest`, `store_associate`, `category_manager`, `compliance_officer`
- Classifications: `public` / `internal` / `secret` on Document/Chunk
- Retrieval is **always** ACL-filtered; the Output Guard blocks secret leaks
- Vision: MIME allowlist + size limit
- Demo tokens in the UI by default (not a production IdP). Optional real login through Keycloak and a Go BFF: [ADR-010](ADR-010-bff-auth.md). A corporate IdP is on the roadmap
- Cluster layer: Restricted Pod Security, default-deny NetworkPolicy, optional Kyverno admission ([k8s-hardening.md](../../docs/infra/k8s-hardening.md))

## Consequences

- (+) The manager vs compliance demo satisfies the course criterion
- (−) In the default mode, a demo bearer token is not real authentication; node-level Neo4j ACL is the next stage

## References

- `app/backend/kp/security/rbac.py`, `guardrails.py`
- Demo: [video](https://www.youtube.com/watch?v=y2_mY9_ceuU)
