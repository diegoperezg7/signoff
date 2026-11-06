"use client";

import { useMemo, useState } from "react";
import {
  Check,
  CircleAlert,
  Download,
  ExternalLink,
  ListChecks,
  PanelsTopLeft,
  Play,
  RefreshCw,
  Search,
  Send,
  X,
} from "lucide-react";
import {
  api,
  type Dashboard,
  type DeliveryChecks,
  type RequirementRow,
  type Tone,
} from "../../lib/api";
import { useChanges, useEvidence, useProjectMutation, useReadiness } from "../../lib/queries";
import { StackedBar, VerificationBars } from "./charts";
import {
  acceptanceTone,
  changeTone,
  evidenceTone,
  formatDate,
  formatRelative,
  label,
  releaseTone,
  scopeTone,
  useCopy,
  verificationTone,
  type Copy,
} from "./copy";
import { EvidenceUpload, Pill, Spinner, StatusText, downloadJson } from "./ui";

export type Tab = "overview" | "requirements" | "changes" | "verification" | "evidence" | "signoff";

type ListTab = "requirements" | "verification" | "signoff";

export function TabView({
  tab,
  projectId,
  data,
  requirements,
  requirementsLoading,
  selectedId,
  onSelect,
  onRunVerification,
  verifyingIds,
  onStartAgent,
  agentStarting,
  onSendForAcceptance,
  sending,
  onOpenPortal,
  notify,
}: {
  tab: Exclude<Tab, "overview">;
  projectId: string;
  data: Dashboard;
  requirements: RequirementRow[];
  requirementsLoading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRunVerification: (ids: string[]) => void;
  verifyingIds: string[];
  onStartAgent: (agentId: string, requirementId: string) => void;
  agentStarting: boolean;
  onSendForAcceptance: () => void;
  sending: boolean;
  onOpenPortal: () => void;
  notify: (message: string) => void;
}) {
  const { c, t, locale } = useCopy();
  const prepare = useProjectMutation(projectId, () => api.prepareDelivery(projectId, locale));
  const status = data.project.status;
  const target = selectedId || requirements[0]?.id || null;

  return (
    <div className="reference-tab-view">
      <div className="reference-tab-view-heading">
        <div>
          <span>{data.project.release}</span>
          <h2>{t(tab)}</h2>
        </div>
        <Pill tone={releaseTone[status] || "neutral"}>{label(c.release, status)}</Pill>
      </div>
      <div className="reference-tab-actions">
        {tab === "requirements" && target && (
          <button className="is-success" disabled={agentStarting} onClick={() => onStartAgent("requirements-coach", target)}>
            {agentStarting ? <Spinner /> : <ListChecks size={14} />}
            {c.improveCriteria} · {target}
          </button>
        )}
        {tab === "verification" && target && (
          <button
            className="is-success"
            disabled={verifyingIds.length > 0}
            onClick={() => onRunVerification([target])}
          >
            {verifyingIds.length ? <Spinner /> : <Play size={14} />}
            {verifyingIds.length ? c.running : `${c.runVerification} · ${target}`}
          </button>
        )}
        {tab === "signoff" && (
          <>
            <button onClick={() => prepare.mutate()} disabled={prepare.isPending}>
              {prepare.isPending ? <Spinner /> : <PanelsTopLeft size={14} />}
              {prepare.isPending ? c.preparing : c.prepareDelivery}
            </button>
            <button className="is-success" onClick={onSendForAcceptance} disabled={sending || status === "ready"}>
              {sending ? <Spinner /> : <Send size={14} />}
              {c.sendForAcceptance}
            </button>
            <button onClick={onOpenPortal}>
              <ExternalLink size={14} />
              {c.openPortal}
            </button>
          </>
        )}
      </div>
      <div className="reference-tab-view-grid">
        {tab === "changes" ? (
          <ChangesList projectId={projectId} notify={notify} />
        ) : tab === "evidence" ? (
          <EvidenceList
            projectId={projectId}
            requirementIds={requirements.map((row) => row.id)}
            selectedId={selectedId}
            onSelect={onSelect}
            notify={notify}
          />
        ) : (
          <RequirementList
            tab={tab}
            rows={requirements}
            loading={requirementsLoading}
            selectedId={selectedId}
            onSelect={onSelect}
            verifyingIds={verifyingIds}
          />
        )}
        <SideSummary tab={tab} projectId={projectId} data={data} checks={prepare.data || null} />
      </div>
    </div>
  );
}

