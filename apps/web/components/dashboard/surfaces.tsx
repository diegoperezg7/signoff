"use client";

import { useRef, useState } from "react";
import {
  CheckCircle2,
  ChevronRight,
  Download,
  FileBarChart2,
  FileStack,
  FolderKanban,
  Link2,
  Milestone,
  PanelsTopLeft,
  Rocket,
  Sparkles,
  TriangleAlert,
  Workflow,
} from "lucide-react";
import {
  api,
  type AttentionItem,
  type Dashboard,
  type Locale,
  type Ref,
  type ScopeVersion,
} from "../../lib/api";
import {
  useActivity,
  useAttention,
  useProjectMutation,
  useProjects,
  useReadiness,
  useReleases,
  useScopeVersions,
  useTeam,
} from "../../lib/queries";
import type { ThemePreference } from "../app-providers";
import { CoverageTrendChart, VerificationBars } from "./charts";
import { formatDate, label, releaseTone, severityTone, useCopy } from "./copy";
import { ActivityCard, KpiRow } from "./overview";
import { Avatar, Pill, Spinner, downloadJson } from "./ui";

export type Surface =
  | "projects"
  | "milestones"
  | "releases"
  | "reports"
  | "baselines"
  | "metrics"
  | "risk"
  | "templates"
  | "teams"
  | "integrations"
  | "settings";

export function GlobalSurface({
  surface,
  projectId,
  data,
  onOpenProject,
  onOpenAttention,
  onNavigateRef,
  notify,
}: {
  surface: Surface;
  projectId: string;
  data: Dashboard;
  onOpenProject: (projectId: string, releaseId: string) => void;
  onOpenAttention: (item: AttentionItem) => void;
  onNavigateRef: (ref: Ref) => void;
  notify: (message: string) => void;
}) {
  const { c, t, locale } = useCopy();
  const [reporting, setReporting] = useState(false);

  async function downloadReport() {
    setReporting(true);
    try {
      const pack = await api.deliveryPack(projectId, locale);
      downloadJson(`${data.project.name.toLowerCase().replaceAll(" ", "-")}-delivery-report.json`, pack);
      notify(c.reportDownloaded);
    } catch {
      notify(c.reportFailed);
    } finally {
      setReporting(false);
    }
  }

  return (
    <section className="reference-global-surface">
      <div className="reference-global-heading">
        <div>
          <span className="reference-eyebrow">
            {data.project.name} · {data.project.release}
          </span>
          <h1>{t(surface)}</h1>
          <p>{c.surface[surface]}</p>
        </div>
        {surface === "reports" && (
          <button className="reference-primary-button" onClick={downloadReport} disabled={reporting}>
            {reporting ? <Spinner /> : <Download size={16} />}
            {c.downloadReport}
          </button>
        )}
      </div>
      {surface === "projects" && <ProjectsSurface currentId={projectId} onOpenProject={onOpenProject} />}
      {(surface === "releases" || surface === "milestones") && (
        <ReleasesSurface
          projectId={projectId}
          data={data}
          milestones={surface === "milestones"}
          onOpenProject={onOpenProject}
        />
      )}
      {surface === "reports" && <ReportsSurface projectId={projectId} onNavigateRef={onNavigateRef} />}
      {surface === "baselines" && <BaselinesSurface projectId={projectId} notify={notify} />}
      {surface === "metrics" && <MetricsSurface projectId={projectId} data={data} />}
      {surface === "risk" && <RiskSurface projectId={projectId} onOpen={onOpenAttention} />}
      {surface === "teams" && <TeamSurface projectId={projectId} client={data.project.client} />}
      {surface === "templates" && (
        <div className="reference-global-grid">
          {c.templates.map((template) => (
            <article className="reference-card reference-template-card" key={template}>
              <FileStack size={20} />
              <h2>{template}</h2>
              <p>{c.templateBody}</p>
              <button className="reference-secondary-button" onClick={() => notify(c.templatePrepared)}>
                {c.useTemplate}
                <ChevronRight size={15} />
              </button>
            </article>
          ))}
        </div>
      )}
      {surface === "integrations" && (
        <div className="reference-global-grid">
          <article className="reference-card reference-integration-card">
            <Link2 size={20} />
            <h2>{c.manualRefs}</h2>
            <p>{c.manualRefsBody}</p>
            <Pill tone="warning">{c.prepared}</Pill>
          </article>
          <article className="reference-card reference-integration-card">
            <Workflow size={20} />
            <h2>{c.providers}</h2>
            <p>Browser Agent · File Inspector · Human Evidence</p>
            <Pill tone="success">{c.activeMock}</Pill>
          </article>
        </div>
      )}
      {surface === "settings" && <SettingsSurface />}
    </section>
  );
}

