"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  Check,
  ChevronRight,
  ClipboardCheck,
  FileSearch,
  FolderCheck,
  GitCompareArrows,
  History,
  Inbox,
  ListChecks,
  LoaderCircle,
  Minus,
  MonitorCheck,
  Plus,
  Route,
  ShieldCheck,
  Sparkles,
  Stamp,
  Wrench,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  api,
  invalidateProject,
  keys,
  readAgentEvents,
  type AgentInfo,
  type AgentStreamEvent,
  type Locale,
  type Proposal,
  type ProposalPayload,
  type Ref,
  type RunStatus,
} from "../../lib/api";
import { useAgentRuns, useAgents, useProjectMutation, useProposals } from "../../lib/queries";
import {
  evidenceTone,
  formatDuration,
  formatRelative,
  label,
  pillClass,
  runTone,
  useCopy,
  type Copy,
} from "../dashboard/copy";

export type DockView =
  | { type: "launch" }
  | { type: "pending" }
  | { type: "history" }
  | { type: "run"; runId: string }
  | { type: "proposal"; id: string };
export type DockState = { open: boolean; view: DockView };

type RunAgentInput = { agentId: string; input?: string; requirementId?: string; consent?: boolean };

/** Starts an agent run; the caller switches the dock to the returned run to watch it stream. */
export function useStartAgent(projectId: string) {
  const { c } = useCopy();
  return useProjectMutation(projectId, (input: RunAgentInput) =>
    api.runAgent(projectId, {
      agent_id: input.agentId,
      input: input.input || c.agentDefaultInput,
      requirement_id: input.requirementId,
      classification: "CONFIDENTIAL",
      consent: Boolean(input.consent),
    }),
  );
}

export function AgentDock({
  projectId,
  requirementId,
  state,
  onChange,
  onNavigate,
  notify,
}: {
  projectId: string;
  requirementId: string | null;
  state: DockState;
  onChange: (state: DockState) => void;
  onNavigate: (ref: Ref) => void;
  notify: (message: string) => void;
}) {
  const { c, locale } = useCopy();
  const proposals = useProposals(projectId);
  const pendingCount = proposals.data?.length ?? 0;
  const view = state.view;
  const setView = (next: DockView) => onChange({ open: true, view: next });
  const topLevel = view.type === "launch" || view.type === "pending" || view.type === "history";

  return (
    <div className="reference-agent-dock">
      <button
        className="reference-agent-trigger"
        onClick={() => onChange({ ...state, open: !state.open })}
        aria-expanded={state.open}
      >
        <Sparkles size={15} />
        {c.agents}
        {pendingCount > 0 && <span className="signoff-count-badge">{pendingCount}</span>}
      </button>
      {state.open && (
        <section className="reference-agent-panel" aria-label={c.agents}>
          <header className="reference-agent-panel-header">
            <div>
              <span className="reference-context-kicker">SIGNOFF INTELLIGENCE</span>
              <h2>{c.agentsTitle}</h2>
            </div>
            <button
              className="reference-agent-close"
              onClick={() => onChange({ ...state, open: false })}
              aria-label={c.closeAgents}
            >
              <X size={16} />
            </button>
          </header>
          {topLevel ? (
            <div className="signoff-dock-tabs" role="tablist">
              <DockTab active={view.type === "launch"} onClick={() => setView({ type: "launch" })} icon={Wrench}>
                {c.launch}
              </DockTab>
              <DockTab active={view.type === "pending"} onClick={() => setView({ type: "pending" })} icon={Inbox}>
                {c.pendingTab}
                {pendingCount > 0 && <span className="signoff-count-badge">{pendingCount}</span>}
              </DockTab>
              <DockTab active={view.type === "history"} onClick={() => setView({ type: "history" })} icon={History}>
                {c.historyTab}
              </DockTab>
            </div>
          ) : (
            <button className="signoff-dock-back" onClick={() => setView({ type: "launch" })}>
              <ArrowLeft size={14} />
              {c.back}
            </button>
          )}
          {view.type === "launch" && (
            <LaunchView
              projectId={projectId}
              requirementId={requirementId}
              onStarted={(runId) => setView({ type: "run", runId })}
            />
          )}
          {view.type === "pending" && (
            <div className="signoff-dock-list">
              {proposals.data?.length ? (
                proposals.data.map((proposal) => (
                  <button
                    key={proposal.id}
                    className="signoff-dock-row"
                    onClick={() => setView({ type: "proposal", id: proposal.id })}
                  >
                    <AgentBadge agentId={proposal.agent.id} />
                    <span>
                      <strong>{proposal.title}</strong>
                      <small>
                        <AgentName agent={proposal.agent} /> · {label(c.proposalKind, proposal.kind)}
                        {proposal.requirement_id ? ` · ${proposal.requirement_id}` : ""}
                      </small>
                    </span>
                    <ChevronRight size={15} />
                  </button>
                ))
              ) : (
                <p className="reference-agent-empty">{c.noPending}</p>
              )}
            </div>
          )}
          {view.type === "history" && (
            <HistoryView projectId={projectId} onOpen={(runId) => setView({ type: "run", runId })} />
          )}
          {view.type === "run" && (
            <RunView
              key={`${view.runId}:${locale}`}
              projectId={projectId}
              runId={view.runId}
              onNavigate={onNavigate}
              notify={notify}
            />
          )}
          {view.type === "proposal" && (
            <StandaloneProposal
              projectId={projectId}
              proposalId={view.id}
              onOpenRun={(runId) => setView({ type: "run", runId })}
              onNavigate={onNavigate}
              notify={notify}
            />
          )}
        </section>
      )}
    </div>
  );
}

