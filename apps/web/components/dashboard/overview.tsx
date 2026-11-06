"use client";

import type { KeyboardEvent, ReactNode } from "react";
import { ChevronRight, CircleCheck, FileStack, Gauge, PanelsTopLeft, Send, Workflow } from "lucide-react";
import { useReadiness } from "../../lib/queries";
import type { ActivityItem, Dashboard, Ref, RequirementRow, Tone } from "../../lib/api";
import {
  AnimatedNumber,
  CoverageTrendChart,
  MiniRing,
  Sparkline,
  StackedBar,
  VerificationBars,
  useAnimatedValue,
} from "./charts";
import {
  formatRelative,
  label,
  releaseTone,
  scopeTone,
  toneClass,
  useCopy,
  verificationTone,
} from "./copy";
import type { Tab } from "./tab-views";
import { Avatar, Pill, Spinner, StatusText } from "./ui";

/* ------------------------------------------------------------------ KPIs */
export function KpiRow({ data, onOpenTab }: { data: Dashboard; onOpenTab?: (tab: Tab) => void }) {
  const { c, t } = useCopy();
  const items = (key: "requirements" | "changes") =>
    data.metrics[key].items.map((item) => ({
      key: item.key,
      label: label(c.metricItem, item.key),
      value: item.value,
      tone: item.tone as Tone,
    }));
  const verification = data.metrics.verification;
  const coverage = data.metrics.coverage;
  const delta = coverage.items.find((item) => item.key === "vs_previous_run");

  return (
    <div className="reference-metrics">
      <MetricCard
        title={t("requirementCount")}
        value={data.metrics.requirements.value}
        icon={FileStack}
        onClick={onOpenTab && (() => onOpenTab("requirements"))}
      >
        <StackedBar items={items("requirements")} />
      </MetricCard>
      <MetricCard
        title={t("verificationCount")}
        value={verification.value}
        suffix="%"
        icon={CircleCheck}
        onClick={onOpenTab && (() => onOpenTab("verification"))}
        aside={<MiniRing value={verification.value} />}
      >
        <div className="reference-metric-items">
          {verification.items.map((item) => (
            <span key={item.key}>
              <i className={`status-dot ${toneClass[item.tone]}`} />
              <b>
                <AnimatedNumber value={item.value} />
              </b>{" "}
              {label(c.metricItem, item.key)}
            </span>
          ))}
        </div>
      </MetricCard>
      <MetricCard
        title={t("coverageCount")}
        value={coverage.value}
        suffix="%"
        icon={Gauge}
        onClick={onOpenTab && (() => onOpenTab("evidence"))}
      >
        <Sparkline values={data.coverage_trend.map((point) => point.value)} />
        <div className="reference-metric-items">
          <span>
            <i className={`status-dot ${toneClass[delta?.tone || "neutral"]}`} />
            {delta ? c.ptsVsPrevious(delta.value) : c.firstRun}
          </span>
        </div>
      </MetricCard>
      <MetricCard
        title={t("changesCount")}
        value={data.metrics.changes.value}
        icon={Workflow}
        onClick={onOpenTab && (() => onOpenTab("changes"))}
      >
        <StackedBar items={items("changes")} />
      </MetricCard>
    </div>
  );
}

function MetricCard({
  title,
  value,
  suffix = "",
  icon: Icon,
  onClick,
  aside,
  children,
}: {
  title: string;
  value: number;
  suffix?: string;
  icon: typeof FileStack;
  onClick?: () => void;
  aside?: ReactNode;
  children: ReactNode;
}) {
  const { display, changed } = useAnimatedValue(value);
  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (onClick && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      onClick();
    }
  }
  return (
    <article
      className={`reference-metric-card${onClick ? " is-interactive" : ""}${changed ? " is-changed" : ""}`}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className="reference-metric-top">
        <span>{title}</span>
        <span className="reference-metric-icon">
          <Icon size={18} strokeWidth={1.45} />
        </span>
      </div>
      <strong className="reference-metric-value" aria-label={`${value}${suffix}`}>
        <span aria-hidden="true">
          {display}
          {suffix}
        </span>
      </strong>
      {aside}
      {children}
    </article>
  );
}

/* -------------------------------------------------------------- overview */
export function Overview({
  data,
  selectedId,
  onSelect,
  onOpenTab,
  onNavigateRef,
  projectId,
  onSendForAcceptance,
  sending,
}: {
  data: Dashboard;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onOpenTab: (tab: Tab) => void;
  onNavigateRef: (ref: Ref) => void;
  projectId: string;
  onSendForAcceptance: () => void;
  sending: boolean;
}) {
  const { c, t } = useCopy();
  return (
    <>
      <KpiRow data={data} onOpenTab={onOpenTab} />
      <div className="reference-content-grid">
        <div className="reference-main-column">
          <div className="reference-requirements-row">
            <AttentionTable rows={data.requirements} selectedId={selectedId} onSelect={onSelect} />
            <ReleaseCard
              projectId={projectId}
              data={data}
              onOpenTab={onOpenTab}
              onSendForAcceptance={onSendForAcceptance}
              sending={sending}
            />
          </div>
          <div className="signoff-chart-grid">
            <CoverageTrendCard trend={data.coverage_trend} />
            <article className="reference-card signoff-chart-card">
              <div className="reference-card-heading">
                <h2>{t("verificationStatus")}</h2>
                <button className="signoff-link-button" onClick={() => onOpenTab("verification")}>
                  {c.viewAll}
                  <ChevronRight size={13} />
                </button>
              </div>
              <VerificationBars
                items={data.verification_status.map((item) => ({
                  key: item.key,
                  label: label(c.verification, item.key),
                  value: item.value,
                  tone: item.tone,
                }))}
              />
            </article>
          </div>
          <ActivityCard items={data.activity} onNavigateRef={onNavigateRef} />
        </div>
      </div>
    </>
  );
}

