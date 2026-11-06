import type { QueryClient } from "@tanstack/react-query";

export const API_BASE =
  process.env.NEXT_PUBLIC_SDA_API_URL || "http://127.0.0.1:8000";
const V1 = `${API_BASE}/api/v1`;

export type Locale = "en" | "es";

/* ----------------------------------------------------------------- enums */
export type Tone = "success" | "warning" | "error" | "progress" | "neutral";
export type ScopeStatus = "agreed" | "pending" | "out_of_scope";
export type Verification = "passed" | "failed" | "in_progress" | "not_started";
export type Acceptance = "accepted" | "pending" | "revision_requested" | "rejected";
export type ReleaseStatus =
  | "in_signoff"
  | "ready"
  | "on_hold"
  | "accepted"
  | "revision_requested"
  | "rejected";
export type ChangeStatus = "proposed" | "approved" | "rejected";
export type ProposalKind =
  | "criteria"
  | "verification_plan"
  | "evidence"
  | "change"
  | "comments"
  | "report";
export type ProposalStatus = "draft" | "approved" | "rejected";
export type ActorKind = "member" | "agent" | "client" | "system";
export type Severity = "critical" | "warning" | "info";
export type Priority = "high" | "medium" | "low";
export type EvidenceState =
  | "demonstrated"
  | "partially_demonstrated"
  | "not_demonstrated";
export type RunStatus =
  | "queued"
  | "running"
  | "requires_approval"
  | "completed"
  | "failed";

/* ---------------------------------------------------------------- shapes */
export type Actor = {
  id: string;
  name: string;
  initials: string;
  kind: ActorKind;
  role?: string;
};
export type RefType =
  | "requirement"
  | "evidence"
  | "change"
  | "proposal"
  | "scope_version";
export type Ref = { type: RefType; id: string; label: string };

export type MetricItem = { key: string; value: number; tone: Tone; label?: string };
export type Metric = { value: number; suffix?: string; items: MetricItem[] };

export type RequirementRow = {
  id: string;
  uuid: string;
  title: string;
  component: string;
  priority: Priority;
  owner: Actor;
  scope_status: ScopeStatus;
  verification: Verification;
  coverage: number;
  criteria_count: number;
  evidence_count: number;
  open_comments: number;
  acceptance: Acceptance;
};

export type ActivityItem = {
  id: string;
  actor: Actor;
  text: string;
  at: string;
  ref?: Ref;
};

export type Dashboard = {
  project: {
    id: string;
    name: string;
    client: string;
    release: string;
    version: string;
    status: ReleaseStatus;
    created_at: string;
    target_date: string;
  };
  metrics: {
    requirements: Metric;
    verification: Metric;
    coverage: Metric;
    changes: Metric;
  };
  requirements: RequirementRow[];
  verification_status: { key: Verification; value: number; tone: Tone }[];
  coverage_trend: { run: number; value: number; at: string }[];
  activity: ActivityItem[];
  attention_count: number;
  pending_proposals: number;
};

export type Evidence = {
  id: string;
  requirement_id: string;
  artifact: string;
  kind: "screenshot" | "log" | "csv" | "document" | "observation";
  source: "verification" | "upload" | "agent";
  state: EvidenceState;
  summary: string;
  sha256: string;
  size?: number;
  created_at: string;
  run_id?: string;
};

export type Comment = {
  id: string;
  requirement_id: string;
  author: Actor;
  text: string;
  created_at: string;
  resolved: boolean;
};

export type VerificationRun = {
  id: string;
  at: string;
  result: Verification;
  criteria_covered: number;
  criteria_total: number;
  coverage: number;
  evidence_ids: string[];
};

export type RequirementDetail = RequirementRow & {
  description: string;
  type: string;
  baseline: string;
  version: string;
  created_at: string;
  agreed_at: string;
  criteria: { id: string; text: string; source: "baseline" | "agent" | "manual" }[];
  verification_plan: null | { steps: string[]; proposal_id?: string };
  runs: VerificationRun[];
  evidence: Evidence[];
  comments: Comment[];
  changes: { id: string; title: string; status: ChangeStatus }[];
};

