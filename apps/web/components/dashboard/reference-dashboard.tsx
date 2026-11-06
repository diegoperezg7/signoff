"use client";

import { useMemo, useState } from "react";
import {
  ArrowUpRight,
  Bell,
  Check,
  ChevronDown,
  CircleAlert,
  Command,
  FileBarChart2,
  FileStack,
  FolderKanban,
  Gauge,
  LayoutDashboard,
  Link2,
  Milestone,
  MoreHorizontal,
  Moon,
  PanelsTopLeft,
  RefreshCw,
  Rocket,
  Search,
  Send,
  Settings2,
  Share2,
  Sparkles,
  Sun,
  TriangleAlert,
  UsersRound,
  Workflow,
} from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { api, type AttentionItem, type Ref, type ReleaseStatus } from "../../lib/api";
import {
  useAttention,
  useDashboard,
  useProjectMutation,
  useProposals,
  useRequirements,
  useTeam,
} from "../../lib/queries";
import { BrandLockup } from "../brand-lockup";
import { AgentDock, useAgentName, useStartAgent, type DockState } from "../agents/agent-dock";
import type { Locale, ThemePreference } from "../app-providers";
import { formatDate, label, releaseTone, severityTone, toneClass, useCopy } from "./copy";
import { Overview } from "./overview";
import { RequirementDrawer } from "./requirement-drawer";
import { GlobalSurface, type Surface } from "./surfaces";
import { TabView, type Tab } from "./tab-views";
import { Avatar } from "./ui";

type NavItem = "dashboard" | Surface;

const navGroups: {
  label?: "projects" | "insights" | "configuration";
  items: { id: NavItem; icon: typeof LayoutDashboard }[];
}[] = [
  { items: [{ id: "dashboard", icon: LayoutDashboard }] },
  {
    label: "projects",
    items: [
      { id: "projects", icon: FolderKanban },
      { id: "milestones", icon: Milestone },
      { id: "releases", icon: Rocket },
      { id: "reports", icon: FileBarChart2 },
    ],
  },
  {
    label: "insights",
    items: [
      { id: "baselines", icon: PanelsTopLeft },
      { id: "metrics", icon: Gauge },
      { id: "risk", icon: TriangleAlert },
    ],
  },
  {
    label: "configuration",
    items: [
      { id: "templates", icon: FileStack },
      { id: "teams", icon: UsersRound },
      { id: "integrations", icon: Workflow },
      { id: "settings", icon: Settings2 },
    ],
  },
];

const navIds: NavItem[] = navGroups.flatMap((group) => group.items.map((item) => item.id));
const tabs: Tab[] = ["overview", "requirements", "changes", "verification", "evidence", "signoff"];
const reviewTokens: Record<string, string> = {
  project_acme: "acme-review-token",
  project_demo: "demo-review-token",
};
const defaultRelease: Record<string, string> = { project_acme: "release_2_3", project_demo: "release_1_0" };

/* Seen notifications are per browser and per project: the dot only shows when something new appears. */
function seenKey(projectId: string) {
  return `signoff-seen-notifications:${projectId}`;
}
function readSeen(projectId: string): string[] {
  if (typeof window === "undefined") return [];
  try {
    return JSON.parse(window.localStorage.getItem(seenKey(projectId)) || "[]") as string[];
  } catch {
    return [];
  }
}
function writeSeen(projectId: string, ids: string[]) {
  try {
    window.localStorage.setItem(seenKey(projectId), JSON.stringify(ids.slice(-200)));
  } catch {
    /* storage unavailable: the dot simply stays */
  }
}

/** `?dock=pending` or `?dock=proposal:<id>` lets other routes open the agent dock on the dashboard. */
function dockFromParam(value: string | null): DockState {
  if (value === "pending") return { open: true, view: { type: "pending" } };
  if (value?.startsWith("proposal:")) return { open: true, view: { type: "proposal", id: value.slice(9) } };
  if (value?.startsWith("run:")) return { open: true, view: { type: "run", runId: value.slice(4) } };
  return { open: false, view: { type: "launch" } };
}