function ProjectsSurface({
  currentId,
  onOpenProject,
}: {
  currentId: string;
  onOpenProject: (projectId: string, releaseId: string) => void;
}) {
  const { c } = useCopy();
  const projects = useProjects();
  if (projects.isPending) return <Spinner />;
  return (
    <div className="reference-global-grid">
      {(projects.data || []).map((project) => (
        <article
          className={`reference-card reference-project-card${project.id === currentId ? " is-current" : ""}`}
          key={project.id}
        >
          <div className="reference-project-card-top">
            <FolderKanban size={19} />
            <Pill tone={releaseTone[project.status] || "neutral"}>{label(c.release, project.status)}</Pill>
          </div>
          <h2>{project.name}</h2>
          <p>
            {project.client} · {project.release_name}
          </p>
          <div className="signoff-readiness-meter">
            <span>
              {c.readiness} <b>{project.readiness}</b>
            </span>
            <span className="signoff-meter">
              <span style={{ width: `${project.readiness}%` }} />
            </span>
          </div>
          <div className="reference-project-meta">
            <span>{c.requirementsCount(project.requirements_count)}</span>
          </div>
          <button className="reference-secondary-button" onClick={() => onOpenProject(project.id, project.release_id)}>
            {c.openProject}
            <ChevronRight size={15} />
          </button>
        </article>
      ))}
    </div>
  );
}

function ReleasesSurface({
  projectId,
  data,
  milestones,
  onOpenProject,
}: {
  projectId: string;
  data: Dashboard;
  milestones: boolean;
  onOpenProject: (projectId: string, releaseId: string) => void;
}) {
  const { c, locale } = useCopy();
  const releases = useReleases(projectId);
  return (
    <>
      <div className="reference-card reference-global-list">
        {releases.isPending && <Spinner />}
        {(releases.data || []).map((release) => (
          <button className="reference-global-row" key={release.id} onClick={() => onOpenProject(projectId, release.id)}>
            <span>
              {milestones ? <Milestone size={16} /> : <Rocket size={16} />}
              <strong>{release.name}</strong>
              <small>
                {milestones
                  ? `${c.created} ${formatDate(release.created_at, locale)} → ${c.target} ${formatDate(release.target_date, locale)}`
                  : `${release.version} · ${release.baseline} · ${c.table.coverage} ${release.coverage}% · ${c.table.verification} ${release.verification}%`}
              </small>
            </span>
            <Pill tone={releaseTone[release.status] || "neutral"}>{label(c.release, release.status)}</Pill>
            <ChevronRight size={16} />
          </button>
        ))}
      </div>
      {!milestones && (
        <div className="reference-release-insight">
          <div>
            <span>{c.currentState}</span>
            <strong>{label(c.release, data.project.status)}</strong>
            <small>{c.next[data.project.status]}</small>
          </div>
          <div>
            <span>{c.table.coverage}</span>
            <strong>{data.metrics.coverage.value}%</strong>
            <small>{c.coverageHint}</small>
          </div>
          <div>
            <span>{c.nextMilestone}</span>
            <strong>{formatDate(data.project.target_date, locale)}</strong>
            <small>{c.targetDate}</small>
          </div>
        </div>
      )}
    </>
  );
}

