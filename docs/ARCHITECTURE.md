# Architecture

SDA has one project/release contract and two adapters: `ProjectCatalog`/`InMemoryRepository` for deterministic mock mode and `PostgresRepository` for production persistence. The API projection is `GET /api/v1/projects/{project_id}/releases/{release_id}/dashboard`; the old reference endpoint remains only as a compatibility alias. New project reads receive the organization from the authenticated user, never from a client-supplied tenant filter.

The web workspace uses the same shell for both demo projects. `/` is the public landing, `/dashboard` is the active release workspace and the sidebar routes are global projections over the same project/release context. Release tabs are the only release-specific navigation.

The browser agent is designed as a state machine: planner → isolated Playwright executor → observation analyzer → evidence collector → structured judge. External page content is untrusted input and never changes system instructions. Long-running work is isolated behind Dramatiq actors in `apps/worker`.

The delivery graph is relational: Agreement → ScopeVersion → Requirement → AcceptanceCriterion → DeliveryReference → VerificationRun → EvidenceArtifact → DeliveryRelease → AcceptanceDecision. SQLAlchemy models cover identity, tenant membership, source documents, criteria, changes, verification steps/results, comments, delivery packs, integrations, audit events and LLM runs.

AI work is exposed through the same `LLMProvider` methods in mock and production modes. `OpenAIProvider` uses structured JSON schema responses, `store=false` and creates an auditable draft proposal before human approval. Long-running work has a `JobRunner` boundary and Dramatiq actors for Redis deployments.

Recommended deployment is Vercel for `apps/web`, a managed container platform for API/worker, managed PostgreSQL, Redis and R2/S3. Jobs must be idempotent and scoped by organization and project.