export type Change = {
  id: string;
  code: string;
  title: string;
  original: string;
  proposed: string;
  classification: string;
  status: ChangeStatus;
  impact: string;
  requirement_ids: string[];
  source: "client" | "agent" | "member";
  created_at: string;
  decided_by?: Actor;
};

export type ScopeVersion = {
  version: string;
  status: "approved" | "draft" | "superseded";
  source: string;
  summary: string;
  created_at: string;
  created_by: Actor;
  diff?: {
    added: { title: string; description: string; component: string }[];
    modified: { id: string; title: string; before: string; after: string }[];
    removed: { id: string; title: string }[];
  };
};

export type AttentionItem = {
  id: string;
  severity: Severity;
  title: string;
  source: string;
  count: number;
  target: {
    tab: "verification" | "changes" | "evidence" | "requirements" | "signoff" | "agents";
    requirement_id?: string;
  };
};

export type TeamMember = Actor & { email: string; role: string };

export type Project = {
  id: string;
  name: string;
  client: string;
  status: ReleaseStatus;
  release_id: string;
  release_name: string;
  requirements_count: number;
  readiness: number;
};

export type Release = {
  id: string;
  name: string;
  version: string;
  status: ReleaseStatus;
  created_at: string;
  target_date: string;
  baseline: string;
  coverage: number;
  verification: number;
};

export type Readiness = {
  release?: string;
  total_requirements: number;
  demonstrated: number;
  partial: number;
  not_demonstrated: number;
  without_evidence: number;
  unapproved_scope_changes: number;
  unresolved_comments: number;
  accepted: number;
  pending_acceptance: number;
  score: number;
};

export type DeliveryCheck = {
  key: string;
  label: string;
  status: "ready" | "attention" | "blocked";
  detail: string;
};
export type DeliveryChecks = { ready: boolean; checks: DeliveryCheck[] };

export type FileInspection = {
  valid?: boolean;
  assessment?: string;
  row_count?: number;
  columns?: string[];
  checks?: Record<string, boolean>;
  [key: string]: unknown;
};

export type ReviewPack = {
  project: { name: string; client: string; release: string };
  release_status: ReleaseStatus;
  story: { promised: string; delivered: string; changed: string; remaining: string };
  evidence: {
    id: string;
    artifact: string;
    summary: string;
    state: EvidenceState;
    requirement_id: string;
  }[];
  decision?: { decision: Acceptance; comment: string; at: string } | null;
};

export type AgentInfo = {
  id: string;
  name: string;
  description: string;
  name_es?: string;
  description_es?: string;
  tools: string[];
  accent: string;
};

export type AgentRunSummary = {
  id: string;
  agent: { id: string; name: string };
  status: RunStatus;
  created_at: string;
  proposal_id?: string;
  requirement_id?: string;
};

export type ProposalPayload = {
  criteria: { before: string[]; after: string[] };
  verification_plan: { steps: string[] };
  evidence: {
    artifact: string;
    summary: string;
    state: EvidenceState;
    observations: string[];
  };
  change: {
    title: string;
    original: string;
    proposed: string;
    classification: string;
    impact: string;
  };
  comments: { items: { requirement_id: string; text: string }[] };
  report: { sections: { title: string; body: string }[]; refs: Ref[] };
};

export type Proposal = {
  id: string;
  run_id: string;
  agent: { id: string; name: string };
  kind: ProposalKind;
  status: ProposalStatus;
  title: string;
  summary: string;
  requirement_id?: string;
  payload: Record<string, unknown>;
  created_at: string;
  decided_by?: Actor;
};

/* ------------------------------------------------------------- transport */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${V1}${path}`, init);
  if (!response.ok) {
    let detail = `Signoff API returned ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

/** The contract returns arrays; older endpoints wrapped lists in `{items}`. Accept both. */
async function list<T>(path: string): Promise<T[]> {
  const body = await request<T[] | { items: T[] }>(path);
  return Array.isArray(body) ? body : body.items || [];
}