function ReportsSurface({ projectId, onNavigateRef }: { projectId: string; onNavigateRef: (ref: Ref) => void }) {
  const { c } = useCopy();
  const activity = useActivity(projectId);
  return (
    <>
      <div className="reference-global-grid">
        <article className="reference-card reference-report-card">
          <FileBarChart2 size={22} />
          <h2>{c.deliveryReport}</h2>
          <p>{c.deliveryReportBody}</p>
        </article>
        <article className="reference-card reference-report-card">
          <PanelsTopLeft size={22} />
          <h2>{c.evidencePack}</h2>
          <p>{c.evidencePackBody}</p>
        </article>
      </div>
      <div className="signoff-surface-block">
        <ActivityCard items={activity.data || []} onNavigateRef={onNavigateRef} title={c.activityLog} />
      </div>
    </>
  );
}

function BaselinesSurface({ projectId, notify }: { projectId: string; notify: (message: string) => void }) {
  const { c, locale } = useCopy();
  const versions = useScopeVersions(projectId);
  const [file, setFile] = useState<File | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const extract = useProjectMutation(projectId, (selected: File) => api.extractScope(projectId, selected));
  const approve = useProjectMutation(projectId, (version: string) => api.approveScopeVersion(projectId, version));
  const list = versions.data || [];
  const draft = list.find((item) => item.status === "draft");

  return (
    <div className="reference-card reference-global-list">
      <div className="reference-baseline-import">
        <label className="reference-file-picker">
          <FileStack size={16} />
          <span>{file ? file.name : c.baselineSelect}</span>
          <input
            ref={input}
            type="file"
            accept=".pdf,.docx,.txt,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </label>
        <button
          className="reference-secondary-button"
          disabled={extract.isPending || !file}
          onClick={() =>
            file &&
            extract.mutate(file, {
              onSuccess: () => {
                notify(c.extracted);
                setFile(null);
                if (input.current) input.current.value = "";
              },
              onError: () => notify(c.extractFailed),
            })
          }
        >
          {extract.isPending ? <Spinner /> : <Sparkles size={14} />}
          {extract.isPending ? c.extracting : c.extract}
        </button>
      </div>
      {draft && (
        <DraftReview
          draft={draft}
          busy={approve.isPending}
          onConfirm={() =>
            approve.mutate(draft.version, {
              onSuccess: () => notify(c.baselineConfirmed),
              onError: () => notify(c.baselineFailed),
            })
          }
        />
      )}
      {versions.isPending && <Spinner />}
      {list.map((item) => (
        <div className="reference-global-row" key={item.version}>
          <span>
            <PanelsTopLeft size={16} />
            <strong>{item.version}</strong>
            <small>
              {item.source} · {item.summary} · {formatDate(item.created_at, locale)}
              {item.created_by ? ` · ${c.by(item.created_by.name)}` : ""}
            </small>
          </span>
          <Pill tone={item.status === "approved" ? "success" : item.status === "draft" ? "warning" : "neutral"}>
            {label(c.scopeVersionStatus, item.status)}
          </Pill>
        </div>
      ))}
    </div>
  );
}

