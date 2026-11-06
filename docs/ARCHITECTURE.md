# Architecture

Signoff has one project/release contract and two adapters: the in-memory store for deterministic mock mode and `PostgresRepository` for production persistence. The API projection is `GET /api/v1/projects/{project_id}/releases/{release_id}/dashboard`; the old reference endpoint remains only as a compatibility alias. New project reads receive the organization from the authenticated user, never from a client-supplied tenant filter.

## Store and projections

In mock mode both demo projects live in one store, `store.projects[project_id]`, seeded by `apps/api/app/seed.py`. The store keeps facts only: requirements with their criteria, owner, scope status and verification state; evidence with artifact, SHA-256 and the run that produced it; verification runs; changes; comments; scope versions with their diff; client decisions; agent proposals and audit events. Visible text is stored in English and Spanish and resolved by the `locale` query parameter; enum values stay stable English keys.

Every number and list the product shows is computed from those facts by pure functions in `apps/api/app/projections.py`: dashboard metrics and rows, the coverage trend (replayed from evidence timestamps at each run), attention items, the activity feed (audit events rendered as localized sentences with their author), readiness through `domain.calculate_readiness`, prepare-delivery checks, the delivery pack, the client review story, and the project and release cards. `apps/api/app/catalog.py` is a thin facade over the store and the projections, kept so the PostgreSQL bootstrap and older callers use the same method names.

Mutations change facts under one lock and write an audit event with the project, the acting member, agent or client, a reference and the parameters for its activity text. Nothing is cached, so the next read of any view reflects the change. The web app reads every endpoint through react-query (`apps/web/lib/queries.ts`), and each mutation invalidates the shared project keys (`apps/web/lib/api.ts`), so all sections refresh together.

The seed is coherent by construction. Acme has 86 unique requirements (74 agreed, 8 pending on the two proposed changes, 4 out of scope after the two rejected changes), evidence for every passed requirement, 12 changes, open and resolved comments and 12 historical verification runs. Northstar keeps its 12 requirements with the same structure. A verification outcome is deterministic: a requirement without criteria or with a known defect fails until a change or a criteria proposal fixes it.

The web workspace uses the same shell for both demo projects. `/` redirects to `/dashboard`, the active release workspace, and the sidebar routes are global projections over the same project/release context. Release tabs are the only release-specific navigation.

The browser agent is designed as a state machine: planner → isolated Playwright executor → observation analyzer → evidence collector → structured judge. External page content is untrusted input and never changes system instructions. Long-running work is isolated behind Dramatiq actors in `apps/worker`.

The delivery graph is relational: Agreement → ScopeVersion → Requirement → AcceptanceCriterion → DeliveryReference → VerificationRun → EvidenceArtifact → DeliveryRelease → AcceptanceDecision. SQLAlchemy models cover identity, tenant membership, source documents, criteria, changes, verification steps/results, comments, delivery packs, integrations, audit events and LLM runs.

AI work uses the same `LLMProvider` methods in mock and production modes. The hosted adapter requests structured JSON, asks the provider not to retain the payload, and stores an auditable draft proposal until a person approves it. Long-running work has a `JobRunner` boundary and worker actors for Redis deployments.

Recommended deployment is Vercel for `apps/web`, a managed container platform for API/worker, managed PostgreSQL, Redis and R2/S3. Jobs must be idempotent and scoped by organization and project.