function json(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
}

const p = (projectId: string) => `/projects/${encodeURIComponent(projectId)}`;
const q = (locale: Locale) => `locale=${locale}`;

export const api = {
  projects: (locale: Locale) => list<Project>(`/projects?${q(locale)}`),
  releases: (projectId: string, locale: Locale) =>
    list<Release>(`${p(projectId)}/releases?${q(locale)}`),
  dashboard: (projectId: string, releaseId: string, locale: Locale) =>
    request<Dashboard>(
      `${p(projectId)}/releases/${encodeURIComponent(releaseId)}/dashboard?${q(locale)}`,
    ),
  requirements: (projectId: string, locale: Locale) =>
    list<RequirementRow>(`${p(projectId)}/requirements?${q(locale)}`),
  requirement: (projectId: string, humanId: string, locale: Locale) =>
    request<RequirementDetail>(
      `${p(projectId)}/requirements/${encodeURIComponent(humanId)}?${q(locale)}`,
    ),
  updateRequirement: (
    projectId: string,
    humanId: string,
    body: { scope_status?: ScopeStatus; priority?: Priority; owner_id?: string },
  ) =>
    request<RequirementDetail>(
      `${p(projectId)}/requirements/${encodeURIComponent(humanId)}`,
      json("PATCH", body),
    ),
  addComment: (projectId: string, humanId: string, text: string) =>
    request<Comment>(
      `${p(projectId)}/requirements/${encodeURIComponent(humanId)}/comments`,
      json("POST", { text }),
    ),
  resolveComment: (projectId: string, commentId: string) =>
    request<Comment>(
      `${p(projectId)}/comments/${encodeURIComponent(commentId)}/resolve`,
      json("POST"),
    ),
  evidence: (projectId: string, locale: Locale) =>
    list<Evidence>(`${p(projectId)}/evidence?${q(locale)}`),
  uploadEvidence: (
    projectId: string,
    input: { file: File; requirementId: string; description: string },
  ) => {
    const form = new FormData();
    form.append("file", input.file);
    form.append("requirement_id", input.requirementId);
    form.append("description", input.description);
    return request<{ evidence: Evidence; inspection?: FileInspection | null }>(
      `${p(projectId)}/evidence`,
      { method: "POST", body: form },
    );
  },
  evidenceUrl: async (projectId: string, artifact: string) => {
    const result = await request<{ url: string }>(
      `${p(projectId)}/evidence/${encodeURIComponent(artifact)}/signed-url`,
    );
    return result.url.startsWith("/") ? `${API_BASE}${result.url}` : result.url;
  },
  runVerification: (projectId: string, requirementIds: string[]) =>
    request<{ runs: VerificationRun[]; evidence: Evidence[]; requirements: RequirementRow[] }>(
      `${p(projectId)}/runs`,
      json("POST", { requirement_ids: requirementIds }),
    ),
  changes: (projectId: string, locale: Locale) =>
    list<Change>(`${p(projectId)}/changes?${q(locale)}`),
  updateChange: (projectId: string, changeId: string, status: "approved" | "rejected") =>
    request<Change>(
      `${p(projectId)}/changes/${encodeURIComponent(changeId)}`,
      json("PATCH", { status }),
    ),
  scopeVersions: (projectId: string, locale: Locale) =>
    list<ScopeVersion>(`${p(projectId)}/scope/versions?${q(locale)}`),
  extractScope: (projectId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ScopeVersion>(`${p(projectId)}/scope/extract`, {
      method: "POST",
      body: form,
    });
  },
  approveScopeVersion: (projectId: string, version: string) =>
    request<ScopeVersion>(
      `${p(projectId)}/scope/versions/${encodeURIComponent(version)}/approve`,
      json("POST"),
    ),
  attention: (projectId: string, locale: Locale) =>
    list<AttentionItem>(`${p(projectId)}/attention?${q(locale)}`),
  activity: (projectId: string, locale: Locale, limit = 20) =>
    list<ActivityItem>(`${p(projectId)}/activity?${q(locale)}&limit=${limit}`),
  team: (projectId: string) => list<TeamMember>(`${p(projectId)}/team`),
  readiness: (projectId: string) => request<Readiness>(`${p(projectId)}/readiness`),
  prepareDelivery: (projectId: string, locale: Locale) =>
    request<DeliveryChecks>(`${p(projectId)}/prepare-delivery?${q(locale)}`, json("POST")),
  deliveryPack: (projectId: string, locale: Locale) =>
    request<Record<string, unknown>>(`${p(projectId)}/delivery-pack?${q(locale)}`),
  setReleaseStatus: (projectId: string, releaseId: string, status: ReleaseStatus) =>
    request<unknown>(
      `${p(projectId)}/releases/${encodeURIComponent(releaseId)}/status`,
      json("PATCH", { status }),
    ),
  sendForAcceptance: (projectId: string, releaseId: string) =>
    request<unknown>(
      `${p(projectId)}/releases/${encodeURIComponent(releaseId)}/send-for-acceptance`,
      json("POST"),
    ),
  review: (token: string, locale: Locale) =>
    request<ReviewPack>(`/review/${encodeURIComponent(token)}?${q(locale)}`),
  submitReview: (
    token: string,
    decision: "accepted" | "rejected" | "revision_requested",
    comment: string,
  ) =>
    request<unknown>(`/review/${encodeURIComponent(token)}`, json("POST", { decision, comment })),
  agents: () => list<AgentInfo>(`/agents`),
  agentRuns: (projectId: string) => list<AgentRunSummary>(`${p(projectId)}/agents/runs`),
  runAgent: (
    projectId: string,
    body: {
      agent_id: string;
      input: string;
      requirement_id?: string;
      classification: string;
      consent: boolean;
    },
  ) =>
    request<{ run_id: string; agent: { id: string; name: string }; status: RunStatus }>(
      `${p(projectId)}/agents/run`,
      json("POST", body),
    ),
  dispatchAgent: (
    projectId: string,
    body: {
      input: string;
      requirement_id?: string;
      classification: string;
      consent: boolean;
      target_url?: string;
    },
  ) =>
    request<{ run_id: string; agent: { id: string; name: string }; status: RunStatus }>(
      `${p(projectId)}/agents/dispatch`,
      json("POST", body),
    ),
  proposals: (projectId: string, locale: Locale, status: ProposalStatus | "all" = "draft") =>
    list<Proposal>(
      `${p(projectId)}/proposals?${q(locale)}${status === "all" ? "" : `&status=${status}`}`,
    ),
  approveProposal: (projectId: string, proposalId: string) =>
    request<{ proposal: Proposal; applied: Ref[] }>(
      `${p(projectId)}/proposals/${encodeURIComponent(proposalId)}/approve`,
      json("POST"),
    ),
  rejectProposal: (projectId: string, proposalId: string, comment?: string) =>
    request<{ proposal: Proposal }>(
      `${p(projectId)}/proposals/${encodeURIComponent(proposalId)}/reject`,
      json("POST", { comment }),
    ),
  runEventsUrl: (runId: string, locale: Locale, after: number) =>
    `${V1}/agent-runs/${encodeURIComponent(runId)}/events?${q(locale)}&after=${after}`,
};

