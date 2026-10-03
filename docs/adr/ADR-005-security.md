# ADR-005: Security & RBAC

## Decision
- Roles: guest, store_associate, category_manager, compliance_officer
- Classifications: public / internal / secret on every chunk/document
- Retrieval **always** ACL-filtered; Output Guard blocks secret leakage
- Vision path: MIME allowlist + size limit
- Evolution of hw-6 security layer