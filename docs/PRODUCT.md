# Product

SDA is the operating system for proving software delivery. It connects:

`AGREEMENT → BUILD → CHANGE → VERIFY → EVIDENCE → ACCEPT`

Jira manages the work, GitHub manages the code and testing tools test software. SDA proves what was agreed, what changed, what was delivered and what the client accepted.

Core product objects are Scope Baseline, Requirements, Acceptance Criteria, Delivery Graph, Change Radar, Verification Engine, Evidence Graph, Delivery Readiness, Delivery Pack and Client Acceptance.

The demo narrative is: import scope, review requirements, run controlled verification, inspect evidence, detect scope change and send a client-ready delivery pack.

The seeded workspace contains two projects using the same modules: Acme Inc. / Release 2.3 is the visual sign-off reference, and Customer Operations Portal v1 / Release 1.0 is the functional end-to-end demo. Switching projects changes the API projection and every downstream view; it does not load a second product implementation.

## Product surface

SDA is delivered as a browser-based B2B SaaS, not as a desktop application. The landing page (`/`) introduces the product and routes users into the demo workspace (`/dashboard`). A separate tokenized route (`/review/[token]`) is used for client acceptance, so reviewers can inspect a delivery pack without entering the internal workspace.

The initial experience is intentionally usable without external credentials: `MOCK_MODE=true` seeds a demo project and lets a user explore the full story before connecting real authentication, storage, LLM and browser providers.