/* ---------------------------------------------------------- query keys */
/** Every project-scoped key starts with [name, projectId] so prefix invalidation reaches all variants. */
export const keys = {
  projects: (locale: Locale) => ["projects", locale] as const,
  releases: (projectId: string, locale: Locale) => ["releases", projectId, locale] as const,
  dashboard: (projectId: string, releaseId: string, locale: Locale) =>
    ["dashboard", projectId, releaseId, locale] as const,
  requirements: (projectId: string, locale: Locale) =>
    ["requirements", projectId, locale] as const,
  requirement: (projectId: string, humanId: string, locale: Locale) =>
    ["requirement", projectId, humanId, locale] as const,
  changes: (projectId: string, locale: Locale) => ["changes", projectId, locale] as const,
  evidence: (projectId: string, locale: Locale) => ["evidence", projectId, locale] as const,
  attention: (projectId: string, locale: Locale) => ["attention", projectId, locale] as const,
  activity: (projectId: string, locale: Locale) => ["activity", projectId, locale] as const,
  readiness: (projectId: string) => ["readiness", projectId] as const,
  proposals: (projectId: string, locale: Locale) => ["proposals", projectId, locale] as const,
  scopeVersions: (projectId: string, locale: Locale) =>
    ["scope-versions", projectId, locale] as const,
  team: (projectId: string) => ["team", projectId] as const,
  agentRuns: (projectId: string) => ["agent-runs", projectId] as const,
  agents: () => ["agents"] as const,
  review: (token: string, locale: Locale) => ["review", token, locale] as const,
};

