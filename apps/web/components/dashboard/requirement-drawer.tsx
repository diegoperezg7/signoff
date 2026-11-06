"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import {
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleCheck,
  ClipboardCheck,
  Download,
  ExternalLink,
  FileStack,
  Gauge,
  Link2,
  ListChecks,
  MessageCircle,
  MoreHorizontal,
  Play,
  X,
} from "lucide-react";
import { api, type RequirementDetail, type ScopeStatus } from "../../lib/api";
import { useProjectMutation, useRequirement } from "../../lib/queries";
import {
  acceptanceTone,
  changeTone,
  evidenceTone,
  formatDate,
  formatRelative,
  label,
  scopeTone,
  toneClass,
  useCopy,
  verificationTone,
} from "./copy";
import { Avatar, EvidenceUpload, Pill, Spinner, StatusText, downloadJson } from "./ui";

type DrawerTab = "details" | "verification" | "evidence" | "comments";

export function RequirementDrawer({
  projectId,
  requirementId,
  releaseName,
  onClose,
  onPrevious,
  onNext,
  onOpenVerification,
  onRunVerification,
  verifying,
  onStartAgent,
  agentStarting,
  notify,
}: {
  projectId: string;
  requirementId: string;
  releaseName: string;
  onClose: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onOpenVerification: () => void;
  onRunVerification: (ids: string[]) => void;
  verifying: boolean;
  onStartAgent: (agentId: string, requirementId: string) => void;
  agentStarting: boolean;
  notify: (message: string) => void;
}) {
  const { c, t } = useCopy();
  const detail = useRequirement(projectId, requirementId);
  const [tab, setTab] = useState<DrawerTab>("details");
  const [popover, setPopover] = useState<"" | "status" | "relations" | "more">("");
  const updateScope = useProjectMutation(projectId, (scope: ScopeStatus) =>
    api.updateRequirement(projectId, requirementId, { scope_status: scope }),
  );
  const requirement = detail.data;
  const openComments = requirement?.comments.filter((comment) => !comment.resolved).length ?? 0;

  async function copyId() {
    setPopover("");
    try {
      await navigator.clipboard.writeText(requirementId);
      notify(c.copied(requirementId));
    } catch {
      notify(c.copyFailed);
    }
  }

  return (
    <aside className="reference-drawer" aria-label={requirementId}>
      <div className="reference-drawer-header">
        <strong>{requirementId}</strong>
        <div>
          <button onClick={onPrevious} aria-label={t("previous")}>
            <ChevronLeft size={16} />
          </button>
          <button onClick={onNext} aria-label={t("next")}>
            <ChevronRight size={16} />
          </button>
          <span />
          <button onClick={onClose} aria-label={t("close")}>
            <X size={17} />
          </button>
        </div>
      </div>
      <div className="reference-drawer-content">
        {!requirement ? (
          <div className="reference-drawer-loading">
            {detail.isError ? c.detailUnavailable : <Spinner />}
          </div>
        ) : (
          <>
            <div className="reference-drawer-toolbar">
              <button
                className={`reference-pill pill-tone-${scopeTone[requirement.scope_status]}`}
                onClick={() => setPopover(popover === "status" ? "" : "status")}
                aria-expanded={popover === "status"}
                disabled={updateScope.isPending}
              >
                {updateScope.isPending ? (
                  <Spinner size={11} />
                ) : (
                  <span className={`status-dot ${toneClass[scopeTone[requirement.scope_status]]}`} />
                )}
                {label(c.scope, requirement.scope_status)}
                <ChevronDown size={12} />
              </button>
              <button
                aria-label={c.relationships}
                aria-expanded={popover === "relations"}
                onClick={() => setPopover(popover === "relations" ? "" : "relations")}
              >
                <Link2 size={15} />
              </button>
              <span className="reference-version">{requirement.version}</span>
              <button
                aria-label={c.moreActions}
                aria-expanded={popover === "more"}
                onClick={() => setPopover(popover === "more" ? "" : "more")}
              >
                <MoreHorizontal size={16} />
              </button>
              {popover === "status" && (
                <div className="reference-drawer-popover reference-drawer-more">
                  {(["agreed", "pending", "out_of_scope"] as ScopeStatus[]).map((scope) => (
                    <button
                      key={scope}
                      onClick={() => {
                        setPopover("");
                        if (scope === requirement.scope_status) return;
                        updateScope.mutate(scope, {
                          onSuccess: () => notify(c.scopeUpdated),
                          onError: () => notify(c.scopeFailed),
                        });
                      }}
                    >
                      <span className={`status-dot ${toneClass[scopeTone[scope]]}`} />
                      {label(c.scope, scope)}
                      {scope === requirement.scope_status && <Check size={13} />}
                    </button>
                  ))}
                </div>
              )}
              {popover === "relations" && (
                <div className="reference-drawer-popover">
                  <strong>{c.relationships}</strong>
                  <span>
                    {t("baseline")}: {requirement.baseline}
                  </span>
                  <span>{releaseName}</span>
                  {requirement.changes.map((change) => (
                    <span key={change.id}>
                      <i className={`status-dot ${toneClass[changeTone[change.status]]}`} /> {change.title}
                    </span>
                  ))}
                </div>
              )}
              {popover === "more" && (
                <div className="reference-drawer-popover reference-drawer-more">
                  <button onClick={copyId}>
                    <Link2 size={14} />
                    {c.copyId}
                  </button>
                  <button
                    onClick={() => {
                      setPopover("");
                      downloadJson(`${requirementId.toLowerCase()}-evidence.json`, {
                        requirement: requirementId,
                        release: releaseName,
                        evidence: requirement.evidence,
                        runs: requirement.runs,
                        generatedAt: new Date().toISOString(),
                      });
                      notify(c.evidenceExported);
                    }}
                  >
                    <Download size={14} />
                    {c.exportEvidence}
                  </button>
                </div>
              )}
            </div>
            <h2>{requirement.title}</h2>
            <p className="reference-drawer-description">{requirement.description}</p>
            <div className="reference-drawer-tabs" role="tablist">
              <DrawerTabButton active={tab === "details"} onClick={() => setTab("details")}>
                {t("details")}
              </DrawerTabButton>
              <DrawerTabButton active={tab === "verification"} onClick={() => setTab("verification")}>
                {t("verification")} ({requirement.runs.length})
              </DrawerTabButton>
              <DrawerTabButton active={tab === "evidence"} onClick={() => setTab("evidence")}>
                {t("evidence")} ({requirement.evidence.length})
              </DrawerTabButton>
              <DrawerTabButton active={tab === "comments"} onClick={() => setTab("comments")}>
                {c.commentsTab} ({openComments})
              </DrawerTabButton>
            </div>
            {tab === "details" && (
              <DetailsPanel
                requirement={requirement}
                onStartAgent={(agentId) => onStartAgent(agentId, requirementId)}
                agentStarting={agentStarting}
              />
            )}
            {tab === "verification" && (
              <VerificationPanel
                requirement={requirement}
                running={verifying}
                onRun={() => onRunVerification([requirementId])}
                onOpen={onOpenVerification}
              />
            )}
            {tab === "evidence" && (
              <EvidencePanel projectId={projectId} requirement={requirement} notify={notify} />
            )}
            {tab === "comments" && (
              <CommentsPanel projectId={projectId} requirement={requirement} notify={notify} />
            )}
          </>
        )}
        <button className="reference-drawer-cta" onClick={onOpenVerification}>
          <span>{t("viewVerification")}</span>
          <ChevronRight size={18} />
        </button>
      </div>
    </aside>
  );
}

function DrawerTabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button role="tab" aria-selected={active} className={active ? "is-active" : ""} onClick={onClick}>
      {children}
    </button>
  );
}

function DetailsPanel({
  requirement,
  onStartAgent,
  agentStarting,
}: {
  requirement: RequirementDetail;
  onStartAgent: (agentId: string) => void;
  agentStarting: boolean;
}) {
  const { c, t, locale } = useCopy();
  return (
    <>
      <div className="reference-detail-list">
        <Detail label={t("type")} value={label(c.requirementType, requirement.type)} />
        <Detail label={t("priority")} value={label(c.priority, requirement.priority)} tone="priority" />
        <Detail label={t("component")} value={requirement.component} />
        <Detail label={t("baseline")} value={requirement.baseline} accent />
        <Detail label={t("createdLabel")} value={formatDate(requirement.created_at, locale)} />
        <Detail label={t("agreedLabel")} value={formatDate(requirement.agreed_at, locale)} />
        <div>
          <span>{t("owner")}</span>
          <strong className="is-owner">
            <Avatar actor={requirement.owner} size="sm" />
            {requirement.owner?.name}
          </strong>
        </div>
        <div>
          <span>{c.acceptanceLabel}</span>
          <strong>
            <StatusText tone={acceptanceTone[requirement.acceptance]}>
              {label(c.acceptance, requirement.acceptance)}
            </StatusText>
          </strong>
        </div>
      </div>
      <div className="reference-criteria">
        <div className="signoff-section-heading">
          <h3>{t("acceptanceCriteria")}</h3>
          <button
            className="signoff-link-button"
            onClick={() => onStartAgent("requirements-coach")}
            disabled={agentStarting}
          >
            {agentStarting ? <Spinner size={12} /> : <ListChecks size={13} />}
            {c.improveCriteria}
          </button>
        </div>
        {requirement.criteria.length ? (
          requirement.criteria.map((criterion) => (
            <div key={criterion.id}>
              <CircleCheck size={15} />
              <span>{criterion.text}</span>
              {criterion.source !== "baseline" && (
                <small className="signoff-source-tag">{label(c.criterionSource, criterion.source)}</small>
              )}
            </div>
          ))
        ) : (
          <p className="signoff-empty-text">{c.noCriteria}</p>
        )}
      </div>
      <div className="reference-criteria signoff-plan-block">
        <div className="signoff-section-heading">
          <h3>{c.verificationPlan}</h3>
          {!requirement.verification_plan && (
            <button
              className="signoff-link-button"
              onClick={() => onStartAgent("verification-planner")}
              disabled={agentStarting}
            >
              {agentStarting ? <Spinner size={12} /> : <ClipboardCheck size={13} />}
              {c.planWithAgent}
            </button>
          )}
        </div>
        {requirement.verification_plan?.steps.length ? (
          <ol className="signoff-plan">
            {requirement.verification_plan.steps.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ol>
        ) : (
          <p className="signoff-empty-text">{c.noPlan}</p>
        )}
      </div>
    </>
  );
}

function VerificationPanel({
  requirement,
  running,
  onRun,
  onOpen,
}: {
  requirement: RequirementDetail;
  running: boolean;
  onRun: () => void;
  onOpen: () => void;
}) {
  const { c, locale } = useCopy();
  const last = requirement.runs[0];
  return (
    <section className="reference-drawer-panel">
      <div className="reference-panel-status">
        <span>{c.lastRun}</span>
        <strong>{last ? formatRelative(last.at, locale) : c.never}</strong>
      </div>
      <div className="reference-panel-list">
        <div>
          <CircleCheck size={14} />
          <span>{c.result}</span>
          <strong>
            <StatusText tone={verificationTone[requirement.verification]}>
              {label(c.verification, requirement.verification)}
            </StatusText>
          </strong>
        </div>
        <div>
          <ListChecks size={14} />
          <span>{c.criteriaCovered}</span>
          <strong>{last ? `${last.criteria_covered}/${last.criteria_total}` : `0/${requirement.criteria_count}`}</strong>
        </div>
        <div>
          <Gauge size={14} />
          <span>{c.table.coverage}</span>
          <strong>{requirement.coverage}%</strong>
        </div>
      </div>
      {running && (
        <p className="signoff-running-note">
          <Spinner size={13} />
          {c.running}
        </p>
      )}
      {requirement.runs.length > 0 && (
        <div className="signoff-run-history">
          <span className="reference-context-kicker">{c.runHistory}</span>
          {requirement.runs.slice(0, 5).map((run) => (
            <div key={run.id}>
              <StatusText tone={verificationTone[run.result]}>{label(c.verification, run.result)}</StatusText>
              <small>
                {run.criteria_covered}/{run.criteria_total} · {run.coverage}%
              </small>
              <time dateTime={run.at}>{formatRelative(run.at, locale)}</time>
            </div>
          ))}
        </div>
      )}
      <div className="reference-drawer-actions">
        <button onClick={onRun} disabled={running}>
          {running ? <Spinner /> : <Play size={14} />}
          <span>{running ? c.running : c.runVerification}</span>
        </button>
        <button onClick={onOpen}>
          <ExternalLink size={14} />
          {c.openReport}
        </button>
      </div>
    </section>
  );
}

function EvidencePanel({
  projectId,
  requirement,
  notify,
}: {
  projectId: string;
  requirement: RequirementDetail;
  notify: (message: string) => void;
}) {
  const { c, locale } = useCopy();
  async function open(artifact: string) {
    try {
      window.open(await api.evidenceUrl(projectId, artifact), "_blank", "noopener,noreferrer");
    } catch {
      notify(c.linkUnavailable);
    }
  }
  return (
    <section className="reference-drawer-panel">
      <div className="reference-panel-status">
        <span>{c.table.evidence}</span>
        <strong>{requirement.evidence.length}</strong>
      </div>
      <div className="reference-panel-list">
        {requirement.evidence.length ? (
          requirement.evidence.map((item) => (
            <div key={item.id} className="signoff-evidence-item">
              <FileStack size={14} />
              <span>
                <b>{item.artifact}</b>
                <small>
                  {label(c.evidenceKind, item.kind)} · {formatRelative(item.created_at, locale)} ·{" "}
                  <code title={item.sha256}>{item.sha256.slice(0, 10)}</code>
                </small>
              </span>
              <Pill tone={evidenceTone[item.state]}>{label(c.evidenceState, item.state)}</Pill>
              <button onClick={() => open(item.artifact)} aria-label={c.openArtifact(item.artifact)}>
                <ExternalLink size={13} />
              </button>
            </div>
          ))
        ) : (
          <p className="signoff-empty-text">{c.noEvidence}</p>
        )}
      </div>
      <EvidenceUpload
        projectId={projectId}
        requirementIds={[requirement.id]}
        defaultRequirementId={requirement.id}
        notify={notify}
        compact
      />
    </section>
  );
}

function CommentsPanel({
  projectId,
  requirement,
  notify,
}: {
  projectId: string;
  requirement: RequirementDetail;
  notify: (message: string) => void;
}) {
  const { c, locale } = useCopy();
  const [draft, setDraft] = useState("");
  const add = useProjectMutation(projectId, (text: string) => api.addComment(projectId, requirement.id, text));
  const resolve = useProjectMutation(projectId, (commentId: string) => api.resolveComment(projectId, commentId));
  const open = requirement.comments.filter((comment) => !comment.resolved).length;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    add.mutate(text, {
      onSuccess: () => {
        setDraft("");
        notify(c.commentAdded);
      },
      onError: () => notify(c.commentFailed),
    });
  }

  return (
    <section className="reference-drawer-panel">
      <div className="reference-panel-status">
        <span>{c.openComments}</span>
        <strong>{open}</strong>
      </div>
      <div className="reference-comment-list">
        {requirement.comments.length ? (
          requirement.comments.map((comment) => (
            <div className={`reference-comment signoff-comment${comment.resolved ? " is-resolved" : ""}`} key={comment.id}>
              <div className="signoff-comment-head">
                <Avatar actor={comment.author} size="sm" />
                <strong>{comment.author.name}</strong>
                <time dateTime={comment.created_at}>{formatRelative(comment.created_at, locale)}</time>
              </div>
              <p>{comment.text}</p>
              {comment.resolved ? (
                <small className="signoff-resolved">
                  <Check size={11} /> {c.resolved}
                </small>
              ) : (
                <button
                  className="signoff-link-button"
                  disabled={resolve.isPending && resolve.variables === comment.id}
                  onClick={() => resolve.mutate(comment.id)}
                >
                  {resolve.isPending && resolve.variables === comment.id ? <Spinner size={11} /> : <Check size={12} />}
                  {c.resolve}
                </button>
              )}
            </div>
          ))
        ) : (
          <p className="signoff-empty-text">{c.noComments}</p>
        )}
      </div>
      <form className="reference-comment-form" onSubmit={submit}>
        <textarea
          aria-label={c.newComment}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={c.commentPlaceholder}
        />
        <button type="submit" disabled={add.isPending || !draft.trim()}>
          {add.isPending ? <Spinner size={13} /> : <MessageCircle size={14} />}
          {c.addComment}
        </button>
      </form>
    </section>
  );
}

function Detail({
  label: name,
  value,
  accent = false,
  tone = "",
}: {
  label: string;
  value: string;
  accent?: boolean;
  tone?: string;
}) {
  return (
    <div>
      <span>{name}</span>
      <strong className={`${accent ? "is-accent" : ""} ${tone}`}>{value}</strong>
    </div>
  );
}
