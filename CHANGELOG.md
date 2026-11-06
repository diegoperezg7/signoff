# Changelog

## Unreleased — Visual redesign

- New palette: pure black and pure white backgrounds, untinted greys, ink black as the light-mode primary and phosphor lime as the dark-mode primary and signature accent. Status colours shifted so they do not collide with the lime.
- Inter replaces Geist as the product font; tighter title, KPI and table typography.
- Redrawn brand mark as an inline SVG that inverts between themes; regenerated favicon, app icons and README lockups.
- Agent avatars are now Lucide icons on neutral tiles instead of generated 3D images.
- Charts (coverage trend, verification ring and donut, coverage bars) read the theme tokens.
- Dashboard layout: wider table next to the drawer, KPI cards without coloured bars, calmer navigation and secondary buttons.
- Removed the public landing page: `/` now redirects to `/dashboard`.
- The client review portal follows the same tokens in both themes.
- Screenshots of every screen in light and dark mode in `docs/screenshots/`.
- One live store for both projects: the API keeps facts only and derives every metric, list, attention item, activity line, readiness score, delivery check and review story from them. The three override dictionaries and all literal numbers are gone.
- Coherent bilingual seed: Acme has 86 unique requirements across six components with owners, evidence for every passed requirement, 12 real changes, comments and a 12-run coverage history; Northstar keeps its 12 requirements with the same structure.
- Every mutation writes an audit event with project, actor and parameters, rendered as a localized activity feed; `/audit` no longer returns events from other projects.
- Agents run in the background and stream their steps over Server-Sent Events, with replay through `Last-Event-ID` or `?after=`. Tools read the live project context, every run ends with one typed draft proposal, and approving it applies criteria, a verification plan, evidence, a change or comments. Failed runs end as `failed` instead of a server error.
- New endpoints: requirement detail and update, comments with resolve, multipart evidence upload with CSV inspection, scope extraction into a draft baseline with a diff and approval that applies it, team, activity, and proposals with approve and reject.
- Verification runs and scope extraction now work for both projects, and the client decision in the portal sets the release status for either one.
- The web app reads everything through react-query and invalidates shared keys after each action, so all sections stay in sync.
- Dashboard charts: a coverage trend chart with one point per verification run, horizontal verification status bars instead of the donut, and stacked bars under the requirements and changes KPIs.
- Motion: KPIs count up on load and animate to new values after an action, bars grow on mount and agent steps enter as they arrive; all of it is disabled under `prefers-reduced-motion`.
- CORS also allows the dev preview on port 4100.

## Portfolio polish

- Fixed the display font token, which made the client review portal fall back to a serif font.
- Fixed text buttons in project, template and baseline cards, and tab content being pushed below the requirement drawer.
- Derived the failed verification count, release status card and next decision from the active release instead of fixed text.
- Kept the coverage trend inside its metric card.
- Compacted the workspace header on phones and showed the full wordmark in the mobile sidebar and review portal.
- Styled the landing theme toggle and fixed the dark mode proof cards and secondary button.
- Summarized agent tool outputs in the agent panel instead of showing raw JSON.
- Scoped every `/api/v1/projects/{project_id}` route to the caller's organization, including verification runs, evidence, file inspection and acceptance.
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