function DockTab({
  active,
  onClick,
  icon: Icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon: LucideIcon;
  children: ReactNode;
}) {
  return (
    <button role="tab" aria-selected={active} className={active ? "is-active" : ""} onClick={onClick}>
      <Icon size={13} />
      {children}
    </button>
  );
}

/* ---------------------------------------------------------------- launch */
function LaunchView({
  projectId,
  requirementId,
  onStarted,
}: {
  projectId: string;
  requirementId: string | null;
  onStarted: (runId: string) => void;
}) {
  const { c, locale } = useCopy();
  const agents = useAgents();
  const [agentId, setAgentId] = useState("delivery-analyst");
  const [question, setQuestion] = useState("");
  const [consent, setConsent] = useState(false);
  const start = useStartAgent(projectId);
  const dispatch = useProjectMutation(projectId, () =>
    api.dispatchAgent(projectId, {
      input: question || c.dispatchDefaultInput,
      requirement_id: requirementId || undefined,
      classification: "CONFIDENTIAL",
      consent,
      target_url: `${window.location.origin}/dashboard`,
    }),
  );
  const busy = start.isPending || dispatch.isPending;
  const error = start.error || dispatch.error;
  const list = agents.data || [];

  return (
    <>
      <div className="reference-agent-safety">
        <ShieldCheck size={15} />
        <span>{c.agentSafety}</span>
      </div>
      <div className="reference-agent-list">
        {agents.isPending && (
          <div className="reference-agent-loading">
            <LoaderCircle className="reference-agent-spinner" size={15} />
            {c.loadingAgents}
          </div>
        )}
        {!agents.isPending && list.length === 0 && <div className="reference-agent-empty">{c.noAgents}</div>}
        {list.map((agent) => (
          <button
            key={agent.id}
            className={`reference-agent-option${agent.id === agentId ? " is-selected" : ""}`}
            onClick={() => setAgentId(agent.id)}
            aria-pressed={agent.id === agentId}
          >
            <span className={`reference-agent-icon agent-${agent.accent}`}>
              <AgentAvatar agentId={agent.id} />
            </span>
            <span>
              <strong>{agentDisplayName(agent.id, agent.name, locale, list)}</strong>
              <small>{agentDescription(agent, locale)}</small>
            </span>
            <ChevronRight size={15} />
          </button>
        ))}
      </div>
      <label className="reference-agent-question">
        <span>{c.agentQuestion}</span>
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder={c.agentPlaceholder}
          rows={2}
        />
      </label>
      <label className="reference-agent-consent">
        <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
        <span>{c.consent}</span>
      </label>
      <div className="reference-agent-actions">
        <button
          className="reference-agent-run"
          disabled={busy || !list.some((agent) => agent.id === agentId)}
          onClick={() =>
            start.mutate(
              { agentId, input: question, requirementId: requirementId || undefined, consent },
              { onSuccess: (result) => onStarted(result.run_id) },
            )
          }
        >
          <Wrench size={15} />
          {start.isPending ? c.starting : c.runAgent}
          {start.isPending ? <LoaderCircle className="reference-agent-spinner" size={15} /> : <ChevronRight size={15} />}
        </button>
        <button
          className="reference-agent-ask"
          disabled={busy}
          onClick={() => dispatch.mutate(undefined, { onSuccess: (result) => onStarted(result.run_id) })}
        >
          {dispatch.isPending ? <LoaderCircle className="reference-agent-spinner" size={15} /> : <Sparkles size={15} />}
          {c.askSignoff}
        </button>
      </div>
      {error && <p className="reference-agent-error">{`${c.agentFailed}: ${error.message}`}</p>}
    </>
  );
}