/* ---------------------------------------------------- requirement lists */
const filterKeys: Record<ListTab, string[]> = {
  requirements: ["agreed", "pending", "out_of_scope"],
  verification: ["passed", "failed", "in_progress", "not_started"],
  signoff: ["accepted", "pending", "revision_requested", "rejected"],
};

function filterValue(tab: ListTab, row: RequirementRow) {
  return tab === "requirements" ? row.scope_status : tab === "verification" ? row.verification : row.acceptance;
}

function filterLabel(tab: ListTab, key: string, c: Copy) {
  return tab === "requirements"
    ? label(c.scope, key)
    : tab === "verification"
      ? label(c.verification, key)
      : label(c.acceptance, key);
}

function RequirementList({
  tab,
  rows,
  loading,
  selectedId,
  onSelect,
  verifyingIds,
}: {
  tab: ListTab;
  rows: RequirementRow[];
  loading: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
  verifyingIds: string[];
}) {
  const { c } = useCopy();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    rows.forEach((row) => {
      const key = filterValue(tab, row);
      result[key] = (result[key] || 0) + 1;
    });
    return result;
  }, [rows, tab]);
  const needle = query.trim().toLowerCase();
  const visible = rows.filter(
    (row) =>
      (filter === "all" || filterValue(tab, row) === filter) &&
      (!needle || `${row.id} ${row.title} ${row.component}`.toLowerCase().includes(needle)),
  );

  return (
    <article className="reference-card signoff-list-card">
      <p>{c.tabIntro[tab]}</p>
      <div className="signoff-list-tools">
        <label className="signoff-filter-search">
          <Search size={14} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={c.filterPlaceholder}
            aria-label={c.filterPlaceholder}
          />
        </label>
        <div className="signoff-chips" role="group">
          <button className={filter === "all" ? "is-active" : ""} aria-pressed={filter === "all"} onClick={() => setFilter("all")}>
            {c.filterAll} <b>{rows.length}</b>
          </button>
          {filterKeys[tab].map((key) => (
            <button
              key={key}
              className={filter === key ? "is-active" : ""}
              aria-pressed={filter === key}
              onClick={() => setFilter(key)}
            >
              {filterLabel(tab, key, c)} <b>{counts[key] || 0}</b>
            </button>
          ))}
        </div>
        <small className="signoff-list-count">{c.showing(visible.length, rows.length)}</small>
      </div>
      <div className={`signoff-table is-${tab}`}>
        <div className="signoff-table-row signoff-table-head">
          <span>{c.table.id}</span>
          <span>{c.table.title}</span>
          {tab === "requirements" && (
            <>
              <span>{c.table.priority}</span>
              <span>{c.table.criteria}</span>
              <span>{c.table.status}</span>
            </>
          )}
          {tab === "verification" && (
            <>
              <span>{c.table.verification}</span>
              <span>{c.table.coverage}</span>
              <span>{c.table.evidence}</span>
            </>
          )}
          {tab === "signoff" && (
            <>
              <span>{c.table.verification}</span>
              <span>{c.table.acceptance}</span>
              <span>{c.commentsTab}</span>
            </>
          )}
        </div>
        <div className="signoff-table-body">
          {loading && !rows.length ? (
            <div className="reference-empty">
              <Spinner />
            </div>
          ) : visible.length ? (
            visible.map((row) => (
              <button
                key={row.id}
               
                className={`signoff-table-row${row.id === selectedId ? " is-selected" : ""}`}
                onClick={() => onSelect(row.id)}
              >
                <span className="reference-req-id">{row.id}</span>
                <span className="signoff-cell-title">
                  <strong>{row.title}</strong>
                  <small>{row.component}</small>
                </span>
                {tab === "requirements" && (
                  <>
                    <span className={`signoff-priority is-${row.priority}`}>{label(c.priority, row.priority)}</span>
                    <span className="signoff-num">{row.criteria_count}</span>
                    <span>
                      <Pill tone={scopeTone[row.scope_status]}>{label(c.scope, row.scope_status)}</Pill>
                    </span>
                  </>
                )}
                {tab === "verification" && (
                  <>
                    <span>
                      {verifyingIds.includes(row.id) ? (
                        <span className="reference-verification-status">
                          <Spinner size={11} /> {c.running}
                        </span>
                      ) : (
                        <StatusText tone={verificationTone[row.verification]}>
                          {label(c.verification, row.verification)}
                        </StatusText>
                      )}
                    </span>
                    <span className="reference-coverage-cell">
                      <span>{row.coverage}%</span>
                      <span className="signoff-meter">
                        <span style={{ width: `${row.coverage}%` }} />
                      </span>
                    </span>
                    <span className="signoff-num">{row.evidence_count}</span>
                  </>
                )}
                {tab === "signoff" && (
                  <>
                    <span>
                      <StatusText tone={verificationTone[row.verification]}>
                        {label(c.verification, row.verification)}
                      </StatusText>
                    </span>
                    <span>
                      <Pill tone={acceptanceTone[row.acceptance]}>{label(c.acceptance, row.acceptance)}</Pill>
                    </span>
                    <span className="signoff-num">{row.open_comments}</span>
                  </>
                )}
              </button>
            ))
          ) : (
            <div className="reference-empty">{c.searchEmpty}</div>
          )}
        </div>
      </div>
    </article>
  );
}

