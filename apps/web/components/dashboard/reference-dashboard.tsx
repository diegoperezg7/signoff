"use client";

/* Chart measurement uses callback refs intentionally so Recharts never receives a zero-size container. */
/* eslint-disable react-hooks/refs */

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import {
  Bell,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  Command,
  Download,
  FileBarChart2,
  FileStack,
  FolderKanban,
  Gauge,
  LayoutDashboard,
  Link2,
  MessageCircle,
  Milestone,
  MoreHorizontal,
  Moon,
  PanelsTopLeft,
  Play,
  Rocket,
  Search,
  Settings2,
  Share2,
  SlidersHorizontal,
  Sparkles,
  Sun,
  RefreshCw,
  Send,
  ExternalLink,
  TriangleAlert,
  UserRound,
  UsersRound,
  Workflow,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { BrandLockup } from "../brand-lockup";
import { AgentDock } from "../agents/agent-dock";
import {
  useAppPreferences,
  type Locale,
  type MessageKey,
  type ThemePreference,
} from "../app-providers";

const API =
  process.env.NEXT_PUBLIC_SDA_API_URL ||
  process.env.SDA_API_URL ||
  "http://127.0.0.1:8000";

type Tone = "success" | "warning" | "error" | "progress" | "neutral";
type Tab =
  | "overview"
  | "requirements"
  | "changes"
  | "verification"
  | "evidence"
  | "signoff";
type DrawerTab = "details" | "verification" | "evidence" | "comments";
type ReleaseStatus = "in_signoff" | "ready" | "on_hold" | "accepted";
type NavItem =
  | "dashboard"
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
type Translate = (key: MessageKey) => string;

type DashboardData = {
  project: {
    id: string;
    name: string;
    client: string;
    release: string;
    version: string;
    status: string;
    created_at: string;
    target_date: string;
  };
  metrics: Record<
    string,
    {
      value: number;
      suffix?: string;
      items: { value: number; tone: Tone; label: string }[];
    }
  >;
  requirements: RequirementRow[];
  selected_requirement: RequirementDetail;
  activity: ActivityItem[];
  verification_status: { name: string; value: number; tone: Tone }[];
  coverage_trend: number[];
};

type RequirementRow = {
  id: string;
  title: string;
  status: "agreed" | "pending";
  verification: "passed" | "in_progress" | "not_started";
  coverage: number;
};
type RequirementDetail = {
  id: string;
  status: "agreed" | "pending";
  version: string;
  title: string;
  description: string;
  type: string;
  priority: string;
  component: string;
  baseline: string;
  created: string;
  agreed: string;
  owner: string;
  criteria: string[];
};
type ActivityItem = {
  avatar: string;
  author: string;
  text: string;
  time: string;
};

const navGroups: {
  label?: string;
  items: {
    id: NavItem;
    icon: typeof LayoutDashboard;
    label: keyof typeof labelKeys;
  }[];
}[] = [
  { items: [{ id: "dashboard", icon: LayoutDashboard, label: "dashboard" }] },
  {
    label: "PROJECTS",
    items: [
      { id: "projects", icon: FolderKanban, label: "projects" },
      { id: "milestones", icon: Milestone, label: "milestones" },
      { id: "releases", icon: Rocket, label: "releases" },
      { id: "reports", icon: FileBarChart2, label: "reports" },
    ],
  },
  {
    label: "INSIGHTS",
    items: [
      { id: "baselines", icon: PanelsTopLeft, label: "baselines" },
      { id: "metrics", icon: Gauge, label: "metrics" },
      { id: "risk", icon: TriangleAlert, label: "risk" },
    ],
  },
  {
    label: "CONFIGURATION",
    items: [
      { id: "templates", icon: FileStack, label: "templates" },
      { id: "teams", icon: UsersRound, label: "teams" },
      { id: "integrations", icon: Workflow, label: "integrations" },
      { id: "settings", icon: Settings2, label: "settings" },
    ],
  },
];

const navRoutes: Record<string, NavItem> = {
  "/dashboard": "dashboard",
  "/projects": "projects",
  "/milestones": "milestones",
  "/releases": "releases",
  "/reports": "reports",
  "/baselines": "baselines",
  "/metrics": "metrics",
  "/risk": "risk",
  "/templates": "templates",
  "/teams": "teams",
  "/integrations": "integrations",
  "/settings": "settings",
};

const navRoutesById: Record<NavItem, string> = Object.entries(navRoutes).reduce(
  (result, [path, id]) => ({ ...result, [id]: path }),
  {} as Record<NavItem, string>,
);

const labelKeys = {
  dashboard: "dashboard",
  projects: "projects",
  milestones: "milestones",
  releases: "releases",
  reports: "reports",
  baselines: "baselines",
  metrics: "metrics",
  risk: "risk",
  templates: "templates",
  teams: "teams",
  integrations: "integrations",
  settings: "settings",
} as const;

const tabKeys: {
  id: Tab;
  key:
    | "overview"
    | "requirements"
    | "changes"
    | "verification"
    | "evidence"
    | "signoff";
}[] = [
  { id: "overview", key: "overview" },
  { id: "requirements", key: "requirements" },
  { id: "changes", key: "changes" },
  { id: "verification", key: "verification" },
  { id: "evidence", key: "evidence" },
  { id: "signoff", key: "signoff" },
];

const toneClass: Record<Tone, string> = {
  success: "tone-success",
  warning: "tone-warning",
  error: "tone-error",
  progress: "tone-progress",
  neutral: "tone-neutral",
};

function translateData(data: DashboardData, locale: Locale): DashboardData {
  if (locale === "en") return data;
  if (data.project.id === "project_demo") {
    return {
      ...data,
      project: { ...data.project, release: "Release 1.0" },
      selected_requirement: {
        ...data.selected_requirement,
        type: "Funcional",
        priority: "Alta",
        component: "Portal de operaciones",
        baseline: "Alcance v1",
        criteria: data.selected_requirement.criteria.map(
          (criterion) => `Criterio cubierto: ${criterion}`,
        ),
      },
      activity: data.activity.map((item) => ({
        ...item,
        text:
          item.avatar === "maria"
            ? "ha aprobado la línea base"
            : "ha verificado los requisitos",
      })),
      verification_status: data.verification_status.map((item) => ({
        ...item,
        name:
          item.name === "Passed"
            ? "Superados"
            : item.name === "Failed"
              ? "Fallidos"
              : item.name === "In progress"
                ? "En progreso"
                : "No iniciados",
      })),
    };
  }
  const rowTitles: Record<string, string> = {
    "REQ-023": "El usuario puede restablecer la contraseña",
    "REQ-041": "El administrador puede exportar datos de usuario",
    "REQ-057": "Autenticación de dos factores",
    "REQ-063": "Registro de auditoría de cambios de datos",
    "REQ-071": "Importación masiva de usuarios",
  };
  return {
    ...data,
    project: { ...data.project, release: "Release 2.3" },
    requirements: data.requirements.map((row) => ({
      ...row,
      title: rowTitles[row.id] || row.title,
    })),
    selected_requirement: {
      ...data.selected_requirement,
      title: rowTitles["REQ-041"],
      description:
        "Como administrador, quiero exportar los datos de usuarios en formato CSV para realizar análisis externos.",
      type: "Funcional",
      priority: "Alta",
      component: "Gestión de usuarios",
      criteria: [
        "La exportación incluye todos los campos definidos en el diccionario de datos",
        "El archivo CSV se puede descargar desde el panel de administración",
        "La exportación incluye filtros de datos (rango de fechas, rol, estado)",
        "El sistema gestiona hasta 10.000 registros por exportación",
      ],
    },
    activity: data.activity.map((item) => ({
      ...item,
      text:
        item.avatar === "maria"
          ? "ha aprobado el cambio CHG-021"
          : item.avatar === "system"
            ? "ha verificado 5 requisitos"
            : "ha comentado REQ-041",
    })),
    verification_status: data.verification_status.map((item) => ({
      ...item,
      name:
        item.name === "Passed"
          ? "Superados"
          : item.name === "Failed"
            ? "Fallidos"
            : item.name === "In progress"
              ? "En progreso"
              : "No iniciados",
    })),
  };
}

export function ReferenceDashboard() {
  const {
    locale,
    t,
    resolvedTheme,
    themePreference,
    setThemePreference,
    setLocale,
  } = useAppPreferences();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const projectId = searchParams.get("project") || "project_acme";
  const releaseId =
    searchParams.get("release") ||
    (projectId === "project_demo" ? "release_1_0" : "release_2_3");
  const activeNav = (Object.entries(navRoutes).find(
    ([path]) => pathname === path,
  )?.[1] || "dashboard") as NavItem;
  const [data, setData] = useState<DashboardData | null>(null);
  const [loadError, setLoadError] = useState("");
  const [requestVersion, setRequestVersion] = useState(0);
  const activeTab = (
    tabKeys.some((item) => item.id === searchParams.get("tab"))
      ? searchParams.get("tab")
      : "overview"
  ) as Tab;
  const selectedId =
    searchParams.get("requirement") ||
    (projectId === "project_demo" ? "REQ-001" : "REQ-041");
  const drawerOpen =
    pathname === "/dashboard" && searchParams.get("drawer") !== "closed";
  const [search, setSearch] = useState("");
  const [profileOpen, setProfileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [notificationOpen, setNotificationOpen] = useState(false);
  const [statusMenuOpen, setStatusMenuOpen] = useState(false);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [releaseStatusOverride, setReleaseStatusOverride] = useState<{
    contextKey: string;
    status: ReleaseStatus;
  } | null>(null);
  const [verificationRunning, setVerificationRunning] = useState(false);
  const [verificationComplete, setVerificationComplete] = useState(false);
  const [releaseSent, setReleaseSent] = useState(false);
  const [shareStatus, setShareStatus] = useState("");
  const [aiRunning, setAiRunning] = useState(false);
  const [deliveryChecks, setDeliveryChecks] = useState<{
    ready: boolean;
    checks: { key: string; label: string; status: string; detail: string }[];
  } | null>(null);

  const isEs = locale === "es";
  const copy = isEs
    ? {
        ready: "Listo para revisión",
        onHold: "En espera",
        accepted: "Aceptado",
        notifications: "Notificaciones",
        markRead: "Marcar todo como leído",
        noNotifications: "No hay notificaciones nuevas",
        verificationStarted: "Verificación iniciada",
        verificationComplete: "Verificación completada",
        evidenceExported: "Índice de evidencia descargado",
        releaseSent: "Release enviado para aprobación",
        portalOpened: "Portal del cliente abierto",
        reportOpened: "Informe de verificación abierto",
        statusUpdated: "Estado de release actualizado",
        settingsOpened: "Configuración disponible en el perfil",
      }
    : {
        ready: "Ready for review",
        onHold: "On hold",
        accepted: "Accepted",
        notifications: "Notifications",
        markRead: "Mark all as read",
        noNotifications: "No new notifications",
        verificationStarted: "Verification started",
        verificationComplete: "Verification complete",
        evidenceExported: "Evidence index downloaded",
        releaseSent: "Release sent for acceptance",
        portalOpened: "Client portal opened",
        reportOpened: "Verification report opened",
        statusUpdated: "Release status updated",
        settingsOpened: "Settings are available from your profile",
      };

  useEffect(() => {
    let cancelled = false;
    const canonicalUrl = `${API}/api/v1/projects/${projectId}/releases/${releaseId}/dashboard`;
    const compatibilityUrl = `${API}/api/v1/reference-dashboard`;
    fetch(canonicalUrl)
      .then(async (response) => {
        if (response.ok) return response.json();
        if (response.status === 404 && projectId === "project_acme") {
          const fallback = await fetch(compatibilityUrl);
          if (fallback.ok) return fallback.json();
        }
        throw new Error(`dashboard unavailable (${response.status})`);
      })
      .then((payload: DashboardData) => {
        if (!cancelled) {
          setLoadError("");
          setData(payload);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled)
          setLoadError(
            error instanceof Error && error.message.includes("(5")
              ? "Signoff API is unavailable right now. Check the API service and try again."
              : "This workspace is not available from the current API. Restart the API service and try again.",
          );
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, releaseId, requestVersion]);

  const localized = useMemo(
    () =>
      data && data.project.id === projectId
        ? translateData(data, locale)
        : null,
    [data, locale, projectId],
  );
  if (!localized)
    return (
      <WorkspaceLoading
        theme={resolvedTheme}
        error={loadError}
        onRetry={() => setRequestVersion((value) => value + 1)}
      />
    );
  const currentData = localized;
  const selectedRow =
    currentData.requirements.find((item) => item.id === selectedId) ||
    currentData.requirements[0];
  const selected =
    selectedRow.id === currentData.selected_requirement.id
      ? currentData.selected_requirement
      : {
          ...currentData.selected_requirement,
          id: selectedRow.id,
          title: selectedRow.title,
          status: selectedRow.status,
          description:
            locale === "es"
              ? `La entrega debe demostrar: ${selectedRow.title}.`
              : `The delivery must demonstrate: ${selectedRow.title}.`,
          version: "v1.0",
        };
  const filteredRequirements = currentData.requirements.filter((item) =>
    `${item.id} ${item.title}`.toLowerCase().includes(search.toLowerCase()),
  );

  const contextKey = `${projectId}/${releaseId}`;
  const serverReleaseStatus: ReleaseStatus =
    currentData.project.status === "in_signoff"
      ? "in_signoff"
      : currentData.project.status === "accepted"
        ? "accepted"
        : currentData.project.status === "pending_acceptance"
          ? "ready"
          : "on_hold";
  const releaseStatus =
    releaseStatusOverride?.contextKey === contextKey
      ? releaseStatusOverride.status
      : serverReleaseStatus;

  const statusLabel =
    releaseStatus === "accepted"
      ? copy.accepted
      : releaseStatus === "ready"
        ? copy.ready
        : releaseStatus === "on_hold"
          ? copy.onHold
          : t("inSignoff");
  const statusTone =
    releaseStatus === "on_hold" ? "tone-warning" : "tone-success";

  function selectNav(id: NavItem) {
    const path = navRoutesById[id];
    if (path === "/dashboard") {
      router.push(
        `/dashboard?project=${projectId}&release=${releaseId}&tab=overview&requirement=${selectedId}`,
      );
    } else {
      router.push(`${path}?project=${projectId}&release=${releaseId}`);
    }
    setProfileOpen(false);
  }

  function selectRequirement(id: string) {
    const next = new URLSearchParams(searchParams.toString());
    next.set("project", projectId);
    next.set("release", releaseId);
    next.set("tab", activeTab);
    next.set("requirement", id);
    next.delete("drawer");
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }

  function selectTab(tab: Tab) {
    const next = new URLSearchParams(searchParams.toString());
    next.set("project", projectId);
    next.set("release", releaseId);
    next.set("tab", tab);
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }

  function moveRequirement(direction: -1 | 1) {
    const index = currentData.requirements.findIndex(
      (item) => item.id === selectedId,
    );
    const next =
      currentData.requirements[
        (index + direction + currentData.requirements.length) %
          currentData.requirements.length
      ];
    if (next) selectRequirement(next.id);
  }

  async function share() {
    const link = `${window.location.origin}/review/${projectId === "project_acme" ? "acme-review-token" : "demo-review-token"}`;
    try {
      await navigator.clipboard.writeText(link);
      notify(locale === "es" ? "Enlace copiado" : "Link copied");
    } catch {
      notify(link);
    }
  }

  function notify(message: string) {
    setShareStatus(message);
    window.setTimeout(() => setShareStatus(""), 2400);
  }

  async function updateReleaseStatus(next: ReleaseStatus) {
    if (statusUpdating) return;
    setStatusUpdating(true);
    try {
      const response = await fetch(
        `${API}/api/v1/projects/${projectId}/releases/${releaseId}/status`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: next }),
        },
      );
      if (!response.ok) throw new Error("release status unavailable");
      setReleaseStatusOverride({ contextKey, status: next });
      setStatusMenuOpen(false);
      notify(copy.statusUpdated);
    } catch {
      notify(
        locale === "es"
          ? "No se pudo actualizar el estado del release"
          : "Release status could not be updated",
      );
    } finally {
      setStatusUpdating(false);
    }
  }

  async function runVerification() {
    if (verificationRunning) return;
    setVerificationRunning(true);
    setVerificationComplete(false);
    notify(copy.verificationStarted);
    try {
      const response = await fetch(`${API}/api/v1/projects/${projectId}/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requirement_ids: [selectedId] }),
      });
      if (!response.ok) throw new Error("verification unavailable");
      const result = (await response.json()) as {
        evidence?: { state: string }[];
      };
      const state = result.evidence?.[0]?.state;
      setData((current) =>
        current
          ? {
              ...current,
              requirements: current.requirements.map((item) =>
                item.id === selectedId
                  ? {
                      ...item,
                      verification:
                        state === "partially_demonstrated"
                          ? "in_progress"
                          : state === "not_demonstrated"
                            ? "not_started"
                            : "passed",
                      coverage: state === "demonstrated" ? 100 : item.coverage,
                    }
                  : item,
              ),
            }
          : current,
      );
      setVerificationComplete(true);
      notify(copy.verificationComplete);
    } catch {
      notify(
        locale === "es"
          ? "No se pudo ejecutar la verificación"
          : "Verification could not be executed",
      );
    } finally {
      setVerificationRunning(false);
    }
  }

  async function generateCriteria() {
    if (aiRunning) return;
    setAiRunning(true);
    try {
      const response = await fetch(
        `${API}/api/v1/projects/${projectId}/requirements/${selectedId}/criteria`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("criteria unavailable");
      const result = (await response.json()) as {
        id: string;
        criteria: { text: string }[];
      };
      setData((current) =>
        current && current.selected_requirement.id === selectedId
          ? {
              ...current,
              selected_requirement: {
                ...current.selected_requirement,
                criteria: result.criteria.map((item) => item.text),
              },
            }
          : current,
      );
      notify(
        locale === "es"
          ? "Criterios generados como propuesta"
          : "Criteria generated as a proposal",
      );
    } catch {
      notify(
        locale === "es"
          ? "No se pudieron generar los criterios"
          : "Criteria could not be generated",
      );
    } finally {
      setAiRunning(false);
    }
  }

  async function prepareDelivery() {
    try {
      const response = await fetch(
        `${API}/api/v1/projects/${projectId}/prepare-delivery`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("readiness unavailable");
      const result = (await response.json()) as {
        ready: boolean;
        checks: {
          key: string;
          label: string;
          status: string;
          detail: string;
        }[];
      };
      setDeliveryChecks(result);
      notify(
        locale === "es"
          ? result.ready
            ? "Entrega preparada"
            : "La entrega necesita atención"
          : result.ready
            ? "Delivery prepared"
            : "Delivery needs attention",
      );
    } catch {
      notify(
        locale === "es"
          ? "No se pudo calcular la preparación"
          : "Delivery readiness could not be calculated",
      );
    }
  }

  function exportEvidence() {
    const payload = {
      release: currentData.project,
      requirement: selected,
      verification: {
        status: selectedRow.verification,
        coverage: selectedRow.coverage,
      },
      generatedAt: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selected.id.toLowerCase()}-evidence.json`;
    link.click();
    URL.revokeObjectURL(url);
    notify(copy.evidenceExported);
  }

  function openPortal() {
    window.open(
      `/review/${projectId === "project_acme" ? "acme-review-token" : "demo-review-token"}`,
      "_blank",
      "noopener,noreferrer",
    );
    notify(copy.portalOpened);
  }

  async function sendForAcceptance() {
    if (statusUpdating) return;
    setStatusUpdating(true);
    try {
      const response = await fetch(
        `${API}/api/v1/projects/${projectId}/releases/${releaseId}/send-for-acceptance`,
        { method: "POST" },
      );
      if (!response.ok) throw new Error("release acceptance unavailable");
      setReleaseStatusOverride({ contextKey, status: "ready" });
      setReleaseSent(true);
      setMenuOpen(false);
      notify(copy.releaseSent);
    } catch {
      notify(
        locale === "es"
          ? "No se pudo enviar el release a aprobación"
          : "Release could not be sent for acceptance",
      );
    } finally {
      setStatusUpdating(false);
    }
  }

  return (
    <div className={`reference-dashboard reference-${resolvedTheme}`}>
      <aside className="reference-sidebar">
        <div className="reference-brand">
          <BrandLockup compact priority />
        </div>
        <nav className="reference-nav" aria-label={t("dashboard")}>
          {navGroups.map((group, groupIndex) => (
            <div
              className="reference-nav-group"
              key={group.label || groupIndex}
            >
              {group.label && (
                <div className="reference-nav-label">{group.label}</div>
              )}
              {group.items.map(({ id, icon: Icon, label }) => (
                <button
                  key={id}
                  className={`reference-nav-item${activeNav === id ? " is-active" : ""}`}
                  onClick={() => selectNav(id)}
                >
                  <Icon size={17} strokeWidth={1.55} />
                  <span>{t(labelKeys[label])}</span>
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
            <Avatar variant="diego" initials="DP" />
            <span>
              <strong>{currentData.project.client}</strong>
              <small>Diego Pérez</small>
            </span>
            <ChevronDown size={15} />
          </button>
          {profileOpen && (
            <div className="reference-profile-menu">
              <div className="reference-profile-heading">{t("settings")}</div>
              <label>
                {t("language")}
                <select
                  value={locale}
                  onChange={(event) => setLocale(event.target.value as Locale)}
                >
                  <option value="en">English</option>
                  <option value="es">Español</option>
                </select>
              </label>
              <label>
                {t("theme")}
                <select
                  value={themePreference}
                  onChange={(event) =>
                    setThemePreference(event.target.value as ThemePreference)
                  }
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
            <label className="reference-search">
              <Search size={16} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t("search")}
                aria-label={t("search")}
              />
              <kbd>
                <Command size={11} />K
              </kbd>
            </label>
            <div className="reference-notification-wrap">
              <button
                className="reference-icon-button"
                aria-label={copy.notifications}
                aria-expanded={notificationOpen}
                onClick={() => setNotificationOpen((value) => !value)}
              >
                <Bell size={18} />
                <span className="reference-notification-dot" />
              </button>
              {notificationOpen && (
                <div className="reference-notification-panel">
                  <div>
                    <strong>{copy.notifications}</strong>
                    <button onClick={() => notify(copy.markRead)}>
                      {copy.markRead}
                    </button>
                  </div>
                  <button
                    onClick={() => {
                      selectTab("verification");
                      setNotificationOpen(false);
                    }}
                  >
                    <CircleAlert size={15} />
                    <span>
                      <strong>
                        {isEs
                          ? "11 verificaciones fallidas"
                          : "11 failed verifications"}
                      </strong>
                      <small>
                        {isEs ? "Requieren revisión" : "Need review"}
                      </small>
                    </span>
                  </button>
                  <button
                    onClick={() => {
                      selectTab("changes");
                      setNotificationOpen(false);
                    }}
                  >
                    <RefreshCw size={15} />
                    <span>
                      <strong>
                        {isEs ? "2 cambios pendientes" : "2 pending changes"}
                      </strong>
                      <small>{isEs ? "Change Radar" : "Change Radar"}</small>
                    </span>
                  </button>
                </div>
              )}
            </div>
            <button
              className="reference-theme-toggle"
              onClick={() =>
                setThemePreference(resolvedTheme === "dark" ? "light" : "dark")
              }
              aria-label={
                resolvedTheme === "dark"
                  ? t("switchToLight")
                  : t("switchToDark")
              }
              title={
                resolvedTheme === "dark"
                  ? t("switchToLight")
                  : t("switchToDark")
              }
            >
              {resolvedTheme === "dark" ? (
                <Sun size={17} />
              ) : (
                <Moon size={17} />
              )}
            </button>
            <button
              className="reference-user-button"
              onClick={() => setProfileOpen((value) => !value)}
              aria-label={t("settings")}
            >
              <Avatar variant="diego" initials="DP" />
              <ChevronDown size={14} />
            </button>
          </div>
        </header>
        {activeNav === "dashboard" && (
          <div className="reference-context-strip" aria-label={isEs ? "Contexto del release" : "Release context"}>
            <div className="reference-context-lead">
              <span className="reference-context-kicker">{isEs ? "CONTEXTO ACTIVO" : "ACTIVE CONTEXT"}</span>
              <strong>{currentData.project.client} · {currentData.project.release}</strong>
            </div>
            <div className="reference-context-item">
              <span className="context-indicator context-indicator-error" />
              <span>
                <small>{isEs ? "Atención" : "Attention"}</small>
                <strong>{isEs ? "11 verificaciones fallidas" : "11 failed verifications"}</strong>
              </span>
            </div>
            <div className="reference-context-item">
              <span className="context-indicator context-indicator-warning" />
              <span>
                <small>{isEs ? "Siguiente decisión" : "Next decision"}</small>
                <strong>{isEs ? "Aprobación del cliente" : "Client sign-off"}</strong>
              </span>
            </div>
            <button className="reference-context-action" onClick={() => selectTab("verification")}>
              {isEs ? "Revisar hallazgos" : "Review findings"}
              <ArrowUpRight size={15} />
            </button>
            <AgentDock api={API} projectId={projectId} requirementId={selectedId} locale={locale} />
          </div>
        )}
        {activeNav === "dashboard" ? (
          <>
            <section className="reference-release-header">
              <div>
                <div className="reference-title-row">
                  <h1>
                    {currentData.project.release} – {currentData.project.client}
                  </h1>
                  <div className="reference-status-wrap">
                    <button
                      className="reference-status-select"
                      onClick={() => setStatusMenuOpen((value) => !value)}
                      aria-expanded={statusMenuOpen}
                    >
                      <span className={`status-dot ${statusTone}`} />
                      {statusLabel}
                      <ChevronDown size={13} />
                    </button>
                    {statusMenuOpen && (
                      <div className="reference-status-menu">
                        <button
                          onClick={() => updateReleaseStatus("in_signoff")}
                        >
                          <span className="status-dot tone-success" />
                          {t("inSignoff")}
                        </button>
                        <button onClick={() => updateReleaseStatus("ready")}>
                          <span className="status-dot tone-progress" />
                          {copy.ready}
                        </button>
                        <button onClick={() => updateReleaseStatus("on_hold")}>
                          <span className="status-dot tone-warning" />
                          {copy.onHold}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                <p>
                  {currentData.project.version} <span>·</span>{" "}
                  {currentData.project.created_at.slice(0, 10)} <span>·</span>{" "}
                  {currentData.project.target_date.slice(0, 10)}
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
                    aria-label="More actions"
                  >
                    <MoreHorizontal size={19} />
                  </button>
                  {menuOpen && (
                    <div className="reference-action-menu">
                      <button onClick={share}>
                        <Link2 size={14} />{" "}
                        {locale === "es"
                          ? "Copiar enlace de revisión"
                          : "Copy review link"}
                      </button>
                      <button
                        onClick={() => {
                          selectTab("verification");
                          setMenuOpen(false);
                          notify(copy.reportOpened);
                        }}
                      >
                        <FileBarChart2 size={14} />{" "}
                        {locale === "es" ? "Abrir informe" : "Open report"}
                      </button>
                      <button
                        onClick={() => {
                          sendForAcceptance();
                          setMenuOpen(false);
                        }}
                      >
                        <Send size={14} />{" "}
                        {locale === "es"
                          ? "Enviar a aprobación"
                          : "Send for acceptance"}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </section>
            <div className="reference-tabs" role="tablist">
              {tabKeys.map(({ id, key }) => (
                <button
                  key={id}
                  role="tab"
                  aria-selected={activeTab === id}
                  className={activeTab === id ? "is-active" : ""}
                  onClick={() => selectTab(id)}
                >
                  {t(key)}
                </button>
              ))}
            </div>
            <section className="reference-workspace">
              {activeTab === "overview" ? (
                <Overview
                  data={currentData}
                  requirements={filteredRequirements}
                  selectedId={selectedId}
                  onSelect={selectRequirement}
                  onOpenTab={selectTab}
                  t={t}
                />
              ) : (
                <TabView
                  tab={activeTab}
                  data={currentData}
                  requirements={filteredRequirements}
                  onSelect={selectRequirement}
                  onRunVerification={runVerification}
                  onExportEvidence={exportEvidence}
                  onSendForAcceptance={sendForAcceptance}
                  onOpenPortal={openPortal}
                  verificationRunning={verificationRunning}
                  releaseSent={releaseSent}
                  projectId={projectId}
                  aiRunning={aiRunning}
                  deliveryChecks={deliveryChecks}
                  onGenerateCriteria={generateCriteria}
                  onPrepareDelivery={prepareDelivery}
                  notify={notify}
                  t={t}
                />
              )}
              {drawerOpen && (
                <RequirementDrawer
                  key={selectedId}
                  requirement={selected}
                  selectedId={selectedId}
                  onClose={() => {
                    const next = new URLSearchParams(searchParams.toString());
                    next.delete("requirement");
                    next.set("drawer", "closed");
                    router.replace(`${pathname}?${next.toString()}`, {
                      scroll: false,
                    });
                  }}
                  onPrevious={() => moveRequirement(-1)}
                  onNext={() => moveRequirement(1)}
                  onRunVerification={runVerification}
                  onExportEvidence={exportEvidence}
                  onOpenVerification={() => {
                    selectTab("verification");
                    const next = new URLSearchParams(searchParams.toString());
                    next.set("tab", "verification");
                    next.set("drawer", "closed");
                    router.replace(`${pathname}?${next.toString()}`, {
                      scroll: false,
                    });
                  }}
                  verificationRunning={verificationRunning}
                  verificationComplete={verificationComplete}
                  releaseName={currentData.project.release}
                  notify={notify}
                  t={t}
                />
              )}
            </section>
          </>
        ) : (
          <GlobalSurface
            surface={activeNav}
            projectId={projectId}
            releaseId={releaseId}
            data={currentData}
            onOpenProject={(nextProjectId, nextReleaseId) =>
              router.push(
                `/dashboard?project=${nextProjectId}&release=${nextReleaseId}&tab=overview&requirement=${nextProjectId === "project_acme" ? "REQ-041" : "REQ-001"}`,
              )
            }
            notify={notify}
          />
        )}
        {shareStatus && (
          <div className="reference-toast">
            <Check size={14} />
            {shareStatus}
          </div>
        )}
      </main>
    </div>
  );
}

function WorkspaceLoading({
  theme,
  error,
  onRetry,
}: {
  theme: "light" | "dark";
  error?: string;
  onRetry: () => void;
}) {
  return (
    <div className={`reference-dashboard reference-${theme}`}>
      <main className="reference-main">
        <div className="reference-loading">
          <BrandLockup compact priority />
          {error ? (
            <>
              <span>{error}</span>
              <button className="reference-primary-button" onClick={onRetry}>
                <RefreshCw size={15} />
                Retry
              </button>
            </>
          ) : (
            <span>Loading workspace…</span>
          )}
        </div>
      </main>
    </div>
  );
}

type CatalogProject = {
  id: string;
  name: string;
  client: string;
  description: string;
  release_id: string;
  release: string;
  baseline: string;
  status: string;
  requirements_count: number;
};
type CatalogRelease = {
  id: string;
  project_id: string;
  name: string;
  version: string;
  status: string;
  created_at: string;
  target_date: string;
  baseline: string;
};

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Signoff API returned ${response.status}`);
  return response.json() as Promise<T>;
}

function GlobalSurface({
  surface,
  projectId,
  releaseId,
  data,
  onOpenProject,
  notify,
}: {
  surface: NavItem;
  projectId: string;
  releaseId: string;
  data: DashboardData;
  onOpenProject: (projectId: string, releaseId: string) => void;
  notify: (message: string) => void;
}) {
  const {
    locale,
    t,
    resolvedTheme,
    themePreference,
    setThemePreference,
    setLocale,
  } = useAppPreferences();
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: () =>
      getJson<{ items: CatalogProject[] }>(`${API}/api/v1/projects`),
  });
  const releasesQuery = useQuery({
    queryKey: ["releases", projectId],
    queryFn: () =>
      getJson<{ items: CatalogRelease[] }>(
        `${API}/api/v1/projects/${projectId}/releases`,
      ),
    enabled: ["releases", "milestones", "reports"].includes(surface),
  });
  const attentionQuery = useQuery({
    queryKey: ["attention", projectId],
    queryFn: () =>
      getJson<Array<{ severity: string; title: string; source: string }>>(
        `${API}/api/v1/projects/${projectId}/attention`,
      ),
    enabled: surface === "risk",
  });
  const scopeQuery = useQuery({
    queryKey: ["scope-versions", projectId],
    queryFn: () =>
      getJson<
        Array<{
          version: string;
          status: string;
          source: string;
          summary: string;
        }>
      >(`${API}/api/v1/projects/${projectId}/scope/versions`),
    enabled: surface === "baselines",
  });
  const [scopeFile, setScopeFile] = useState<File | null>(null);
  const [scopeBusy, setScopeBusy] = useState(false);
  const [scopeResult, setScopeResult] = useState<{
    filename: string;
    version: string;
    message: string;
  } | null>(null);
  const labels: Record<NavItem, { title: string; description: string }> = {
    dashboard: { title: t("dashboard"), description: "" },
    projects: {
      title: t("projects"),
      description:
        locale === "es"
          ? "Todos tus espacios de entrega, con el contexto que los conecta."
          : "Every delivery workspace, with the context that connects it.",
    },
    milestones: {
      title: t("milestones"),
      description:
        locale === "es"
          ? "Hitos y fechas de cada release."
          : "Milestones and dates for each release.",
    },
    releases: {
      title: t("releases"),
      description:
        locale === "es"
          ? "Un inventario de releases listo para revisar."
          : "A release inventory ready to review.",
    },
    reports: {
      title: t("reports"),
      description:
        locale === "es"
          ? "Historias de entrega y paquetes de evidencia."
          : "Delivery stories and evidence packs.",
    },
    baselines: {
      title: t("baselines"),
      description:
        locale === "es"
          ? "Líneas base aprobadas y sus versiones."
          : "Approved baselines and their versions.",
    },
    metrics: {
      title: t("metrics"),
      description:
        locale === "es"
          ? "Cobertura, verificación y aceptación desde una sola fuente."
          : "Coverage, verification and acceptance from one source.",
    },
    risk: {
      title: t("risk"),
      description:
        locale === "es"
          ? "Atención priorizada sobre cambios, evidencia y aceptación."
          : "Prioritized attention across changes, evidence and acceptance.",
    },
    templates: {
      title: t("templates"),
      description:
        locale === "es"
          ? "Plantillas para arrancar una entrega trazable."
          : "Templates to start a traceable delivery.",
    },
    teams: {
      title: t("teams"),
      description:
        locale === "es"
          ? "Personas y roles de esta organización."
          : "People and roles in this organization.",
    },
    integrations: {
      title: t("integrations"),
      description:
        locale === "es"
          ? "Conexiones que aportan referencias, no duplican tu source of truth."
          : "Connections that add references without replacing your source of truth.",
    },
    settings: {
      title: t("settings"),
      description:
        locale === "es"
          ? "Preferencias de idioma y apariencia del workspace."
          : "Workspace language and appearance preferences.",
    },
  };
  const label = labels[surface];
  const projects = projectsQuery.data?.items || [];
  const releases = releasesQuery.data?.items || [];

  function downloadReport() {
    const payload = {
      project: data.project,
      metrics: data.metrics,
      requirements: data.requirements,
      generatedAt: new Date().toISOString(),
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(payload, null, 2)], {
        type: "application/json",
      }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${data.project.name.toLowerCase().replaceAll(" ", "-")}-delivery-report.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    notify(locale === "es" ? "Informe descargado" : "Report downloaded");
  }

  async function importBaseline() {
    if (!scopeFile) {
      notify(
        locale === "es"
          ? "Selecciona un documento primero"
          : "Select a document first",
      );
      return;
    }
    setScopeBusy(true);
    try {
      const form = new FormData();
      form.append("file", scopeFile);
      const response = await fetch(
        `${API}/api/v1/projects/${projectId}/scope/extract`,
        { method: "POST", body: form },
      );
      if (!response.ok) throw new Error("baseline import unavailable");
      const result = await response.json();
      setScopeResult(result);
      await scopeQuery.refetch();
      notify(
        locale === "es"
          ? "Documento importado como borrador"
          : "Document imported as draft",
      );
    } catch {
      notify(
        locale === "es"
          ? "No se pudo importar el documento"
          : "Document could not be imported",
      );
    } finally {
      setScopeBusy(false);
    }
  }

  return (
    <section className="reference-global-surface">
      <div className="reference-global-heading">
        <div>
          <span className="reference-eyebrow">
            {data.project.name} · {data.project.release}
          </span>
          <h1>{label.title}</h1>
          <p>{label.description}</p>
        </div>
        {surface === "reports" && (
          <button className="reference-primary-button" onClick={downloadReport}>
            <Download size={16} />
            {locale === "es" ? "Descargar informe" : "Download report"}
          </button>
        )}
      </div>
      {surface === "projects" && (
        <div className="reference-global-grid">
          {projects.map((project) => (
            <article
              className={`reference-card reference-project-card${project.id === projectId ? " is-current" : ""}`}
              key={project.id}
            >
              <div className="reference-project-card-top">
                <FolderKanban size={19} />
                <span className="reference-pill pill-agreed">
                  {project.status.replace("_", " ")}
                </span>
              </div>
              <h2>{project.name}</h2>
              <p>{project.description}</p>
              <div className="reference-project-meta">
                <span>{project.client}</span>
                <span>
                  {project.requirements_count} {t("requirements").toLowerCase()}
                </span>
              </div>
              <button
                className="reference-secondary-button"
                onClick={() => onOpenProject(project.id, project.release_id)}
              >
                {locale === "es" ? "Abrir proyecto" : "Open project"}
                <ChevronRight size={15} />
              </button>
            </article>
          ))}
        </div>
      )}
      {["releases", "milestones"].includes(surface) && (
        <div className="reference-card reference-global-list">
          {releases.map((release) => (
            <button
              className="reference-global-row"
              key={release.id}
              onClick={() => onOpenProject(release.project_id, release.id)}
            >
              <span>
                <Rocket size={16} />
                <strong>{release.name}</strong>
                <small>
                  {release.version} · {release.baseline}
                </small>
              </span>
              <span className="reference-pill pill-agreed">
                {release.status.replace("_", " ")}
              </span>
              <ChevronRight size={16} />
            </button>
          ))}
        </div>
      )}
      {surface === "reports" && (
        <div className="reference-global-grid">
          <article className="reference-card reference-report-card">
            <FileBarChart2 size={22} />
            <h2>{locale === "es" ? "Delivery report" : "Delivery report"}</h2>
            <p>
              {locale === "es"
                ? "Una exportación de la vista actual, siempre limitada al proyecto y release seleccionados."
                : "An export of the current view, always scoped to the selected project and release."}
            </p>
          </article>
          <article className="reference-card reference-report-card">
            <PanelsTopLeft size={22} />
            <h2>Evidence pack</h2>
            <p>
              {locale === "es"
                ? "La evidencia se genera desde los mismos requisitos y runs del release."
                : "Evidence is generated from the same release requirements and runs."}
            </p>
          </article>
        </div>
      )}
      {surface === "releases" && (
        <div className="reference-release-insight" aria-label={locale === "es" ? "Estado del release" : "Release context"}>
          <div>
            <span>{locale === "es" ? "ESTADO ACTUAL" : "CURRENT STATE"}</span>
            <strong>{data.project.status === "in_signoff" ? (locale === "es" ? "En aprobación" : "In signoff") : data.project.status.replace("_", " ")}</strong>
            <small>{locale === "es" ? "La entrega está en revisión del cliente." : "The delivery is currently with the client for review."}</small>
          </div>
          <div>
            <span>{locale === "es" ? "COBERTURA" : "COVERAGE"}</span>
            <strong>{data.metrics.coverage.value}%</strong>
            <small>{locale === "es" ? "Requisitos con evidencia trazable." : "Requirements with traceable evidence."}</small>
          </div>
          <div>
            <span>{locale === "es" ? "PRÓXIMO HITO" : "NEXT MILESTONE"}</span>
            <strong>{data.project.target_date.slice(0, 10)}</strong>
            <small>{locale === "es" ? "Fecha objetivo de aprobación." : "Target sign-off date."}</small>
          </div>
        </div>
      )}
      {surface === "baselines" && (
        <div className="reference-card reference-global-list">
          <div className="reference-baseline-import">
            <label className="reference-file-picker">
              <FileStack size={16} />
              <span>
                {scopeFile
                  ? scopeFile.name
                  : locale === "es"
                    ? "Seleccionar SOW, PDF, DOCX o TXT"
                    : "Select SOW, PDF, DOCX or TXT"}
              </span>
              <input
                type="file"
                accept=".pdf,.docx,.txt,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={(event) =>
                  setScopeFile(event.target.files?.[0] || null)
                }
              />
            </label>
            <button
              className="reference-secondary-button"
              onClick={importBaseline}
              disabled={scopeBusy || !scopeFile}
            >
              {scopeBusy ? (
                <RefreshCw size={14} className="reference-spin" />
              ) : (
                <Sparkles size={14} />
              )}
              {scopeBusy
                ? locale === "es"
                  ? "Extrayendo…"
                  : "Extracting…"
                : locale === "es"
                  ? "Extraer baseline con IA"
                  : "Extract baseline with AI"}
            </button>
          </div>
          {scopeResult && (
            <div className="reference-inspection-result">
              <CheckCircle2 size={15} />
              <span>
                {scopeResult.filename} · {scopeResult.version} ·{" "}
                {scopeResult.message}
              </span>
            </div>
          )}
          {(
            scopeQuery.data || [
              {
                version:
                  data.project.name === "Acme Inc." ? "BR-1.4" : "Scope v1",
                status: "approved",
                source: "Approved project baseline",
                summary: "Frozen baseline used by this release.",
              },
            ]
          ).map((item) => (
            <div className="reference-global-row" key={item.version}>
              <span>
                <PanelsTopLeft size={16} />
                <strong>{item.version}</strong>
                <small>
                  {item.source} · {item.summary}
                </small>
              </span>
              <span className="reference-pill pill-agreed">{item.status}</span>
            </div>
          ))}
        </div>
      )}
      {surface === "metrics" && (
        <div className="reference-metrics reference-global-metrics">
          {Object.entries(data.metrics).map(([key, metric]) => (
            <MetricCard
              key={key}
              title={t(
                key === "requirements"
                  ? "requirementCount"
                  : key === "verification"
                    ? "verificationCount"
                    : key === "coverage"
                      ? "coverageCount"
                      : "changesCount",
              )}
              metric={metric}
              icon={
                key === "requirements"
                  ? "requirements"
                  : key === "verification"
                    ? "verification"
                    : key === "changes"
                      ? "changes"
                      : "coverage"
              }
              t={t}
              trend={key === "coverage" ? data.coverage_trend : undefined}
            />
          ))}
        </div>
      )}
      {surface === "risk" && (
        <div className="reference-card reference-global-list">
          {(attentionQuery.data || []).map((item) => (
            <div className="reference-global-row" key={item.title}>
              <span>
                <TriangleAlert size={16} />
                <strong>{item.title}</strong>
                <small>{item.source}</small>
              </span>
              <span
                className={`reference-pill ${item.severity === "critical" ? "pill-rejected" : "pill-pending"}`}
              >
                {item.severity}
              </span>
            </div>
          ))}
        </div>
      )}
      {surface === "templates" && (
        <div className="reference-global-grid">
          {[
            "Agreement baseline",
            "Acceptance criteria set",
            "Delivery pack",
          ].map((template) => (
            <article
              className="reference-card reference-template-card"
              key={template}
            >
              <FileStack size={20} />
              <h2>{template}</h2>
              <p>
                {locale === "es"
                  ? "Estructura reutilizable para mantener trazabilidad."
                  : "Reusable structure for traceable delivery."}
              </p>
              <button
                className="reference-secondary-button"
                onClick={() =>
                  notify(
                    locale === "es"
                      ? "Plantilla preparada para este proyecto"
                      : "Template prepared for this project",
                  )
                }
              >
                {locale === "es" ? "Usar plantilla" : "Use template"}
                <ChevronRight size={15} />
              </button>
            </article>
          ))}
        </div>
      )}
      {surface === "teams" && (
        <div className="reference-global-grid">
          <article className="reference-card reference-team-card">
            <Avatar variant="diego" initials="DP" />
            <h2>Diego Pérez</h2>
            <p>Owner · {data.project.client}</p>
          </article>
          <article className="reference-card reference-team-card">
            <Avatar variant="maria" initials="ML" />
            <h2>María López</h2>
            <p>Client reviewer · {data.project.client}</p>
          </article>
        </div>
      )}
      {surface === "integrations" && (
        <div className="reference-global-grid">
          <article className="reference-card reference-integration-card">
            <Link2 size={20} />
            <h2>Manual references</h2>
            <p>
              {locale === "es"
                ? "Añade Jira, GitHub o CI/CD como referencias auditables."
                : "Add Jira, GitHub or CI/CD as auditable references."}
            </p>
            <span className="reference-pill pill-pending">
              {locale === "es" ? "Preparado" : "Prepared"}
            </span>
          </article>
          <article className="reference-card reference-integration-card">
            <Workflow size={20} />
            <h2>Verification providers</h2>
            <p>Browser Agent · File Inspector · Human Evidence</p>
            <span className="reference-pill pill-agreed">
              {locale === "es" ? "Activo en mock" : "Active in mock"}
            </span>
          </article>
        </div>
      )}
      {surface === "settings" && (
        <div className="reference-card reference-settings-card">
          <label>
            {t("language")}
            <select
              value={locale}
              onChange={(event) => setLocale(event.target.value as Locale)}
            >
              <option value="en">English</option>
              <option value="es">Español</option>
            </select>
          </label>
          <label>
            {t("theme")}
            <select
              value={themePreference}
              onChange={(event) =>
                setThemePreference(event.target.value as ThemePreference)
              }
            >
              <option value="dark">{t("dark")}</option>
              <option value="light">{t("light")}</option>
              <option value="system">{t("system")}</option>
            </select>
          </label>
          <div className="reference-settings-preview">
            <span
              className={`status-dot ${resolvedTheme === "dark" ? "tone-progress" : "tone-success"}`}
            />
            {locale === "es"
              ? `Tema ${resolvedTheme === "dark" ? "oscuro" : "claro"} activo`
              : `${resolvedTheme === "dark" ? "Dark" : "Light"} theme active`}
          </div>
        </div>
      )}
    </section>
  );
}

function Overview({
  data,
  requirements,
  selectedId,
  onSelect,
  onOpenTab,
  t,
}: {
  data: DashboardData;
  requirements: RequirementRow[];
  selectedId: string;
  onSelect: (id: string) => void;
  onOpenTab: (tab: Tab) => void;
  t: Translate;
}) {
  return (
    <>
      <div className="reference-metrics">
        <MetricCard
          title={t("requirementCount")}
          metric={data.metrics.requirements}
          icon="requirements"
          onClick={() => onOpenTab("requirements")}
          t={t}
        />
        <MetricCard
          title={t("verificationCount")}
          metric={data.metrics.verification}
          icon="verification"
          onClick={() => onOpenTab("verification")}
          t={t}
        />
        <MetricCard
          title={t("coverageCount")}
          metric={data.metrics.coverage}
          icon="coverage"
          onClick={() => onOpenTab("verification")}
          t={t}
          trend={data.coverage_trend}
        />
        <MetricCard
          title={t("changesCount")}
          metric={data.metrics.changes}
          icon="changes"
          onClick={() => onOpenTab("changes")}
          t={t}
        />
      </div>
      <div className="reference-content-grid">
        <div className="reference-main-column">
          <div className="reference-requirements-row">
            <RequirementsCard
              requirements={requirements}
              selectedId={selectedId}
              onSelect={onSelect}
              t={t}
            />
            <RequirementStatusCard selectedId={selectedId} t={t} />
          </div>
          <div className="reference-bottom-grid">
            <ActivityCard items={data.activity} onOpenTab={onOpenTab} t={t} />
            <VerificationCard
              data={data.verification_status}
              value={data.metrics.verification.value}
              onOpenTab={onOpenTab}
              t={t}
            />
          </div>
        </div>
      </div>
    </>
  );
}

function MetricCard({
  title,
  metric,
  icon,
  t,
  trend,
  onClick,
}: {
  title: string;
  metric: DashboardData["metrics"][string];
  icon: string;
  t: Translate;
  trend?: number[];
  onClick?: () => void;
}) {
  const Icon =
    icon === "requirements"
      ? FileStack
      : icon === "changes"
        ? Workflow
        : icon === "verification"
          ? CircleCheck
          : Gauge;
  const coverageChart = useChartSize();
  const miniRingChart = useChartSize();
  const reducedMotion = useReducedMotion();
  const miniRingData = [
    { name: "verified", value: metric.value, fill: "#1DB954" },
    {
      name: "remaining",
      value: Math.max(0, 100 - metric.value),
      fill: "#1c2638",
    },
  ];
  function handleKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (onClick && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      onClick();
    }
  }
  return (
    <article
      className={`reference-metric-card${onClick ? " is-interactive" : ""}`}
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
      <strong className="reference-metric-value">
        {metric.value}
        {metric.suffix}
      </strong>
      {trend ? (
        <div className="reference-coverage-chart">
          <div ref={coverageChart.setElement} className="reference-chart-frame">
            {coverageChart.width > 0 && coverageChart.height > 0 && (
              <AreaChart
                width={coverageChart.width}
                height={coverageChart.height}
                data={trend.map((value, index) => ({ index, value }))}
              >
                <defs>
                  <linearGradient id="coverageFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6b61ff" stopOpacity={0.32} />
                    <stop
                      offset="100%"
                      stopColor="#6b61ff"
                      stopOpacity={0.03}
                    />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="value"
                  stroke="#786dff"
                  strokeWidth={1.8}
                  fill="url(#coverageFill)"
                  dot={false}
                  isAnimationActive={!reducedMotion}
                  animationDuration={520}
                  animationEasing="ease-out"
                />
                <Tooltip content={() => null} />
              </AreaChart>
            )}
          </div>
        </div>
      ) : icon === "verification" ? (
        <div ref={miniRingChart.setElement} className="reference-mini-ring">
          {miniRingChart.width > 0 && miniRingChart.height > 0 && (
            <PieChart width={miniRingChart.width} height={miniRingChart.height}>
              <Pie
                data={miniRingData}
                dataKey="value"
                innerRadius="70%"
                outerRadius="100%"
                startAngle={90}
                endAngle={-270}
                paddingAngle={1}
                cornerRadius={4}
                stroke="none"
                isAnimationActive={!reducedMotion}
                animationDuration={520}
                animationEasing="ease-out"
              >
                <Cell fill={miniRingData[0].fill} />
                <Cell fill={miniRingData[1].fill} />
              </Pie>
            </PieChart>
          )}
        </div>
      ) : null}
      <div className="reference-metric-items">
        {metric.items.map((item) => (
          <span key={`${item.label}-${item.value}`}>
            <i className={`status-dot ${toneClass[item.tone]}`} />
            <b>
              {item.value}
              {icon === "coverage" ? "%" : ""}
            </b>{" "}
            {item.label === "vs last release"
              ? ` ${t("vsLastRelease")}`
              : item.label === "out of scope"
                ? t("outOfScope")
                : item.label === "in progress"
                  ? t("inProgress")
                  : item.label === "not started"
                    ? t("notStarted")
                    : item.label === "passed"
                      ? t("passed")
                      : item.label === "failed"
                        ? t("failed")
                        : item.label === "pending"
                          ? t("pending")
                          : item.label === "approved"
                            ? t("agreed") === "Acordado"
                              ? "aprobados"
                              : "approved"
                            : item.label === "rejected"
                              ? t("rejected")
                              : item.label === "agreed"
                                ? t("agreed")
                                : item.label}
          </span>
        ))}
      </div>
    </article>
  );
}

function RequirementsCard({
  requirements,
  selectedId,
  onSelect,
  t,
}: {
  requirements: RequirementRow[];
  selectedId: string;
  onSelect: (id: string) => void;
  t: Translate;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <article className="reference-card reference-requirements-card">
      <div className="reference-card-heading">
        <h2>{t("topRequirements")}</h2>
        <div className="reference-card-heading-action">
          <button
            aria-label={t("settings")}
            onClick={() => setMenuOpen((value) => !value)}
          >
            <MoreHorizontal size={18} />
          </button>
          {menuOpen && (
            <div className="reference-inline-menu">
              <button
                onClick={() => {
                  onSelect(
                    requirements[requirements.length - 1]?.id || selectedId,
                  );
                  setMenuOpen(false);
                }}
              >
                {t("pending")}
              </button>
              <button onClick={() => setMenuOpen(false)}>{t("close")}</button>
            </div>
          )}
        </div>
      </div>
      <div className="reference-table-header">
        <span>ID</span>
        <span>TITLE</span>
        <span>{t("status").toUpperCase()}</span>
        <span>{t("verification").toUpperCase()}</span>
        <span>{t("coverage").toUpperCase()}</span>
        <span />
      </div>
      <div className="reference-table-body">
        {requirements.length ? (
          requirements.map((item) => (
            <button
              key={item.id}
              className={`reference-requirement-row${selectedId === item.id ? " is-selected" : ""}`}
              onClick={() => onSelect(item.id)}
            >
              <span className="reference-req-id">{item.id}</span>
              <span className="reference-req-title">{item.title}</span>
              <span>
                <span
                  className={`reference-pill ${item.status === "agreed" ? "pill-agreed" : "pill-pending"}`}
                >
                  {item.status === "agreed" ? t("agreed") : t("pending")}
                </span>
              </span>
              <span className="reference-verification-status">
                <span
                  className={`status-dot ${item.verification === "passed" ? "tone-success" : item.verification === "in_progress" ? "tone-progress" : "tone-neutral"}`}
                />
                {item.verification === "passed"
                  ? t("passed")
                  : item.verification === "in_progress"
                    ? t("inProgress")
                    : t("notStarted")}
              </span>
              <span className="reference-coverage-cell">
                <span>{item.coverage}%</span>
                <CoverageBar value={item.coverage} />
              </span>
              <ChevronRight size={15} />
            </button>
          ))
        ) : (
          <div className="reference-empty">{t("noResults")}</div>
        )}
      </div>
    </article>
  );
}

function CoverageBar({ value }: { value: number }) {
  const chart = useChartSize();
  const reducedMotion = useReducedMotion();
  return (
    <span ref={chart.setElement} className="reference-progress">
      {chart.width > 0 && chart.height > 0 && (
        <BarChart
          width={chart.width}
          height={chart.height}
          data={[{ name: "coverage", value }]}
          layout="vertical"
          margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
        >
          <XAxis type="number" domain={[0, 100]} hide />
          <YAxis type="category" dataKey="name" hide />
          <Bar
            dataKey="value"
            fill="#7069ff"
            radius={[999, 999, 999, 999]}
            background={{ fill: "#202a3b", radius: 999 }}
            isAnimationActive={!reducedMotion}
            animationDuration={420}
            animationEasing="ease-out"
          />
        </BarChart>
      )}
    </span>
  );
}

function RequirementStatusCard({
  selectedId,
  t,
}: {
  selectedId: string;
  t: Translate;
}) {
  return (
    <article className="reference-card reference-requirement-status-card">
      <span className="reference-status-card-id">{selectedId}</span>
      <span className="reference-status-card-pill">{t("inSignoff")}</span>
      <div className="reference-status-card-ring">
        <Check size={18} />
      </div>
      <p>
        {localeText(
          t,
          "Waiting for client approval",
          "Esperando aprobación del cliente",
        )}
      </p>
    </article>
  );
}

function ActivityCard({
  items,
  onOpenTab,
  t,
}: {
  items: ActivityItem[];
  onOpenTab?: (tab: Tab) => void;
  t: Translate;
}) {
  return (
    <article className="reference-card reference-activity-card">
      <div className="reference-card-heading">
        <h2>{t("recentActivity")}</h2>
        <button
          aria-label={t("settings")}
          onClick={() => onOpenTab?.("changes")}
        >
          <MoreHorizontal size={18} />
        </button>
      </div>
      <div className="reference-activity-list">
        {items.map((item) => (
          <div
            className="reference-activity-row"
            key={`${item.author}-${item.time}`}
          >
            <Avatar variant={item.avatar} initials={item.author.slice(0, 2)} />
            <span>
              <strong>{item.author}</strong>
              <small>{item.text}</small>
            </span>
            <time>{item.time}</time>
          </div>
        ))}
      </div>
    </article>
  );
}

function VerificationCard({
  data,
  value,
  onOpenTab,
  t,
}: {
  data: DashboardData["verification_status"];
  value: number;
  onOpenTab?: (tab: Tab) => void;
  t: Translate;
}) {
  const chart = useChartSize();
  const reducedMotion = useReducedMotion();
  const chartData = data.map((item) => ({
    ...item,
    fill:
      item.tone === "success"
        ? "#1DB954"
        : item.tone === "error"
          ? "#FF5A5F"
          : item.tone === "progress"
            ? "#6F82FF"
            : "#B6BFCE",
  }));
  return (
    <article className="reference-card reference-verification-card">
      <div className="reference-card-heading">
        <h2>{t("verificationStatus")}</h2>
        <button
          aria-label={t("settings")}
          onClick={() => onOpenTab?.("verification")}
        >
          <MoreHorizontal size={18} />
        </button>
      </div>
      <div className="reference-verification-body">
        <div ref={chart.setElement} className="reference-donut">
          {chart.width > 0 && chart.height > 0 && (
            <PieChart width={chart.width} height={chart.height}>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                innerRadius="67%"
                outerRadius="100%"
                paddingAngle={3}
                cornerRadius={7}
                stroke="none"
                isAnimationActive={!reducedMotion}
                animationDuration={650}
                animationEasing="ease-out"
              >
                {chartData.map((entry) => (
                  <Cell key={entry.name} fill={entry.fill} />
                ))}
              </Pie>
            </PieChart>
          )}
          <div>
            <strong>{value}%</strong>
            <span>{t("passed")}</span>
          </div>
        </div>
        <div className="reference-legend">
          {chartData.map((item) => (
            <span key={item.name}>
              <i style={{ background: item.fill }} />
              <b>{item.value}</b> {item.name}
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}

function useChartSize() {
  const [node, setNode] = useState<HTMLElement | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const setElement = useCallback((element: HTMLElement | null) => {
    setNode(element);
  }, []);

  useEffect(() => {
    if (!node) return;
    const measure = () => {
      const rect = node.getBoundingClientRect();
      const next = {
        width: Math.max(0, Math.round(rect.width)),
        height: Math.max(0, Math.round(rect.height)),
      };
      setSize((current) =>
        current.width === next.width && current.height === next.height
          ? current
          : next,
      );
    };

    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [node]);

  return { setElement, ...size };
}

function useReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return reducedMotion;
}

function RequirementDrawer({
  requirement,
  selectedId,
  onClose,
  onPrevious,
  onNext,
  onRunVerification,
  onExportEvidence,
  onOpenVerification,
  verificationRunning,
  verificationComplete,
  releaseName,
  notify,
  t,
}: {
  requirement: RequirementDetail;
  selectedId: string;
  onClose: () => void;
  onPrevious: () => void;
  onNext: () => void;
  onRunVerification: () => void;
  onExportEvidence: () => void;
  onOpenVerification: () => void;
  verificationRunning: boolean;
  verificationComplete: boolean;
  releaseName: string;
  notify: (message: string) => void;
  t: Translate;
}) {
  const { locale } = useAppPreferences();
  const [drawerTab, setDrawerTab] = useState<DrawerTab>("details");
  const [relationshipOpen, setRelationshipOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [commentDraft, setCommentDraft] = useState("");
  const [comments, setComments] = useState([
    "John Smith · CSV export needs an audit note.",
  ]);
  const isReferenceDetail = requirement.id === "REQ-041";
  const criteria = isReferenceDetail
    ? requirement.criteria
    : [
        locale === "es"
          ? "El flujo del usuario está disponible y verificado"
          : "User flow is available and verified",
        locale === "es"
          ? "El resultado esperado es visible para el cliente"
          : "Expected output is visible to the client",
        locale === "es"
          ? "La evidencia está vinculada al requisito"
          : "Evidence is linked to the requirement",
        locale === "es"
          ? "El release está listo para aprobación"
          : "Release is ready for sign-off",
      ];
  function addComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = commentDraft.trim();
    if (!value) return;
    setComments((items) => [
      ...items,
      `${locale === "es" ? "Diego Pérez" : "Diego Pérez"} · ${value}`,
    ]);
    setCommentDraft("");
    notify(locale === "es" ? "Comentario añadido" : "Comment added");
  }

  return (
    <aside className="reference-drawer">
      <div className="reference-drawer-header">
        <strong>{requirement.id}</strong>
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
        <div className="reference-drawer-toolbar">
          <button
            className="reference-pill pill-agreed"
            onClick={() =>
              notify(
                locale === "es"
                  ? "Estado del requisito: acordado"
                  : "Requirement status: agreed",
              )
            }
          >
            <span className="status-dot tone-success" />
            {requirement.status === "pending" ? t("pending") : t("agreed")}
            <ChevronDown size={12} />
          </button>
          <button
            aria-label="Relationships"
            onClick={() => setRelationshipOpen((value) => !value)}
          >
            <Link2 size={15} />
          </button>
          <span className="reference-version">
            {isReferenceDetail ? requirement.version : "v1.0"}
          </span>
          <button
            aria-label="More"
            onClick={() => setMoreOpen((value) => !value)}
          >
            <MoreHorizontal size={16} />
          </button>
          {relationshipOpen && (
            <div className="reference-drawer-popover">
              <strong>
                {locale === "es" ? "Relaciones" : "Relationships"}
              </strong>
              <span>{requirement.baseline}</span>
              <span>{requirement.id} · tracked reference</span>
              <span>{releaseName}</span>
            </div>
          )}
          {moreOpen && (
            <div className="reference-drawer-popover reference-drawer-more">
              <button
                onClick={() =>
                  notify(
                    `${requirement.id} ${locale === "es" ? "copiado" : "copied"}`,
                  )
                }
              >
                <Link2 size={14} />
                {locale === "es" ? "Copiar ID" : "Copy requirement ID"}
              </button>
              <button onClick={onExportEvidence}>
                <Download size={14} />
                {locale === "es" ? "Exportar evidencia" : "Export evidence"}
              </button>
            </div>
          )}
        </div>
        <h2>{requirement.title}</h2>
        <p className="reference-drawer-description">
          {requirement.description}
        </p>
        <div className="reference-drawer-tabs">
          <button
            className={drawerTab === "details" ? "is-active" : ""}
            onClick={() => setDrawerTab("details")}
          >
            {t("details")}
          </button>
          <button
            className={drawerTab === "verification" ? "is-active" : ""}
            onClick={() => setDrawerTab("verification")}
          >
            {locale === "es" ? "Verificación" : "Verification"} (
            {isReferenceDetail ? 3 : 1})
          </button>
          <button
            className={drawerTab === "evidence" ? "is-active" : ""}
            onClick={() => setDrawerTab("evidence")}
          >
            {locale === "es" ? "Evidencia" : "Evidence"} (
            {isReferenceDetail ? 4 : 0})
          </button>
          <button
            className={drawerTab === "comments" ? "is-active" : ""}
            onClick={() => setDrawerTab("comments")}
          >
            {locale === "es" ? "Comentarios" : "Comments"} ({comments.length})
          </button>
        </div>
        {drawerTab === "details" && (
          <>
            <div className="reference-detail-list">
              <Detail label={t("type")} value={requirement.type} />
              <Detail
                label={t("priority")}
                value={requirement.priority}
                tone="priority"
              />
              <Detail label={t("component")} value={requirement.component} />
              <Detail
                label={t("baseline")}
                value={requirement.baseline}
                accent
              />
              <Detail label={t("createdLabel")} value={requirement.created} />
              <Detail label={t("agreedLabel")} value={requirement.agreed} />
              <Detail label={t("owner")} value={requirement.owner} owner />
            </div>
            <div className="reference-criteria">
              <h3>{t("acceptanceCriteria")}</h3>
              {criteria.map((criterion) => (
                <div key={criterion}>
                  <CircleCheck size={15} />
                  <span>{criterion}</span>
                </div>
              ))}
            </div>
          </>
        )}
        {drawerTab === "verification" && (
          <VerificationPanel
            requirement={requirement}
            criteria={criteria}
            running={verificationRunning}
            complete={verificationComplete}
            onRun={onRunVerification}
            onOpen={onOpenVerification}
            t={t}
          />
        )}{" "}
        {drawerTab === "evidence" && (
          <EvidencePanel onExport={onExportEvidence} locale={locale} />
        )}{" "}
        {drawerTab === "comments" && (
          <CommentsPanel
            comments={comments}
            draft={commentDraft}
            onDraftChange={setCommentDraft}
            onSubmit={addComment}
            locale={locale}
          />
        )}
        <button className="reference-drawer-cta" onClick={onOpenVerification}>
          <span>{t("viewVerification")}</span>
          <ChevronRight size={18} />
        </button>
      </div>
    </aside>
  );
}

function VerificationPanel({
  requirement,
  criteria,
  running,
  complete,
  onRun,
  onOpen,
  t,
}: {
  requirement: RequirementDetail;
  criteria: string[];
  running: boolean;
  complete: boolean;
  onRun: () => void;
  onOpen: () => void;
  t: Translate;
}) {
  const { locale } = useAppPreferences();
  return (
    <section className="reference-drawer-panel">
      <div className="reference-panel-status">
        <span>{locale === "es" ? "Última ejecución" : "Last run"}</span>
        <strong>
          {complete
            ? locale === "es"
              ? "Ahora"
              : "Just now"
            : requirement.id === "REQ-041"
              ? "2h ago"
              : locale === "es"
                ? "Nunca"
                : "Never"}
        </strong>
      </div>
      <div className="reference-panel-list">
        <div>
          <CircleCheck size={14} />
          <span>
            {locale === "es" ? "Criterios cubiertos" : "Criteria covered"}
          </span>
          <strong>
            {complete ? criteria.length : Math.max(1, criteria.length - 1)}/
            {criteria.length}
          </strong>
        </div>
        <div>
          <Gauge size={14} />
          <span>{locale === "es" ? "Cobertura" : "Coverage"}</span>
          <strong>
            {complete ? "100%" : requirement.id === "REQ-041" ? "100%" : "0%"}
          </strong>
        </div>
      </div>
      {complete && (
        <p className="reference-panel-success">
          <CheckCircle2 size={14} />
          {locale === "es"
            ? "Verificación completada con evidencia actualizada."
            : "Verification completed with refreshed evidence."}
        </p>
      )}
      <div className="reference-drawer-actions">
        <button onClick={onRun} disabled={running}>
          {running ? (
            <RefreshCw size={14} className="reference-spin" />
          ) : (
            <Play size={14} />
          )}
          <span>
            {running
              ? locale === "es"
                ? "Ejecutando…"
                : "Running…"
              : locale === "es"
                ? "Ejecutar verificación"
                : "Run verification"}
          </span>
        </button>
        <button onClick={onOpen}>
          <ExternalLink size={14} />
          {locale === "es" ? "Abrir informe" : "Open report"}
        </button>
      </div>
    </section>
  );
}

function EvidencePanel({
  onExport,
  locale,
}: {
  onExport: () => void;
  locale: Locale;
}) {
  const artifacts =
    locale === "es"
      ? ["Captura de verificación", "Snapshot del DOM", "Log de ejecución"]
      : ["Verification screenshot", "DOM snapshot", "Execution log"];
  return (
    <section className="reference-drawer-panel">
      <div className="reference-panel-status">
        <span>
          {locale === "es" ? "Artefactos vinculados" : "Linked artifacts"}
        </span>
        <strong>3</strong>
      </div>
      <div className="reference-panel-list">
        {artifacts.map((artifact) => (
          <div key={artifact}>
            <FileStack size={14} />
            <span>{artifact}</span>
            <strong>SHA-256</strong>
          </div>
        ))}
      </div>
      <button className="reference-panel-primary" onClick={onExport}>
        <Download size={14} />
        {locale === "es" ? "Descargar índice JSON" : "Download JSON index"}
      </button>
    </section>
  );
}

function CommentsPanel({
  comments,
  draft,
  onDraftChange,
  onSubmit,
  locale,
}: {
  comments: string[];
  draft: string;
  onDraftChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  locale: Locale;
}) {
  return (
    <section className="reference-drawer-panel">
      <div className="reference-panel-status">
        <span>
          {locale === "es" ? "Comentarios abiertos" : "Open comments"}
        </span>
        <strong>{comments.length}</strong>
      </div>
      <div className="reference-comment-list">
        {comments.map((comment) => (
          <div className="reference-comment" key={comment}>
            {comment}
          </div>
        ))}
      </div>
      <form className="reference-comment-form" onSubmit={onSubmit}>
        <textarea
          aria-label={locale === "es" ? "Nuevo comentario" : "New comment"}
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          placeholder={
            locale === "es"
              ? "Añade contexto para el cliente…"
              : "Add context for the client…"
          }
        />
        <button type="submit">
          <MessageCircle size={14} />
          {locale === "es" ? "Añadir comentario" : "Add comment"}
        </button>
      </form>
    </section>
  );
}

function Detail({
  label,
  value,
  accent = false,
  tone = "",
  owner = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
  tone?: string;
  owner?: boolean;
}) {
  return (
    <div>
      <span>{label}</span>
      <strong
        className={`${accent ? "is-accent" : ""} ${tone} ${owner ? "is-owner" : ""}`}
      >
        {owner && <Avatar variant="maria" initials="ML" />}
        {value}
      </strong>
    </div>
  );
}

function Avatar({ variant, initials }: { variant: string; initials: string }) {
  return (
    <span className={`reference-avatar avatar-${variant}`} aria-hidden="true">
      <span>{initials}</span>
    </span>
  );
}

function localeText(t: Translate, english: string, spanish: string) {
  return t("language") === "Idioma" ? spanish : english;
}

function TabView({
  tab,
  data,
  requirements,
  projectId,
  onSelect,
  onRunVerification,
  onExportEvidence,
  onSendForAcceptance,
  onOpenPortal,
  onGenerateCriteria,
  onPrepareDelivery,
  verificationRunning,
  aiRunning,
  releaseSent,
  deliveryChecks,
  notify,
  t,
}: {
  tab: Tab;
  data: DashboardData;
  requirements: RequirementRow[];
  projectId: string;
  onSelect: (id: string) => void;
  onRunVerification: () => void;
  onExportEvidence: () => void;
  onSendForAcceptance: () => void;
  onOpenPortal: () => void;
  onGenerateCriteria: () => void;
  onPrepareDelivery: () => void;
  verificationRunning: boolean;
  aiRunning: boolean;
  releaseSent: boolean;
  deliveryChecks: {
    ready: boolean;
    checks: { key: string; label: string; status: string; detail: string }[];
  } | null;
  notify: (message: string) => void;
  t: Translate;
}) {
  const { locale } = useAppPreferences();
  const [changeBusy, setChangeBusy] = useState("");
  const [inspection, setInspection] = useState<{
    assessment: string;
    row_count?: number;
    columns?: string[];
  } | null>(null);
  const [inspectionBusy, setInspectionBusy] = useState(false);
  const titles: Record<Tab, string> = {
    overview: t("overview"),
    requirements: t("requirements"),
    changes: t("changes"),
    verification: t("verification"),
    evidence: t("evidence"),
    signoff: t("signoff"),
  };
  const changesQuery = useQuery({
    queryKey: ["changes", projectId],
    queryFn: () =>
      getJson<
        {
          id: string;
          title: string;
          proposed: string;
          classification: string;
          status: string;
          impact: string;
        }[]
      >(`${API}/api/v1/projects/${projectId}/changes`),
    enabled: tab === "changes",
  });
  const evidenceQuery = useQuery({
    queryKey: ["evidence", projectId],
    queryFn: () =>
      getJson<
        {
          id: string;
          requirement_id: string;
          state: string;
          summary: string;
          artifact: string;
          sha256: string;
        }[]
      >(`${API}/api/v1/projects/${projectId}/evidence`),
    enabled: tab === "evidence",
  });
  const description =
    tab === "requirements"
      ? locale === "es"
        ? "Revisa los requisitos y genera criterios atómicos antes de verificar."
        : "Review requirements and generate atomic criteria before verification."
      : tab === "changes"
        ? locale === "es"
          ? "Controla el Change Radar y decide qué cambios entran en el release."
          : "Use Change Radar and decide which changes enter the release."
        : tab === "verification"
          ? locale === "es"
            ? "Revisa ejecuciones y evidencia vinculada."
            : "Review verification runs and their linked evidence."
          : tab === "evidence"
            ? locale === "es"
              ? "Traza cada artefacto hasta su requisito e inspecciona archivos exportados."
              : "Trace every artifact to its requirement and inspect exported files."
            : tab === "signoff"
              ? locale === "es"
                ? "Prepara la entrega, envía el pack y registra la decisión del cliente."
                : "Prepare delivery, send the pack and record the client decision."
              : "";

  async function updateChange(
    changeId: string,
    status: "approved" | "rejected",
  ) {
    setChangeBusy(changeId);
    try {
      const response = await fetch(
        `${API}/api/v1/projects/${projectId}/changes/${changeId}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status }),
        },
      );
      if (!response.ok) throw new Error("change update unavailable");
      await changesQuery.refetch();
      notify(locale === "es" ? "Cambio actualizado" : "Change updated");
    } catch {
      notify(
        locale === "es"
          ? "No se pudo actualizar el cambio"
          : "Change could not be updated",
      );
    } finally {
      setChangeBusy("");
    }
  }

  async function inspectFixture() {
    setInspectionBusy(true);
    try {
      const csv = window.btoa("order_id,status\n1001,open\n1002,closed\n");
      const response = await fetch(
        `${API}/api/v1/projects/${projectId}/file-inspections`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: "orders.csv",
            content_base64: csv,
            expected_columns: ["order_id", "status"],
            expected_row_count: 2,
          }),
        },
      );
      if (!response.ok) throw new Error("file inspection unavailable");
      const result = await response.json();
      setInspection(result);
      notify(locale === "es" ? "Archivo inspeccionado" : "File inspected");
    } catch {
      notify(
        locale === "es"
          ? "No se pudo inspeccionar el archivo"
          : "File inspection failed",
      );
    } finally {
      setInspectionBusy(false);
    }
  }

  async function openEvidence(artifact: string) {
    try {
      const response = await fetch(
        `${API}/api/v1/projects/${projectId}/evidence/${encodeURIComponent(artifact)}/signed-url`,
      );
      if (!response.ok) throw new Error("signed link unavailable");
      const result = (await response.json()) as { url: string };
      window.open(
        result.url.startsWith("/") ? `${API}${result.url}` : result.url,
        "_blank",
        "noopener,noreferrer",
      );
    } catch {
      notify(
        locale === "es"
          ? "El enlace de evidencia no está disponible"
          : "Evidence link is unavailable",
      );
    }
  }

  const changes = changesQuery.data || [];
  const evidence = evidenceQuery.data || [];
  return (
    <div className="reference-tab-view">
      <div className="reference-tab-view-heading">
        <div>
          <span>{data.project.release.toUpperCase()}</span>
          <h2>{titles[tab]}</h2>
        </div>
        <span className="reference-pill pill-agreed">
          {releaseSent
            ? locale === "es"
              ? "Enviado a aprobación"
              : "Sent for acceptance"
            : t("inSignoff")}
        </span>
      </div>
      <div className="reference-tab-actions">
        {tab === "requirements" && (
          <button
            className="is-success"
            onClick={onGenerateCriteria}
            disabled={aiRunning}
          >
            {aiRunning ? (
              <RefreshCw size={14} className="reference-spin" />
            ) : (
              <Sparkles size={14} />
            )}
            {aiRunning
              ? locale === "es"
                ? "Generando…"
                : "Generating…"
              : locale === "es"
                ? "Generar criterios con IA"
                : "Generate criteria with AI"}
          </button>
        )}
        {tab === "changes" && (
          <button onClick={() => changesQuery.refetch()}>
            <RefreshCw size={14} />
            {locale === "es"
              ? "Actualizar Change Radar"
              : "Refresh Change Radar"}
          </button>
        )}
        {tab === "verification" && (
          <button
            className="is-success"
            onClick={onRunVerification}
            disabled={verificationRunning}
          >
            {verificationRunning ? (
              <RefreshCw size={14} className="reference-spin" />
            ) : (
              <Play size={14} />
            )}
            {verificationRunning
              ? locale === "es"
                ? "Ejecutando…"
                : "Running…"
              : locale === "es"
                ? "Ejecutar verificación"
                : "Run verification"}
          </button>
        )}
        {tab === "evidence" && (
          <>
            <button onClick={inspectFixture} disabled={inspectionBusy}>
              {inspectionBusy ? (
                <RefreshCw size={14} className="reference-spin" />
              ) : (
                <FileStack size={14} />
              )}
              {inspectionBusy
                ? locale === "es"
                  ? "Inspeccionando…"
                  : "Inspecting…"
                : locale === "es"
                  ? "Inspeccionar CSV"
                  : "Inspect CSV"}
            </button>
            <button onClick={onExportEvidence}>
              <Download size={14} />
              {locale === "es" ? "Descargar índice" : "Download evidence index"}
            </button>
          </>
        )}
        {tab === "signoff" && (
          <>
            <button onClick={onPrepareDelivery}>
              <PanelsTopLeft size={14} />
              {locale === "es" ? "Preparar entrega" : "Prepare delivery"}
            </button>
            <button className="is-success" onClick={onSendForAcceptance}>
              <Send size={14} />
              {locale === "es" ? "Enviar a aprobación" : "Send for acceptance"}
            </button>
            <button onClick={onOpenPortal}>
              <ExternalLink size={14} />
              {locale === "es" ? "Abrir portal cliente" : "Open client portal"}
            </button>
          </>
        )}
      </div>
      <div className="reference-tab-view-grid">
        <article className="reference-card">
          <h2>{titles[tab]}</h2>
          <p>{description}</p>
          {tab === "changes" ? (
            changes.map((change) => (
              <div
                className="reference-tab-row reference-tab-row-static"
                key={change.id}
              >
                <strong>{change.title}</strong>
                <span>{change.proposed}</span>
                <span
                  className={`reference-pill ${change.status === "approved" ? "pill-agreed" : change.status === "rejected" ? "pill-rejected" : "pill-pending"}`}
                >
                  {change.status}
                </span>
                {change.status === "proposed" ? (
                  <span className="reference-row-actions">
                    <button
                      disabled={changeBusy === change.id}
                      onClick={() => updateChange(change.id, "approved")}
                      aria-label={
                        locale === "es"
                          ? `Aprobar ${change.title}`
                          : `Approve ${change.title}`
                      }
                    >
                      <Check size={14} />
                    </button>
                    <button
                      disabled={changeBusy === change.id}
                      onClick={() => updateChange(change.id, "rejected")}
                      aria-label={
                        locale === "es"
                          ? `Rechazar ${change.title}`
                          : `Reject ${change.title}`
                      }
                    >
                      <X size={14} />
                    </button>
                  </span>
                ) : (
                  <ChevronRight size={15} />
                )}
              </div>
            ))
          ) : tab === "evidence" ? (
            <>
              {evidence.map((item) => (
                <div
                  className="reference-tab-row reference-tab-row-static"
                  key={item.id}
                >
                  <strong>{item.artifact}</strong>
                  <span>{item.summary}</span>
                  <span className="reference-pill pill-agreed">
                    {item.state}
                  </span>
                  <button
                    onClick={() => openEvidence(item.artifact)}
                    aria-label={
                      locale === "es"
                        ? `Abrir ${item.artifact}`
                        : `Open ${item.artifact}`
                    }
                  >
                    <ExternalLink size={15} />
                  </button>
                </div>
              ))}
              {inspection && (
                <div className="reference-inspection-result">
                  <CheckCircle2 size={15} />
                  <span>
                    {locale === "es" ? "Inspección" : "Inspection"}:{" "}
                    {inspection.assessment} · {inspection.row_count} rows ·{" "}
                    {(inspection.columns || []).join(", ")}
                  </span>
                </div>
              )}
            </>
          ) : (
            requirements.map((item) => (
              <button
                className="reference-tab-row"
                key={item.id}
                onClick={() => onSelect(item.id)}
              >
                <strong>{item.id}</strong>
                <span>{item.title}</span>
                <span
                  className={`reference-pill ${item.status === "agreed" ? "pill-agreed" : "pill-pending"}`}
                >
                  {item.status === "agreed" ? t("agreed") : t("pending")}
                </span>
                <ChevronRight size={15} />
              </button>
            ))
          )}
        </article>
        <article className="reference-card reference-tab-side">
          <span className="reference-tab-side-number">
            {tab === "verification"
              ? `${data.metrics.verification.value}%`
              : tab === "evidence"
                ? evidence.length
                : tab === "changes"
                  ? changes.length
                  : data.metrics.requirements.value}
          </span>
          <strong>{titles[tab]}</strong>
          <small>{data.project.release}</small>
          {tab === "signoff" && deliveryChecks && (
            <div className="reference-delivery-checks">
              <span
                className={`reference-pill ${deliveryChecks.ready ? "pill-agreed" : "pill-pending"}`}
              >
                {deliveryChecks.ready
                  ? locale === "es"
                    ? "Listo"
                    : "Ready"
                  : locale === "es"
                    ? "Atención"
                    : "Needs attention"}
              </span>
              {deliveryChecks.checks.map((check) => (
                <small key={check.key}>
                  {check.status === "ready" ? (
                    <Check size={12} />
                  ) : (
                    <CircleAlert size={12} />
                  )}{" "}
                  {check.label}
                </small>
              ))}
            </div>
          )}
        </article>
      </div>
    </div>
  );
}