/* --------------------------------------------------------------- history */
function HistoryView({ projectId, onOpen }: { projectId: string; onOpen: (runId: string) => void }) {
  const { c, locale } = useCopy();
  const runs = useAgentRuns(projectId);
  if (runs.isPending)
    return (
      <div className="reference-agent-loading">
        <LoaderCircle className="reference-agent-spinner" size={15} />
      </div>
    );
  if (!runs.data?.length) return <p className="reference-agent-empty">{c.noHistory}</p>;
  return (
    <div className="signoff-dock-list">
      {runs.data.map((run) => (
        <button key={run.id} className="signoff-dock-row" onClick={() => onOpen(run.id)}>
          <AgentBadge agentId={run.agent.id} />
          <span>
            <strong>
              <AgentName agent={run.agent} />
            </strong>
            <small>
              {formatRelative(run.created_at, locale)}
              {run.requirement_id ? ` · ${run.requirement_id}` : ""}
            </small>
          </span>
          <span className={pillClass(runTone[run.status] || "neutral")}>{label(c.runStatus, run.status)}</span>
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------- run view */
type StepState = {
  index: number;
  tool: string;
  label: string;
  status: "pending" | "running" | "done";
  duration_ms?: number;
  summary?: string;
  refs: Ref[];
};
type StreamState = {
  agent: { id: string; name: string } | null;
  steps: StepState[];
  proposal: Proposal | null;
  status: "connecting" | RunStatus;
  summary: string;
  error: string;
  reconnecting: boolean;
};

const initialStream: StreamState = {
  agent: null,
  steps: [],
  proposal: null,
  status: "connecting",
  summary: "",
  error: "",
  reconnecting: false,
};

function upsertStep(steps: StepState[], next: Partial<StepState> & { index: number }) {
  const exists = steps.some((step) => step.index === next.index);
  const merged = exists
    ? steps.map((step) => (step.index === next.index ? { ...step, ...next } : step))
    : [...steps, { tool: "", label: "", status: "pending" as const, refs: [], ...next }];
  return merged.slice().sort((a, b) => a.index - b.index);
}

function reduceStream(current: StreamState, event: AgentStreamEvent): StreamState {
  switch (event.type) {
    case "run_started":
      return {
        ...current,
        status: "running",
        reconnecting: false,
        agent: event.data.agent,
        steps: event.data.steps.reduce(
          (steps, step) =>
            steps.some((item) => item.index === step.index)
              ? steps
              : upsertStep(steps, { ...step, status: "pending" }),
          current.steps,
        ),
      };
    case "step_started":
      return {
        ...current,
        status: "running",
        reconnecting: false,
        steps: upsertStep(current.steps, { ...event.data, status: "running" }),
      };
    case "step_completed":
      return {
        ...current,
        reconnecting: false,
        steps: upsertStep(current.steps, { ...event.data, refs: event.data.refs || [], status: "done" }),
      };
    case "proposal_created":
      return { ...current, proposal: event.data.proposal };
    case "run_completed":
      return {
        ...current,
        reconnecting: false,
        status: event.data.status,
        summary: event.data.summary,
        steps: current.steps.map((step) => ({ ...step, status: "done" as const })),
      };
    case "run_failed":
      return { ...current, reconnecting: false, status: "failed", error: event.data.error };
    default:
      return current;
  }
}

/** Replays the run from the first event (`after=0`), reconnects from the last id if the stream drops. */
function useRunStream(projectId: string, runId: string, locale: Locale) {
  const queryClient = useQueryClient();
  const [stream, setStream] = useState<StreamState>(initialStream);

  useEffect(() => {
    const controller = new AbortController();
    let lastId = 0;
    const handle = (event: AgentStreamEvent) => {
      setStream((current) => reduceStream(current, event));
      if (event.type === "proposal_created" || event.type === "run_completed" || event.type === "run_failed") {
        void invalidateProject(queryClient, projectId);
      }
    };

    (async () => {
      for (let attempt = 0; attempt < 4 && !controller.signal.aborted; attempt += 1) {
        try {
          const result = await readAgentEvents(runId, locale, lastId, handle, controller.signal);
          lastId = result.lastId;
          if (result.terminal) return;
        } catch (caught) {
          if (controller.signal.aborted) return;
          if (attempt === 3) {
            setStream((current) => ({
              ...current,
              status: "failed",
              reconnecting: false,
              error: caught instanceof Error ? caught.message : String(caught),
            }));
            return;
          }
        }
        if (controller.signal.aborted) return;
        setStream((current) => ({ ...current, reconnecting: true }));
        await new Promise((resolve) => window.setTimeout(resolve, 900));
      }
    })();

    return () => controller.abort();
  }, [projectId, queryClient, runId, locale]);

  return stream;
}

function RunView({
  projectId,
  runId,
  onNavigate,
  notify,
}: {
  projectId: string;
  runId: string;
  onNavigate: (ref: Ref) => void;
  notify: (message: string) => void;
}) {
  const { c, locale } = useCopy();
  const stream = useRunStream(projectId, runId, locale);
  const status = stream.status;
  const live = status === "connecting" || status === "queued" || status === "running";

  return (
    <div className="reference-agent-result signoff-run">
      <div className={`reference-agent-result-heading is-${status}`}>
        <span className="reference-agent-result-avatar">
          <AgentAvatar agentId={stream.agent?.id || ""} />
        </span>
        <span className="signoff-run-agent">{stream.agent ? <AgentName agent={stream.agent} /> : c.working}</span>
        {live ? (
          <span className={pillClass("progress")}>
            <LoaderCircle className="reference-agent-spinner" size={11} />
            {status === "connecting" ? c.working : label(c.runStatus, status)}
          </span>
        ) : (
          <span className={pillClass(runTone[status as RunStatus] || "neutral")}>{label(c.runStatus, status)}</span>
        )}
      </div>
      <div className="reference-agent-meta">{runId}</div>
      {stream.reconnecting && <p className="reference-agent-error">{c.streamLost}</p>}
      <ol className="signoff-steps" aria-live="polite">
        {stream.steps.map((step) => (
          <li key={step.index} className={`signoff-step is-${step.status}`}>
            <span className="signoff-step-icon" aria-hidden="true">
              {step.status === "done" ? (
                <Check size={12} />
              ) : step.status === "running" ? (
                <LoaderCircle className="reference-agent-spinner" size={12} />
              ) : (
                <span className="signoff-step-dot" />
              )}
            </span>
            <div className="signoff-step-body">
              <div className="signoff-step-title">
                <strong>{step.label || step.tool.replaceAll("_", " ")}</strong>
                <small>
                  {step.status === "done" && step.duration_ms !== undefined
                    ? formatDuration(step.duration_ms, locale)
                    : step.status === "running"
                      ? c.stepRunning
                      : c.stepPending}
                </small>
              </div>
              {step.summary && <p>{step.summary}</p>}
              {step.refs.length > 0 && <RefChips refs={step.refs} onNavigate={onNavigate} />}
            </div>
          </li>
        ))}
      </ol>
      {stream.error && (
        <p className="reference-agent-error">
          <AlertCircle size={12} /> {stream.error}
        </p>
      )}
      {stream.summary && <p className="signoff-run-summary">{stream.summary}</p>}
      {stream.proposal && (
        <ProposalReview projectId={projectId} proposal={stream.proposal} onNavigate={onNavigate} notify={notify} />
      )}
    </div>
  );
}

/* ------------------------------------------------------------ proposals */
function useAllProposals(projectId: string) {
  const { locale } = useCopy();
  return useQuery({
    queryKey: [...keys.proposals(projectId, locale), "all"],
    queryFn: () => api.proposals(projectId, locale, "all"),
  });
}

function StandaloneProposal({
  projectId,
  proposalId,
  onOpenRun,
  onNavigate,
  notify,
}: {
  projectId: string;
  proposalId: string;
  onOpenRun: (runId: string) => void;
  onNavigate: (ref: Ref) => void;
  notify: (message: string) => void;
}) {
  const { c } = useCopy();
  const all = useAllProposals(projectId);
  const proposal = all.data?.find((item) => item.id === proposalId);
  if (all.isPending)
    return (
      <div className="reference-agent-loading">
        <LoaderCircle className="reference-agent-spinner" size={15} />
      </div>
    );
  if (!proposal) return <p className="reference-agent-empty">{c.noPending}</p>;
  return (
    <div className="reference-agent-result">
      <div className="reference-agent-result-heading">
        <span className="reference-agent-result-avatar">
          <AgentAvatar agentId={proposal.agent.id} />
        </span>
        <span className="signoff-run-agent">
          <AgentName agent={proposal.agent} />
        </span>
        <button className="signoff-link-button" onClick={() => onOpenRun(proposal.run_id)}>
          {proposal.run_id}
          <ChevronRight size={12} />
        </button>
      </div>
      <ProposalReview projectId={projectId} proposal={proposal} onNavigate={onNavigate} notify={notify} />
    </div>
  );
}

function ProposalReview({
  projectId,
  proposal,
  onNavigate,
  notify,
}: {
  projectId: string;
  proposal: Proposal;
  onNavigate: (ref: Ref) => void;
  notify: (message: string) => void;
}) {
  const { c } = useCopy();
  const all = useAllProposals(projectId);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const approve = useProjectMutation(projectId, () => api.approveProposal(projectId, proposal.id));
  const reject = useProjectMutation(projectId, () =>
    api.rejectProposal(projectId, proposal.id, reason || undefined),
  );
  const status =
    approve.data?.proposal.status ||
    reject.data?.proposal.status ||
    all.data?.find((item) => item.id === proposal.id)?.status ||
    proposal.status;
  const applied = approve.data?.applied || [];
  const busy = approve.isPending || reject.isPending;

  return (
    <section className={`signoff-proposal is-${status}`}>
      <header>
        <span className="reference-context-kicker">{label(c.proposalKind, proposal.kind)}</span>
        <span
          className={pillClass(status === "approved" ? "success" : status === "rejected" ? "error" : "warning")}
        >
          {label(c.proposalStatus, status)}
        </span>
      </header>
      <h3>{proposal.title}</h3>
      {proposal.requirement_id && (
        <RefChips
          refs={[{ type: "requirement", id: proposal.requirement_id, label: proposal.requirement_id }]}
          onNavigate={onNavigate}
        />
      )}
      {proposal.summary && <p className="signoff-proposal-summary">{proposal.summary}</p>}
      <ProposalBody proposal={proposal} c={c} onNavigate={onNavigate} />
      {status === "draft" && (
        <div className="signoff-proposal-actions">
          {rejecting && (
            <textarea
              aria-label={c.rejectReason}
              placeholder={c.rejectReason}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={2}
            />
          )}
          <div>
            {rejecting ? (
              <>
                <button className="reference-agent-ask" disabled={busy} onClick={() => setRejecting(false)}>
                  {c.back}
                </button>
                <button
                  className="signoff-danger-button"
                  disabled={busy}
                  onClick={() =>
                    reject.mutate(undefined, {
                      onSuccess: () => notify(c.proposalRejected),
                      onError: () => notify(c.proposalFailed),
                    })
                  }
                >
                  {reject.isPending ? <LoaderCircle className="reference-agent-spinner" size={14} /> : <X size={14} />}
                  {c.reject}
                </button>
              </>
            ) : (
              <>
                <button className="reference-agent-ask" disabled={busy} onClick={() => setRejecting(true)}>
                  <X size={14} />
                  {c.reject}
                </button>
                <button
                  className="reference-agent-approve"
                  disabled={busy}
                  onClick={() =>
                    approve.mutate(undefined, {
                      onSuccess: () => notify(c.proposalApplied),
                      onError: () => notify(c.proposalFailed),
                    })
                  }
                >
                  {approve.isPending ? (
                    <LoaderCircle className="reference-agent-spinner" size={14} />
                  ) : (
                    <Check size={14} />
                  )}
                  {proposal.kind === "report" ? c.acknowledge : c.approve}
                </button>
              </>
            )}
          </div>
        </div>
      )}
      {applied.length > 0 && (
        <div className="signoff-proposal-applied">
          <span>
            <Check size={12} /> {c.applied}
          </span>
          <RefChips refs={applied} onNavigate={onNavigate} />
        </div>
      )}
    </section>
  );
}

function ProposalBody({ proposal, c, onNavigate }: { proposal: Proposal; c: Copy; onNavigate: (ref: Ref) => void }) {
  switch (proposal.kind) {
    case "criteria": {
      const payload = proposal.payload as Partial<ProposalPayload["criteria"]>;
      const before = payload.before || [];
      const after = payload.after || [];
      const rows = [
        ...before.filter((line) => !after.includes(line)).map((text) => ({ text, kind: "removed" as const })),
        ...after.map((text) => ({ text, kind: before.includes(text) ? ("same" as const) : ("added" as const) })),
      ];
      return (
        <ul className="signoff-diff" aria-label={`${c.before} / ${c.after}`}>
          {rows.map((row, index) => (
            <li key={`${row.kind}-${index}`} className={`is-${row.kind}`}>
              {row.kind === "added" ? <Plus size={12} /> : row.kind === "removed" ? <Minus size={12} /> : <span />}
              <span>{row.text}</span>
            </li>
          ))}
        </ul>
      );
    }
    case "verification_plan": {
      const payload = proposal.payload as Partial<ProposalPayload["verification_plan"]>;
      return (
        <ol className="signoff-plan">
          {(payload.steps || []).map((step, index) => (
            <li key={index}>{step}</li>
          ))}
        </ol>
      );
    }
    case "evidence": {
      const payload = proposal.payload as Partial<ProposalPayload["evidence"]>;
      return (
        <div className="signoff-proposal-block">
          <div className="signoff-proposal-line">
            <strong>{payload.artifact}</strong>
            {payload.state && (
              <span className={pillClass(evidenceTone[payload.state] || "neutral")}>
                {label(c.evidenceState, payload.state)}
              </span>
            )}
          </div>
          {payload.summary && <p>{payload.summary}</p>}
          {payload.observations?.length ? (
            <>
              <span className="reference-context-kicker">{c.observations}</span>
              <ul className="signoff-bullets">
                {payload.observations.map((item, index) => (
                  <li key={index}>{item}</li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      );
    }
    case "change": {
      const payload = proposal.payload as Partial<ProposalPayload["change"]>;
      return (
        <div className="signoff-proposal-block">
          <strong>{payload.title}</strong>
          <dl className="signoff-defs">
            <dt>{c.original}</dt>
            <dd>{payload.original}</dd>
            <dt>{c.proposedLabel}</dt>
            <dd>{payload.proposed}</dd>
            <dt>{c.impact}</dt>
            <dd>{payload.impact}</dd>
          </dl>
          {payload.classification && (
            <span className={pillClass("warning")}>{payload.classification.replaceAll("_", " ")}</span>
          )}
        </div>
      );
    }
    case "comments": {
      const payload = proposal.payload as Partial<ProposalPayload["comments"]>;
      return (
        <ul className="signoff-comment-proposals">
          {(payload.items || []).map((item, index) => (
            <li key={index}>
              <RefChips
                refs={[{ type: "requirement", id: item.requirement_id, label: item.requirement_id }]}
                onNavigate={onNavigate}
              />
              <span>{item.text}</span>
            </li>
          ))}
        </ul>
      );
    }
    case "report": {
      const payload = proposal.payload as Partial<ProposalPayload["report"]>;
      return (
        <div className="signoff-proposal-block">
          {(payload.sections || []).map((section, index) => (
            <div key={index} className="signoff-report-section">
              <strong>{section.title}</strong>
              <p>{section.body}</p>
            </div>
          ))}
          {payload.refs?.length ? <RefChips refs={payload.refs} onNavigate={onNavigate} /> : null}
        </div>
      );
    }
    default:
      return null;
  }
}

export function RefChips({ refs, onNavigate }: { refs: Ref[]; onNavigate: (ref: Ref) => void }) {
  return (
    <span className="signoff-ref-chips">
      {refs.map((ref) => (
        <button key={`${ref.type}-${ref.id}`} className="signoff-ref-chip" onClick={() => onNavigate(ref)}>
          {ref.label || ref.id}
          <ChevronRight size={11} />
        </button>
      ))}
    </span>
  );
}

/* ------------------------------------------------------------- identity */
const agentIcons: Record<string, LucideIcon> = {
  "delivery-analyst": Route,
  "requirements-coach": ListChecks,
  "verification-planner": ClipboardCheck,
  "change-radar": GitCompareArrows,
  "agreement-analyst": FileSearch,
  "qa-explorer": MonitorCheck,
  "evidence-curator": FolderCheck,
  "acceptance-assistant": Stamp,
};

export function AgentAvatar({ agentId }: { agentId: string }) {
  const Icon = agentIcons[agentId] || Sparkles;
  return <Icon className="reference-agent-avatar" size={18} strokeWidth={1.6} aria-hidden="true" />;
}

function AgentBadge({ agentId }: { agentId: string }) {
  return (
    <span className="reference-agent-result-avatar">
      <AgentAvatar agentId={agentId} />
    </span>
  );
}

function AgentName({ agent }: { agent: { id: string; name: string } }) {
  const name = useAgentName();
  return <>{name(agent)}</>;
}

const spanishNames: Record<string, string> = {
  "delivery-analyst": "Analista de entrega",
  "requirements-coach": "Coach de requisitos",
  "verification-planner": "Planificador de verificación",
  "change-radar": "Radar de cambios",
  "agreement-analyst": "Analista de acuerdos",
  "qa-explorer": "Explorador QA",
  "evidence-curator": "Curador de evidencias",
  "acceptance-assistant": "Asistente de aceptación",
};

const spanishDescriptions: Record<string, string> = {
  "delivery-analyst": "Explica qué bloquea el release y cuál es la siguiente decisión.",
  "requirements-coach": "Propone criterios de aceptación atómicos y verificables.",
  "verification-planner": "Convierte un requisito en un plan de verificación acotado.",
  "change-radar": "Explica qué señales de cambio necesitan revisión humana.",
  "agreement-analyst": "Encuentra compromisos, ambigüedades y criterios faltantes.",
  "qa-explorer": "Comprueba la aplicación levantada y captura observaciones.",
  "evidence-curator": "Encuentra evidencias débiles, obsoletas o ausentes.",
  "acceptance-assistant": "Prepara un resumen para el cliente sin decidir por él.",
};

function agentDisplayName(id: string, name: string, locale: Locale, agents: AgentInfo[]) {
  if (locale === "en") return name;
  return agents.find((agent) => agent.id === id)?.name_es || spanishNames[id] || name;
}

function agentDescription(agent: AgentInfo, locale: Locale) {
  if (locale === "en") return agent.description;
  return agent.description_es || spanishDescriptions[agent.id] || agent.description;
}

/** Localized agent names, shared with the dashboard's notification list. */
export function useAgentName() {
  const { locale } = useCopy();
  const agents = useAgents();
  return useMemo(
    () => (agent: { id: string; name: string }) =>
      agentDisplayName(agent.id, agent.name, locale, agents.data || []),
    [agents.data, locale],
  );
}