/* --------------------------------------------------------------- changes */
function ChangesList({ projectId, notify }: { projectId: string; notify: (message: string) => void }) {
  const { c, locale } = useCopy();
  const changes = useChanges(projectId);
  const [filter, setFilter] = useState("all");
  const update = useProjectMutation(projectId, (vars: { id: string; status: "approved" | "rejected" }) =>
    api.updateChange(projectId, vars.id, vars.status),
  );
  const rows = changes.data || [];
  const visible = rows.filter((row) => filter === "all" || row.status === filter);
  const busyId = update.isPending ? update.variables?.id : null;

  return (
    <article className="reference-card signoff-list-card">
      <p>{c.tabIntro.changes}</p>
      <div className="signoff-list-tools">
        <div className="signoff-chips" role="group">
          {["all", "proposed", "approved", "rejected"].map((key) => (
            <button key={key} className={filter === key ? "is-active" : ""} aria-pressed={filter === key} onClick={() => setFilter(key)}>
              {key === "all" ? c.filterAll : label(c.change, key)}{" "}
              <b>{key === "all" ? rows.length : rows.filter((row) => row.status === key).length}</b>
            </button>
          ))}
        </div>
        <button className="signoff-icon-button" onClick={() => changes.refetch()} aria-label="Refresh">
          <RefreshCw size={14} className={changes.isFetching ? "reference-spin" : ""} />
        </button>
      </div>
      <div className="signoff-change-list">
        {changes.isPending ? (
          <div className="reference-empty">
            <Spinner />
          </div>
        ) : visible.length ? (
          visible.map((change) => (
            <div className={`signoff-change is-${change.status}`} key={change.id}>
              <div className="signoff-change-main">
                <div className="signoff-change-title">
                  <span className="reference-req-id">{change.code}</span>
                  <strong>{change.title}</strong>
                  <Pill tone={changeTone[change.status]}>{label(c.change, change.status)}</Pill>
                </div>
                <dl className="signoff-defs">
                  <dt>{c.original}</dt>
                  <dd>{change.original}</dd>
                  <dt>{c.proposedLabel}</dt>
                  <dd>{change.proposed}</dd>
                  <dt>{c.impact}</dt>
                  <dd>{change.impact}</dd>
                </dl>
                <small className="signoff-meta-line">
                  {label(c.changeSource, change.source)} · {change.classification.replaceAll("_", " ")} ·{" "}
                  {formatDate(change.created_at, locale)}
                  {change.requirement_ids.length ? ` · ${change.requirement_ids.join(", ")}` : ""}
                  {change.decided_by ? ` · ${c.decidedBy(change.decided_by.name)}` : ""}
                </small>
              </div>
              {change.status === "proposed" && (
                <div className="reference-row-actions signoff-change-actions">
                  <button
                    className="signoff-approve"
                    disabled={busyId === change.id}
                    onClick={() =>
                      update.mutate(
                        { id: change.id, status: "approved" },
                        { onSuccess: () => notify(c.changeUpdated), onError: () => notify(c.changeFailed) },
                      )
                    }
                  >
                    {busyId === change.id && update.variables?.status === "approved" ? <Spinner size={12} /> : <Check size={14} />}
                    {c.approve}
                  </button>
                  <button
                    className="signoff-reject"
                    disabled={busyId === change.id}
                    onClick={() =>
                      update.mutate(
                        { id: change.id, status: "rejected" },
                        { onSuccess: () => notify(c.changeUpdated), onError: () => notify(c.changeFailed) },
                      )
                    }
                  >
                    {busyId === change.id && update.variables?.status === "rejected" ? <Spinner size={12} /> : <X size={14} />}
                    {c.reject}
                  </button>
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="reference-empty">{c.noChanges}</div>
        )}
      </div>
    </article>
  );
}

/* -------------------------------------------------------------- evidence */
function EvidenceList({
  projectId,
  requirementIds,
  selectedId,
  onSelect,
  notify,
}: {
  projectId: string;
  requirementIds: string[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  notify: (message: string) => void;
}) {
  const { c, locale } = useCopy();
  const evidence = useEvidence(projectId);
  const rows = evidence.data || [];

  async function open(artifact: string) {
    try {
      window.open(await api.evidenceUrl(projectId, artifact), "_blank", "noopener,noreferrer");
    } catch {
      notify(c.linkUnavailable);
    }
  }

  return (
    <article className="reference-card signoff-list-card">
      <p>{c.tabIntro.evidence}</p>
      <EvidenceUpload
        key={selectedId || "none"}
        projectId={projectId}
        requirementIds={requirementIds}
        defaultRequirementId={selectedId}
        notify={notify}
      />
      <div className="signoff-list-tools">
        <small className="signoff-list-count">{rows.length}</small>
        <button
          className="signoff-text-button"
          disabled={!rows.length}
          onClick={() => {
            downloadJson(`${projectId}-evidence-index.json`, { evidence: rows, generatedAt: new Date().toISOString() });
            notify(c.evidenceExported);
          }}
        >
          <Download size={14} />
          {c.downloadIndex}
        </button>
      </div>
      <div className="signoff-evidence-list">
        {evidence.isPending ? (
          <div className="reference-empty">
            <Spinner />
          </div>
        ) : rows.length ? (
          rows.map((item) => (
            <div className="signoff-evidence-row" key={item.id}>
              <button className="reference-req-id signoff-req-link" onClick={() => onSelect(item.requirement_id)}>
                {item.requirement_id}
              </button>
              <span className="signoff-cell-title">
                <strong>{item.artifact}</strong>
                <small>
                  {item.summary} · {label(c.evidenceKind, item.kind)} · {label(c.evidenceSource, item.source)} ·{" "}
                  {formatRelative(item.created_at, locale)} · <code title={item.sha256}>{item.sha256.slice(0, 10)}</code>
                </small>
              </span>
              <Pill tone={evidenceTone[item.state]}>{label(c.evidenceState, item.state)}</Pill>
              <button className="signoff-icon-button" onClick={() => open(item.artifact)} aria-label={c.openArtifact(item.artifact)}>
                <ExternalLink size={14} />
              </button>
            </div>
          ))
        ) : (
          <div className="reference-empty">{c.noEvidence}</div>
        )}
      </div>
    </article>
  );
}

/* ---------------------------------------------------------- side summary */
function SideSummary({
  tab,
  projectId,
  data,
  checks,
}: {
  tab: Exclude<Tab, "overview">;
  projectId: string;
  data: Dashboard;
  checks: DeliveryChecks | null;
}) {
  const { c, t } = useCopy();
  const readiness = useReadiness(projectId, tab === "signoff");
  const evidence = useEvidence(projectId, tab === "evidence");
  const metricItems = (key: "requirements" | "changes", map: Record<string, string>) =>
    data.metrics[key].items.map((item) => ({
      key: item.key,
      label: label(map, item.key),
      value: item.value,
      tone: item.tone as Tone,
    }));

  return (
    <article className="reference-card reference-tab-side">
      {tab === "requirements" && (
        <>
          <span className="reference-tab-side-number">{data.metrics.requirements.value}</span>
          <strong>{t("requirements")}</strong>
          <StackedBar items={metricItems("requirements", c.metricItem)} />
        </>
      )}
      {tab === "changes" && (
        <>
          <span className="reference-tab-side-number">{data.metrics.changes.value}</span>
          <strong>{t("changes")}</strong>
          <StackedBar items={metricItems("changes", c.metricItem)} />
        </>
      )}
      {tab === "verification" && (
        <>
          <span className="reference-tab-side-number">{data.metrics.verification.value}%</span>
          <strong>{t("verification")}</strong>
          <VerificationBars
            items={data.verification_status.map((item) => ({
              key: item.key,
              label: label(c.verification, item.key),
              value: item.value,
              tone: item.tone,
            }))}
          />
        </>
      )}
      {tab === "evidence" && (
        <>
          <span className="reference-tab-side-number">{evidence.data?.length ?? "—"}</span>
          <strong>{t("evidence")}</strong>
          <small>
            {t("coverage")}: {data.metrics.coverage.value}%
          </small>
        </>
      )}
      {tab === "signoff" && (
        <>
          <span className="reference-tab-side-number">{readiness.data ? readiness.data.score : "—"}</span>
          <strong>{c.readinessScore}</strong>
          <small>{label(c.release, data.project.status)}</small>
          {readiness.data && (
            <dl className="signoff-defs signoff-readiness">
              <dt>{c.verification.passed}</dt>
              <dd>
                {readiness.data.demonstrated}/{readiness.data.total_requirements}
              </dd>
              <dt>{c.noEvidence}</dt>
              <dd>{readiness.data.without_evidence}</dd>
              <dt>{c.change.proposed}</dt>
              <dd>{readiness.data.unapproved_scope_changes}</dd>
              <dt>{c.openComments}</dt>
              <dd>{readiness.data.unresolved_comments}</dd>
            </dl>
          )}
          {checks && (
            <div className="reference-delivery-checks">
              <Pill tone={checks.ready ? "success" : "warning"}>
                {checks.ready ? c.deliveryReady : c.deliveryAttention}
              </Pill>
              {checks.checks.map((check) => (
                <small key={check.key} className={`signoff-check is-${check.status}`}>
                  {check.status === "ready" ? <Check size={12} /> : <CircleAlert size={12} />}
                  <span>
                    <b>{check.label}</b>
                    {check.detail}
                  </span>
                </small>
              ))}
            </div>
          )}
        </>
      )}
      <small>{data.project.release}</small>
    </article>
  );
}