function AttentionTable({
  rows,
  selectedId,
  onSelect,
}: {
  rows: RequirementRow[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { c } = useCopy();
  return (
    <article className="reference-card reference-requirements-card">
      <div className="reference-card-heading">
        <h2>{c.attentionRows}</h2>
      </div>
      <div className="reference-table-header">
        <span>{c.table.id}</span>
        <span>{c.table.title}</span>
        <span>{c.table.status}</span>
        <span>{c.table.verification}</span>
        <span>{c.table.coverage}</span>
        <span />
      </div>
      <div className="reference-table-body">
        {rows.length ? (
          rows.map((item) => (
            <button
              key={item.id}
              className={`reference-requirement-row${selectedId === item.id ? " is-selected" : ""}`}
              onClick={() => onSelect(item.id)}
            >
              <span className="reference-req-id">{item.id}</span>
              <span className="reference-req-title">{item.title}</span>
              <span>
                <Pill tone={scopeTone[item.scope_status]}>{label(c.scope, item.scope_status)}</Pill>
              </span>
              <StatusText tone={verificationTone[item.verification]}>
                {label(c.verification, item.verification)}
              </StatusText>
              <span className="reference-coverage-cell">
                <span>{item.coverage}%</span>
                <span className="signoff-meter">
                  <span style={{ width: `${item.coverage}%` }} />
                </span>
              </span>
              <ChevronRight size={15} />
            </button>
          ))
        ) : (
          <div className="reference-empty">{c.allClear}</div>
        )}
      </div>
    </article>
  );
}

function ReleaseCard({
  projectId,
  data,
  onOpenTab,
  onSendForAcceptance,
  sending,
}: {
  projectId: string;
  data: Dashboard;
  onOpenTab: (tab: Tab) => void;
  onSendForAcceptance: () => void;
  sending: boolean;
}) {
  const { c } = useCopy();
  const readiness = useReadiness(projectId);
  const status = data.project.status;
  const canSend = status !== "ready" && status !== "accepted";
  return (
    <article className="reference-card signoff-release-card">
      <span className="reference-context-kicker">{c.releaseStatusLabel}</span>
      <Pill tone={releaseTone[status] || "neutral"}>{label(c.release, status)}</Pill>
      <div className="signoff-release-next">
        <small>{c.nextDecision}</small>
        <strong>{status === "ready" ? c.waitingClient : c.next[status]}</strong>
      </div>
      <div className="signoff-readiness-meter">
        <span>
          {c.readinessScore} <b>{readiness.data ? readiness.data.score : "—"}</b>
        </span>
        <span className="signoff-meter">
          <span style={{ width: `${readiness.data?.score ?? 0}%` }} />
        </span>
      </div>
      <div className="signoff-release-actions">
        {canSend && (
          <button className="reference-primary-button" onClick={onSendForAcceptance} disabled={sending}>
            {sending ? <Spinner /> : <Send size={14} />}
            {c.sendForAcceptance}
          </button>
        )}
        <button className="reference-secondary-button" onClick={() => onOpenTab("signoff")}>
          <PanelsTopLeft size={14} />
          {c.prepareDelivery}
        </button>
      </div>
    </article>
  );
}

function CoverageTrendCard({ trend }: { trend: Dashboard["coverage_trend"] }) {
  const { c } = useCopy();
  return (
    <article className="reference-card signoff-chart-card signoff-trend-card">
      <div className="reference-card-heading">
        <h2>{c.coverageTrend}</h2>
      </div>
      <p className="signoff-card-hint">{c.coverageTrendHint}</p>
      <CoverageTrendChart trend={trend} />
    </article>
  );
}

export function ActivityCard({
  items,
  onNavigateRef,
  title,
}: {
  items: ActivityItem[];
  onNavigateRef: (ref: Ref) => void;
  title?: string;
}) {
  const { c, t, locale } = useCopy();
  return (
    <article className="reference-card reference-activity-card">
      <div className="reference-card-heading">
        <h2>{title || t("recentActivity")}</h2>
      </div>
      <div className="reference-activity-list">
        {items.length ? (
          items.map((item) => (
            <div className="reference-activity-row" key={item.id}>
              <Avatar actor={item.actor} />
              <span>
                <strong>{item.actor.name}</strong>
                <small>
                  <ActivityText item={item} onNavigateRef={onNavigateRef} />
                </small>
              </span>
              <time dateTime={item.at}>{formatRelative(item.at, locale)}</time>
            </div>
          ))
        ) : (
          <div className="reference-empty">{c.noActivity}</div>
        )}
      </div>
    </article>
  );
}

/** The sentence already names the entity: make that id the link instead of repeating it as a chip. */
function ActivityText({ item, onNavigateRef }: { item: ActivityItem; onNavigateRef: (ref: Ref) => void }) {
  const ref = item.ref;
  if (!ref) return <>{item.text}</>;
  const index = item.text.indexOf(ref.id);
  const link = (text: string) => (
    <button className="signoff-inline-link" onClick={() => onNavigateRef(ref)}>
      {text}
    </button>
  );
  if (index === -1) {
    return (
      <>
        {item.text} {link(ref.label || ref.id)}
      </>
    );
  }
  return (
    <>
      {item.text.slice(0, index)}
      {link(ref.id)}
      {item.text.slice(index + ref.id.length)}
    </>
  );
}