export function ReferenceDashboard() {
  const { c, t, locale, resolvedTheme, themePreference, setThemePreference, setLocale } = useCopy();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project") || "project_acme";
  const releaseId = searchParams.get("release") || defaultRelease[projectId] || "release_2_3";
  const activeNav: NavItem = navIds.find((id) => pathname === `/${id}`) || "dashboard";
  const tabParam = searchParams.get("tab") as Tab | null;
  const activeTab: Tab = tabParam && tabs.includes(tabParam) ? tabParam : "overview";

  const dashboard = useDashboard(projectId, releaseId);
  const requirements = useRequirements(projectId);
  const attention = useAttention(projectId);
  const proposals = useProposals(projectId);
  const team = useTeam(projectId);
  const agentName = useAgentName();

  const [search, setSearch] = useState("");
  const [searchFocused, setSearchFocused] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [statusMenuOpen, setStatusMenuOpen] = useState(false);
  const [toast, setToast] = useState("");
  const [seenVersion, setSeenVersion] = useState(0);
  const [dock, setDock] = useState<DockState>(() => dockFromParam(searchParams.get("dock")));

  const verification = useProjectMutation(projectId, (ids: string[]) => api.runVerification(projectId, ids));
  const setStatus = useProjectMutation(projectId, (status: ReleaseStatus) =>
    api.setReleaseStatus(projectId, releaseId, status),
  );
  const sendForAcceptance = useProjectMutation(projectId, () => api.sendForAcceptance(projectId, releaseId));
  const startAgent = useStartAgent(projectId);

  const allRows = useMemo(() => requirements.data || [], [requirements.data]);
  const data = dashboard.data && dashboard.data.project.id === projectId ? dashboard.data : null;
  const selectedId = searchParams.get("requirement") || data?.requirements[0]?.id || allRows[0]?.id || null;
  const drawerOpen = activeNav === "dashboard" && searchParams.get("drawer") !== "closed" && Boolean(selectedId);

  const notifications: {
    key: string;
    tone: "error" | "warning" | "progress";
    title: string;
    detail: string;
    open: () => void;
  }[] = [
    ...(attention.data || [])
      .filter((item) => !(item.target.tab === "agents" && proposals.data?.length))
      .map((item) => ({
      key: `a:${item.id}:${item.count}`,
      tone: severityTone[item.severity] as "error" | "warning" | "progress",
      title: item.title,
      detail: item.source,
      open: () => openAttention(item),
    })),
    ...(proposals.data || []).map((proposal) => ({
      key: `p:${proposal.id}`,
      tone: "progress" as const,
      title: proposal.title,
      detail: `${agentName(proposal.agent)} · ${label(c.proposalKind, proposal.kind)}`,
      open: () => openDock({ type: "proposal", id: proposal.id }, `proposal:${proposal.id}`),
    })),
  ];
  // seenVersion forces a re-read after the user marks something as read.
  const seen = useMemo(() => readSeen(projectId), [projectId, seenVersion]); // eslint-disable-line react-hooks/exhaustive-deps
  const unread = notifications.filter((item) => !seen.includes(item.key));

  function markSeen(keysToMark: string[]) {
    writeSeen(projectId, Array.from(new Set([...seen, ...keysToMark])));
    setSeenVersion((value) => value + 1);
  }

  function notify(message: string) {
    setToast(message);
    window.setTimeout(() => setToast((current) => (current === message ? "" : current)), 2600);
  }

  /** All dashboard navigation goes through the URL so links, back/forward and reloads agree. */
  function goDashboard(update: { tab?: Tab; requirement?: string; drawer?: "closed" | null; dock?: string }) {
    const next = new URLSearchParams(pathname === "/dashboard" ? searchParams.toString() : "");
    next.delete("dock");
    if (update.dock) next.set("dock", update.dock);
    next.set("project", projectId);
    next.set("release", releaseId);
    if (update.tab) next.set("tab", update.tab);
    else if (!next.get("tab")) next.set("tab", "overview");
    if (update.requirement) next.set("requirement", update.requirement);
    if (update.drawer === null) next.delete("drawer");
    else if (update.drawer) next.set("drawer", update.drawer);
    const url = `/dashboard?${next.toString()}`;
    if (pathname === "/dashboard") router.replace(url, { scroll: false });
    else router.push(url);
  }

  function selectRequirement(id: string) {
    goDashboard({ requirement: id, drawer: null });
  }

  function openDock(view: DockState["view"], param: string) {
    if (activeNav === "dashboard") setDock({ open: true, view });
    else goDashboard({ dock: param });
  }

  function navigateRef(ref: Ref) {
    if (ref.type === "requirement") selectRequirement(ref.id);
    else if (ref.type === "evidence") goDashboard({ tab: "evidence" });
    else if (ref.type === "change") goDashboard({ tab: "changes" });
    else if (ref.type === "proposal") openDock({ type: "proposal", id: ref.id }, `proposal:${ref.id}`);
    else if (ref.type === "scope_version") router.push(`/baselines?project=${projectId}&release=${releaseId}`);
  }

  function openAttention(item: AttentionItem) {
    if (item.target.tab === "agents") {
      openDock({ type: "pending" }, "pending");
      return;
    }
    goDashboard({
      tab: item.target.tab,
      ...(item.target.requirement_id ? { requirement: item.target.requirement_id, drawer: null } : {}),
    });
  }

  function selectNav(id: NavItem) {
    setProfileOpen(false);
    if (id === "dashboard") goDashboard({ tab: "overview" });
    else router.push(`/${id}?project=${projectId}&release=${releaseId}`);
  }

  function runAgent(agentId: string, requirementId: string) {
    startAgent.mutate(
      { agentId, requirementId },
      {
        onSuccess: (result) => setDock({ open: true, view: { type: "run", runId: result.run_id } }),
        onError: (error) => notify(`${c.agentFailed}: ${error.message}`),
      },
    );
  }

  function runVerification(ids: string[]) {
    verification.mutate(ids, {
      onSuccess: (result) => {
        const run = result.runs[0];
        notify(run ? c.verificationDone(ids[0], label(c.verification, run.result)) : c.verificationDone(ids[0], "—"));
      },
      onError: () => notify(c.verificationFailed),
    });
  }

  function moveRequirement(direction: -1 | 1) {
    const rows = allRows.length ? allRows : data?.requirements || [];
    const index = rows.findIndex((row) => row.id === selectedId);
    const next = rows[(index + direction + rows.length) % rows.length];
    if (next) selectRequirement(next.id);
  }

  async function share() {
    const link = `${window.location.origin}/review/${reviewTokens[projectId] || "acme-review-token"}`;
    setMenuOpen(false);
    try {
      await navigator.clipboard.writeText(link);
      notify(c.linkCopied);
    } catch {
      notify(link);
    }
  }

  function openPortal() {
    window.open(`/review/${reviewTokens[projectId] || "acme-review-token"}`, "_blank", "noopener,noreferrer");
  }

  function send() {
    setMenuOpen(false);
    sendForAcceptance.mutate(undefined, {
      onSuccess: () => notify(c.releaseSent),
      onError: () => notify(c.releaseSendFailed),
    });
  }

  if (!data) {
    return (
      <div className={`reference-dashboard reference-${resolvedTheme}`}>
        <main className="reference-main">
          <div className="reference-loading">
            <BrandLockup compact />
            {dashboard.isError ? (
              <>
                <span>{c.apiDown}</span>
                <button className="reference-primary-button" onClick={() => dashboard.refetch()}>
                  <RefreshCw size={15} />
                  {c.retry}
                </button>
              </>
            ) : (
              <span>{c.loading}</span>
            )}
          </div>
        </main>
      </div>
    );
  }

  const status = data.project.status;
  const owner = team.data?.find((member) => member.role === "owner") || team.data?.[0];
  const needle = search.trim().toLowerCase();
  const matches = needle
    ? allRows.filter((row) => `${row.id} ${row.title} ${row.component}`.toLowerCase().includes(needle)).slice(0, 8)
    : [];
  const topAttention = attention.data?.[0];
  const hasCritical = (attention.data || []).some((item) => item.severity === "critical");

  return (
    <div className={`reference-dashboard reference-${resolvedTheme}`}>
      <aside className="reference-sidebar">
        <div className="reference-brand">
          <BrandLockup compact />
        </div>
        <nav className="reference-nav" aria-label={t("dashboard")}>
          {navGroups.map((group, groupIndex) => (
            <div className="reference-nav-group" key={group.label || groupIndex}>
              {group.label && <div className="reference-nav-label">{c.groups[group.label]}</div>}
              {group.items.map(({ id, icon: Icon }) => (
                <button
                  key={id}
                  className={`reference-nav-item${activeNav === id ? " is-active" : ""}`}
                  aria-current={activeNav === id ? "page" : undefined}
                  onClick={() => selectNav(id)}
                >
                  <Icon size={17} strokeWidth={1.55} />
                  <span>{t(id)}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="reference-account">
          <button
            className="reference-account-button"
            onClick={() => setProfileOpen((value) => !value)}
            aria-expanded={profileOpen}
          >
            <Avatar actor={owner} />
            <span>
              <strong>{owner?.name || data.project.client}</strong>
              <small>
                {owner?.role ? label(c.roles, owner.role) : c.workspaceOwner} · {data.project.client}
              </small>
            </span>
            <ChevronDown size={15} />
          </button>
          {profileOpen && (
            <div className="reference-profile-menu">
              <div className="reference-profile-heading">{t("settings")}</div>
              <label>
                {t("language")}
                <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
                  <option value="en">English</option>
                  <option value="es">Español</option>
                </select>
              </label>
              <label>
                {t("theme")}
                <select
                  value={themePreference}
                  onChange={(event) => setThemePreference(event.target.value as ThemePreference)}
                >
                  <option value="dark">{t("dark")}</option>
                  <option value="light">{t("light")}</option>
                  <option value="system">{t("system")}</option>
                </select>
              </label>
            </div>
          )}
        </div>
      </aside>
      <main className="reference-main">
        <header className="reference-topbar">
          <div className="reference-top-actions">
            <div className="signoff-search-wrap">
              <label className="reference-search">
                <Search size={16} />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  onFocus={() => setSearchFocused(true)}
                  onBlur={() => window.setTimeout(() => setSearchFocused(false), 150)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && matches[0]) {
                      selectRequirement(matches[0].id);
                      setSearch("");
                    }
                    if (event.key === "Escape") setSearch("");
                  }}
                  placeholder={t("search")}
                  aria-label={c.searchAll}
                />
                <kbd>
                  <Command size={11} />K
                </kbd>
              </label>
              {searchFocused && needle && (
                <div className="signoff-search-results" role="listbox" aria-label={c.searchAll}>
                  {matches.length ? (
                    matches.map((row) => (
                      <button
                        key={row.id}
                        role="option"
                        aria-selected={row.id === selectedId}
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => {
                          selectRequirement(row.id);
                          setSearch("");
                        }}
                      >
                        <span className="reference-req-id">{row.id}</span>
                        <span>{row.title}</span>
                        <small>{label(c.verification, row.verification)}</small>
                      </button>
                    ))
                  ) : (
                    <span className="signoff-empty-text">{c.searchEmpty}</span>
                  )}
                </div>
              )}
            </div>
            <div className="reference-notification-wrap">
              <button
                className="reference-icon-button"
                aria-label={`${c.notifications}${unread.length ? ` (${unread.length})` : ""}`}
                aria-expanded={notificationOpen}
                onClick={() => setNotificationOpen((value) => !value)}
              >
                <Bell size={18} />
                {unread.length > 0 && <span className="reference-notification-dot" />}
              </button>
              {notificationOpen && (
                <div className="reference-notification-panel">
                  <div>
                    <strong>{c.notifications}</strong>
                    <button
                      disabled={!unread.length}
                      onClick={() => markSeen(notifications.map((item) => item.key))}
                    >
                      {c.markRead}
                    </button>
                  </div>
                  {notifications.length ? (
                    notifications.map((item) => (
                      <button
                        key={item.key}
                        className={seen.includes(item.key) ? "is-read" : "is-unread"}
                        onClick={() => {
                          markSeen([item.key]);
                          setNotificationOpen(false);
                          item.open();
                        }}
                      >
                        {item.key.startsWith("p:") ? (
                          <Sparkles size={15} className={`signoff-ink-${item.tone}`} />
                        ) : (
                          <CircleAlert size={15} className={`signoff-ink-${item.tone}`} />
                        )}
                        <span>
                          <strong>{item.title}</strong>
                          <small>{item.detail}</small>
                        </span>
                      </button>
                    ))
                  ) : (
                    <p className="signoff-empty-text">{c.noNotifications}</p>
                  )}
                </div>
              )}
            </div>
            <button
              className="reference-theme-toggle"
              onClick={() => setThemePreference(resolvedTheme === "dark" ? "light" : "dark")}
              aria-label={resolvedTheme === "dark" ? t("switchToLight") : t("switchToDark")}
              title={resolvedTheme === "dark" ? t("switchToLight") : t("switchToDark")}
            >
              {resolvedTheme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button
              className="reference-user-button"
              onClick={() => setProfileOpen((value) => !value)}
              aria-label={t("settings")}
            >
              <Avatar actor={owner} />
              <ChevronDown size={14} />
            </button>
          </div>
        </header>
        {activeNav === "dashboard" && (
          <div className="reference-context-strip" aria-label={c.activeContext}>
            <div className="reference-context-lead">
              <span className="reference-context-kicker">{c.activeContext}</span>
              <strong>
                {data.project.client} · {data.project.release}
              </strong>
            </div>
            <div className="reference-context-item">
              <span
                className={`context-indicator ${data.attention_count ? (hasCritical ? "context-indicator-error" : "context-indicator-warning") : "context-indicator-success"}`}
              />
              <span>
                <small>{c.attention}</small>
                <strong>{data.attention_count ? c.needAttention(data.attention_count) : c.allClear}</strong>
              </span>
            </div>
            <div className="reference-context-item">
              <span className={`context-indicator context-indicator-${releaseTone[status] || "neutral"}`} />
              <span>
                <small>{c.nextDecision}</small>
                <strong>{c.next[status]}</strong>
              </span>
            </div>
            {topAttention && (
              <button className="reference-context-action" onClick={() => openAttention(topAttention)}>
                {c.reviewFindings}
                <ArrowUpRight size={15} />
              </button>
            )}
            <AgentDock
              projectId={projectId}
              requirementId={selectedId}
              state={dock}
              onChange={setDock}
              onNavigate={navigateRef}
              notify={notify}
            />
          </div>
        )}
        {activeNav === "dashboard" ? (
          <>
            <section className="reference-release-header">
              <div>
                <div className="reference-title-row">
                  <h1>
                    {data.project.release} – {data.project.client}
                  </h1>
                  <div className="reference-status-wrap">
                    <button
                      className="reference-status-select"
                      onClick={() => setStatusMenuOpen((value) => !value)}
                      aria-expanded={statusMenuOpen}
                      disabled={setStatus.isPending}
                    >
                      <span className={`status-dot ${toneClass[releaseTone[status] || "neutral"]}`} />
                      {label(c.release, status)}
                      <ChevronDown size={13} />
                    </button>
                    {statusMenuOpen && (
                      <div className="reference-status-menu">
                        {(["in_signoff", "ready", "on_hold"] as ReleaseStatus[]).map((option) => (
                          <button
                            key={option}
                            onClick={() => {
                              setStatusMenuOpen(false);
                              if (option === status) return;
                              setStatus.mutate(option, {
                                onSuccess: () => notify(c.statusUpdated),
                                onError: () => notify(c.statusFailed),
                              });
                            }}
                          >
                            <span className={`status-dot ${toneClass[releaseTone[option]]}`} />
                            {label(c.release, option)}
                            {option === status && <Check size={13} />}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <p>
                  {data.project.version} <span>·</span> {c.created} {formatDate(data.project.created_at, locale)}{" "}
                  <span>·</span> {c.target} {formatDate(data.project.target_date, locale)}
                </p>
              </div>
              <div className="reference-header-buttons">
                <button className="reference-primary-button" onClick={share}>
                  <Share2 size={16} />
                  {t("share")}
                </button>
                <div className="reference-menu-wrap">
                  <button
                    className="reference-secondary-button"
                    onClick={() => setMenuOpen((value) => !value)}
                    aria-label={c.moreActions}
                    aria-expanded={menuOpen}
                  >
                    <MoreHorizontal size={19} />
                  </button>
                  {menuOpen && (
                    <div className="reference-action-menu">
                      <button onClick={share}>
                        <Link2 size={14} /> {c.copyReviewLink}
                      </button>
                      <button
                        onClick={() => {
                          setMenuOpen(false);
                          goDashboard({ tab: "signoff" });
                        }}
                      >
                        <FileBarChart2 size={14} /> {c.openReport}
                      </button>
                      <button onClick={send} disabled={sendForAcceptance.isPending || status === "ready"}>
                        <Send size={14} /> {c.sendForAcceptance}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </section>
            <div className="reference-tabs" role="tablist">
              {tabs.map((id) => (
                <button
                  key={id}
                  role="tab"
                  aria-selected={activeTab === id}
                  className={activeTab === id ? "is-active" : ""}
                  onClick={() => goDashboard({ tab: id })}
                >
                  {t(id)}
                </button>
              ))}
            </div>
            <section className="reference-workspace">
              {activeTab === "overview" ? (
                <Overview
                  data={data}
                  selectedId={selectedId}
                  onSelect={selectRequirement}
                  onOpenTab={(tab) => goDashboard({ tab })}
                  onNavigateRef={navigateRef}
                  projectId={projectId}
                  onSendForAcceptance={send}
                  sending={sendForAcceptance.isPending}
                />
              ) : (
                <TabView
                  tab={activeTab}
                  projectId={projectId}
                  data={data}
                  requirements={allRows}
                  requirementsLoading={requirements.isPending}
                  selectedId={selectedId}
                  onSelect={selectRequirement}
                  onRunVerification={runVerification}
                  verifyingIds={verification.isPending ? verification.variables || [] : []}
                  onStartAgent={runAgent}
                  agentStarting={startAgent.isPending}
                  onSendForAcceptance={send}
                  sending={sendForAcceptance.isPending}
                  onOpenPortal={openPortal}
                  notify={notify}
                />
              )}
              {drawerOpen && selectedId && (
                <RequirementDrawer
                  key={selectedId}
                  projectId={projectId}
                  requirementId={selectedId}
                  releaseName={data.project.release}
                  onClose={() => goDashboard({ drawer: "closed" })}
                  onPrevious={() => moveRequirement(-1)}
                  onNext={() => moveRequirement(1)}
                  onOpenVerification={() => goDashboard({ tab: "verification", drawer: "closed" })}
                  onRunVerification={runVerification}
                  verifying={verification.isPending && (verification.variables || []).includes(selectedId)}
                  onStartAgent={runAgent}
                  agentStarting={startAgent.isPending}
                  notify={notify}
                />
              )}
            </section>
          </>
        ) : (
          <GlobalSurface
            surface={activeNav}
            projectId={projectId}
            data={data}
            onOpenProject={(nextProject, nextRelease) =>
              router.push(`/dashboard?project=${nextProject}&release=${nextRelease}&tab=overview`)
            }
            onOpenAttention={openAttention}
            onNavigateRef={navigateRef}
            notify={notify}
          />
        )}
        {toast && (
          <div className="reference-toast" role="status">
            <Check size={14} />
            {toast}
          </div>
        )}
      </main>
    </div>
  );
}