function DraftReview({ draft, busy, onConfirm }: { draft: ScopeVersion; busy: boolean; onConfirm: () => void }) {
  const { c } = useCopy();
  const diff = draft.diff || { added: [], modified: [], removed: [] };
  const empty = !diff.added.length && !diff.modified.length && !diff.removed.length;
  return (
    <section className="signoff-draft">
      <header>
        <strong>{c.draftReview(draft.version)}</strong>
        <button className="reference-primary-button" onClick={onConfirm} disabled={busy}>
          {busy ? <Spinner /> : <CheckCircle2 size={15} />}
          {busy ? c.confirming : c.confirmBaseline}
        </button>
      </header>
      {empty && <p className="signoff-empty-text">{c.noDiff}</p>}
      {diff.added.length > 0 && (
        <div className="signoff-draft-group is-added">
          <span className="reference-context-kicker">
            {c.added} · {diff.added.length}
          </span>
          {diff.added.map((item, index) => (
            <div key={`${item.title}-${index}`}>
              <strong>{item.title}</strong>
              <small>
                {item.component}
                {item.description ? ` · ${item.description}` : ""}
              </small>
            </div>
          ))}
        </div>
      )}
      {diff.modified.length > 0 && (
        <div className="signoff-draft-group is-modified">
          <span className="reference-context-kicker">
            {c.modified} · {diff.modified.length}
          </span>
          {diff.modified.map((item) => (
            <div key={item.id}>
              <strong>
                {item.id} · {item.title}
              </strong>
              <small className="signoff-before">{item.before}</small>
              <small className="signoff-after">{item.after}</small>
            </div>
          ))}
        </div>
      )}
      {diff.removed.length > 0 && (
        <div className="signoff-draft-group is-removed">
          <span className="reference-context-kicker">
            {c.removed} · {diff.removed.length}
          </span>
          {diff.removed.map((item) => (
            <div key={item.id}>
              <strong>
                {item.id} · {item.title}
              </strong>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function MetricsSurface({ projectId, data }: { projectId: string; data: Dashboard }) {
  const { c, t } = useCopy();
  const readiness = useReadiness(projectId);
  return (
    <>
      <div className="reference-global-metrics">
        <KpiRow data={data} />
      </div>
      <div className="signoff-chart-grid signoff-surface-block">
        <article className="reference-card signoff-chart-card signoff-trend-card">
          <div className="reference-card-heading">
            <h2>{c.coverageTrend}</h2>
          </div>
          <p className="signoff-card-hint">{c.coverageTrendHint}</p>
          <CoverageTrendChart trend={data.coverage_trend} />
        </article>
        <article className="reference-card signoff-chart-card">
          <div className="reference-card-heading">
            <h2>{t("verificationStatus")}</h2>
          </div>
          <VerificationBars
            items={data.verification_status.map((item) => ({
              key: item.key,
              label: label(c.verification, item.key),
              value: item.value,
              tone: item.tone,
            }))}
          />
          {readiness.data && (
            <div className="signoff-readiness-meter">
              <span>
                {c.readinessScore} <b>{readiness.data.score}</b>
              </span>
              <span className="signoff-meter">
                <span style={{ width: `${readiness.data.score}%` }} />
              </span>
            </div>
          )}
        </article>
      </div>
    </>
  );
}

function RiskSurface({ projectId, onOpen }: { projectId: string; onOpen: (item: AttentionItem) => void }) {
  const { c } = useCopy();
  const attention = useAttention(projectId);
  if (attention.isPending) return <Spinner />;
  const items = attention.data || [];
  return (
    <div className="reference-card reference-global-list">
      {items.length ? (
        items.map((item) => (
          <button className="reference-global-row" key={item.id} onClick={() => onOpen(item)}>
            <span>
              <TriangleAlert size={16} />
              <strong>{item.title}</strong>
              <small>
                {item.source}
                {item.count ? ` · ${c.occurrences(item.count)}` : ""}
              </small>
            </span>
            <Pill tone={severityTone[item.severity] || "neutral"}>{label(c.severity, item.severity)}</Pill>
            <ChevronRight size={16} />
          </button>
        ))
      ) : (
        <div className="reference-empty">{c.noRisk}</div>
      )}
    </div>
  );
}

function TeamSurface({ projectId, client }: { projectId: string; client: string }) {
  const { c } = useCopy();
  const team = useTeam(projectId);
  if (team.isPending) return <Spinner />;
  return (
    <div className="reference-global-grid">
      {(team.data || []).map((member) => (
        <article className="reference-card reference-team-card" key={member.id}>
          <Avatar actor={member} />
          <h2>{member.name}</h2>
          <p>
            {label(c.roles, member.role)} · {client}
          </p>
          <small>{member.email}</small>
        </article>
      ))}
    </div>
  );
}

function SettingsSurface() {
  const { c, t, locale, setLocale, themePreference, setThemePreference, resolvedTheme } = useCopy();
  return (
    <div className="reference-card reference-settings-card">
      <label>
        {t("language")}
        <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
          <option value="en">English</option>
          <option value="es">Español</option>
        </select>
      </label>
      <label>
        {t("theme")}
        <select value={themePreference} onChange={(event) => setThemePreference(event.target.value as ThemePreference)}>
          <option value="dark">{t("dark")}</option>
          <option value="light">{t("light")}</option>
          <option value="system">{t("system")}</option>
        </select>
      </label>
      <div className="reference-settings-preview">
        <span className={`status-dot ${resolvedTheme === "dark" ? "tone-progress" : "tone-success"}`} />
        {c.themeActive(resolvedTheme === "dark")}
      </div>
    </div>
  );
}