const PROJECT_SCOPED = [
  "dashboard",
  "requirements",
  "requirement",
  "changes",
  "evidence",
  "attention",
  "activity",
  "readiness",
  "proposals",
  "releases",
  "scope-versions",
  "team",
  "agent-runs",
] as const;

/** One invalidation for every write: whatever changed, every view of the project re-derives from the API. */
export function invalidateProject(queryClient: QueryClient, projectId: string) {
  return Promise.all([
    ...PROJECT_SCOPED.map((name) =>
      queryClient.invalidateQueries({ queryKey: [name, projectId] }),
    ),
    queryClient.invalidateQueries({ queryKey: ["projects"] }),
    queryClient.invalidateQueries({ queryKey: ["review"] }),
  ]);
}

/* ------------------------------------------------------------ SSE stream */
export type AgentStreamEvent =
  | {
      type: "run_started";
      id: number;
      data: {
        run_id: string;
        agent: { id: string; name: string };
        steps: { index: number; tool: string; label: string }[];
      };
    }
  | { type: "step_started"; id: number; data: { index: number; tool: string; label: string } }
  | {
      type: "step_completed";
      id: number;
      data: {
        index: number;
        tool: string;
        label: string;
        duration_ms: number;
        summary: string;
        refs: Ref[];
      };
    }
  | { type: "proposal_created"; id: number; data: { proposal: Proposal } }
  | { type: "run_completed"; id: number; data: { status: RunStatus; summary: string } }
  | { type: "run_failed"; id: number; data: { error: string } };

/**
 * Reads `text/event-stream` with fetch + ReadableStream (not EventSource, so auth headers can be
 * added outside mock mode). Resolves when the stream closes; reports whether a terminal event arrived.
 */
export async function readAgentEvents(
  runId: string,
  locale: Locale,
  after: number,
  onEvent: (event: AgentStreamEvent) => void,
  signal: AbortSignal,
): Promise<{ lastId: number; terminal: boolean }> {
  const response = await fetch(api.runEventsUrl(runId, locale, after), {
    headers: {
      Accept: "text/event-stream",
      ...(after > 0 ? { "Last-Event-ID": String(after) } : {}),
    },
    signal,
  });
  if (!response.ok || !response.body) {
    throw new ApiError(response.status, `Event stream unavailable (${response.status})`);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let lastId = after;
  let terminal = false;

  const dispatch = (block: string) => {
    let id: number | null = null;
    let type = "message";
    const data: string[] = [];
    for (const rawLine of block.split("\n")) {
      const line = rawLine.replace(/\r$/, "");
      if (!line || line.startsWith(":")) continue;
      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
      if (field === "id") id = Number(value);
      else if (field === "event") type = value;
      else if (field === "data") data.push(value);
    }
    if (!data.length) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(data.join("\n"));
    } catch {
      return;
    }
    if (id !== null && Number.isFinite(id)) lastId = id;
    if (type === "run_completed" || type === "run_failed") terminal = true;
    onEvent({ type, id: id ?? lastId, data: parsed } as AgentStreamEvent);
  };

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      dispatch(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) dispatch(buffer);
  return { lastId, terminal };
}
