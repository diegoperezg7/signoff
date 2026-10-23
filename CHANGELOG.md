# Changelog

## Unreleased — Portfolio polish

- Fixed the display font token, which made the client review portal fall back to a serif font.
- Fixed text buttons in project, template and baseline cards, and tab content being pushed below the requirement drawer.
- Derived the failed verification count, release status card and next decision from the active release instead of fixed text.
- Kept the coverage trend inside its metric card.
- Compacted the workspace header on phones and showed the full wordmark in the mobile sidebar and review portal.
- Styled the landing theme toggle and fixed the dark mode proof cards and secondary button.
- Summarized agent tool outputs in the agent panel instead of showing raw JSON.
- Replaced the screenshots with a light-theme walkthrough and an animated tour, and documented the agents, request path, evidence links and verification flow with diagrams.

## 0.3.0 — 2026-08-19 — Contextual agents and privacy controls

- Added eight contextual agents with allowlisted tools, a risk-rated tool registry, an organization agent policy, checkpoints, approvals and the agent panel.
- Added the QA explorer for route discovery and smoke checks on allowed hosts, with observations stored as evidence.
- Added opt-in, metadata-only email alerts for agent runs.
- Added per-document AI consent, retention windows and document erasure that keeps only audit metadata.
- Added agent avatars and clearer feedback while an agent runs.

## 0.2.0 — 2026-08-18 — Consolidated workspace

- Added two shared-architecture demo projects with canonical project/release dashboard projections.
- Added real global workspace navigation, URL-synchronised context and token-resolved review portals.
- Added structured LLM provider parity, a hosted model adapter, auditable proposals, PostgreSQL models/repository and signed evidence links.
- Wired shared verification, evidence, readiness, acceptance and Delivery Pack endpoints to the active demo project, with canonical IDs in the PostgreSQL adapter.
- Completed and smoke-tested the customer journey from project selection through AI criteria, Change Radar, verification, evidence inspection, readiness, Delivery Pack and client acceptance.
- Removed the legacy dashboard from the landing route and kept `/` focused on product entry.

## 0.1.0 — 2026-08-18 — Demo vertical slice

- Added mock FastAPI API and seeded delivery assurance project.
- Added Next.js dark-first dashboard and client review portal.
- Added requirements, scope changes, verification, evidence and delivery pack views.
- Added Docker Compose, CI, tests and architecture/product/security documentation.
