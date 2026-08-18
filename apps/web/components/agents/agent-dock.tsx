"use client";

import { useEffect, useMemo, useState } from "react";
import { Bot, Check, ChevronRight, LoaderCircle, ShieldCheck, Sparkles, Wrench, X } from "lucide-react";

type Agent = { id: string; name: string; description: string; tools: string[]; accent: string };
type AgentRun = {
  id?: string;
  status: string;
  result: Record<string, unknown>;
  tool_calls: { tool: string; status: string }[];
  proposal_id?: string;
  requires_approval?: boolean;
  current_step?: number;
  max_steps?: number;
  checkpoint_ids?: string[];
};

export function AgentDock({ api, projectId, requirementId, locale }: { api: string; projectId: string; requirementId: string; locale: "en" | "es" }) {
  const [open, setOpen] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState("delivery-analyst");
  const [question, setQuestion] = useState("");
  const [consent, setConsent] = useState(false);
  const [running, setRunning] = useState(false);
  const [dispatching, setDispatching] = useState(false);
  const [approving, setApproving] = useState(false);
  const [run, setRun] = useState<AgentRun | null>(null);
  const [recentRuns, setRecentRuns] = useState<AgentRun[]>([]);
  const [error, setError] = useState("");
  const isEs = locale === "es";

  useEffect(() => {
    if (!open || agents.length) return;
    fetch(`${api}/api/v1/agents`)
      .then(async (response) => {
        if (!response.ok) throw new Error("agents unavailable");
        const payload = (await response.json()) as { items: Agent[] };
        setAgents(payload.items);
      })
      .catch(() => setError(isEs ? "No se pudieron cargar los agentes." : "Agents could not be loaded."));
  }, [api, agents.length, isEs, open]);

  useEffect(() => {
    if (!open) return;
    fetch(`${api}/api/v1/projects/${projectId}/agents/runs`)
      .then(async (response) => {
        if (!response.ok) return;
        const payload = (await response.json()) as { items: AgentRun[] };
        setRecentRuns(payload.items.slice(0, 3));
      })
      .catch(() => undefined);
  }, [api, open, projectId, run]);

  const selected = useMemo(() => agents.find((item) => item.id === agentId), [agentId, agents]);

  async function execute() {
    setRunning(true);
    setError("");
    setRun(null);
    try {
      const response = await fetch(`${api}/api/v1/projects/${projectId}/agents/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agentId, input: question || (isEs ? "Revisa el contexto activo." : "Review the active delivery context."), requirement_id: requirementId, classification: "CONFIDENTIAL", consent }),
      });
      const payload = (await response.json()) as AgentRun & { detail?: string };
      if (!response.ok) throw new Error(payload.detail || "agent run failed");
      setRun(payload);
      setRecentRuns((items) => [payload, ...items.filter((item) => item.id !== payload.id)].slice(0, 3));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : (isEs ? "La ejecución falló." : "The run failed."));
    } finally {
      setRunning(false);
    }
  }

  async function askSignoff() {
    setDispatching(true);
    setError("");
    setRun(null);
    try {
      const response = await fetch(`${api}/api/v1/projects/${projectId}/agents/dispatch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: question || (isEs ? "Comprueba el estado del proyecto y sus funcionalidades." : "Check the project status and its functionality."), requirement_id: requirementId, classification: "CONFIDENTIAL", consent, target_url: typeof window !== "undefined" ? window.location.origin + "/dashboard" : "http://localhost:3000/dashboard" }),
      });
      const payload = (await response.json()) as AgentRun & { detail?: string };
      if (!response.ok) throw new Error(payload.detail || "dispatch failed");
      setRun(payload);
      setRecentRuns((items) => [payload, ...items.filter((item) => item.id !== payload.id)].slice(0, 3));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : (isEs ? "La consulta falló." : "The request failed."));
    } finally {
      setDispatching(false);
    }
  }

  async function approve() {
    if (!run?.proposal_id) return;
    setApproving(true);
    try {
      const response = await fetch(`${api}/api/v1/ai/proposals/${run.proposal_id}/approve`, { method: "POST" });
      if (!response.ok) throw new Error("approval failed");
      setRun({ ...run, status: "completed", requires_approval: false });
    } catch {
      setError(isEs ? "No se pudo aprobar la propuesta." : "The proposal could not be approved.");
    } finally {
      setApproving(false);
    }
  }

  return (
    <div className="reference-agent-dock">
      <button className="reference-agent-trigger" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <Sparkles size={15} />
        {isEs ? "Agentes Signoff" : "Signoff agents"}
      </button>
      {open && (
        <section className="reference-agent-panel" aria-label={isEs ? "Agentes de Signoff" : "Signoff agents"}>
          <header className="reference-agent-panel-header">
            <div>
              <span className="reference-context-kicker">SIGNOFF INTELLIGENCE</span>
              <h2>{isEs ? "Agentes para este release" : "Agents for this release"}</h2>
            </div>
            <button className="reference-agent-close" onClick={() => setOpen(false)} aria-label={isEs ? "Cerrar agentes" : "Close agents"}><X size={16} /></button>
          </header>
          <div className="reference-agent-safety"><ShieldCheck size={15} /><span>{isEs ? "Las acciones de escritura siempre requieren aprobación." : "Write actions always require approval."}</span></div>
          <div className="reference-agent-list">
            {agents.map((agent) => (
              <button key={agent.id} className={`reference-agent-option${agent.id === agentId ? " is-selected" : ""}`} onClick={() => { setAgentId(agent.id); setRun(null); }}>
                <span className={`reference-agent-icon agent-${agent.accent}`}><Bot size={16} /></span>
                <span><strong>{isEs ? translateAgentName(agent.id) : agent.name}</strong><small>{isEs ? translateAgentDescription(agent.id) : agent.description}</small></span>
                <ChevronRight size={15} />
              </button>
            ))}
          </div>
          <label className="reference-agent-question">
            <span>{isEs ? "Qué necesitas revisar" : "What should it review"}</span>
            <textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder={isEs ? "Ej. ¿Qué bloquea la aprobación?" : "e.g. What is blocking approval?"} rows={2} />
          </label>
          <label className="reference-agent-consent"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /><span>{isEs ? "Permitir procesamiento externo si el modo real está activo" : "Allow external processing if real AI mode is active"}</span></label>
          <div className="reference-agent-actions">
            <button className="reference-agent-run" onClick={execute} disabled={running || dispatching || !selected}><Wrench size={15} />{running ? (isEs ? "Ejecutando..." : "Running...") : (isEs ? "Ejecutar agente" : "Run agent")}{running ? <LoaderCircle className="reference-agent-spinner" size={15} /> : <ChevronRight size={15} />}</button>
            <button className="reference-agent-ask" onClick={askSignoff} disabled={running || dispatching}>{dispatching ? <LoaderCircle className="reference-agent-spinner" size={15} /> : <Sparkles size={15} />}{isEs ? "Preguntar a Signoff" : "Ask Signoff"}</button>
          </div>
          {error && <p className="reference-agent-error">{error}</p>}
          {run && (
            <div className="reference-agent-result">
              <div className="reference-agent-result-heading"><Check size={14} />{run.requires_approval ? (isEs ? "Propuesta pendiente" : "Proposal pending") : (isEs ? "Ejecución completada" : "Run completed")}</div>
              <div className="reference-agent-meta">{run.id ? `Run ${run.id}` : ""}{run.checkpoint_ids?.length ? ` · ${run.checkpoint_ids.length} ${isEs ? "checkpoints" : "checkpoints"}` : ""}</div>
              <div className="reference-agent-tools">{run.tool_calls.map((call) => <span key={call.tool}><Check size={12} />{call.tool.replaceAll("_", " ")}</span>)}</div>
              {run.proposal_id && <button className="reference-agent-approve" onClick={approve} disabled={approving}>{approving ? (isEs ? "Aprobando..." : "Approving...") : (isEs ? "Aprobar propuesta" : "Approve proposal")}</button>}
              <pre>{JSON.stringify(run.result, null, 2)}</pre>
            </div>
          )}
          {!run && recentRuns.length > 0 && <div className="reference-agent-history"><span className="reference-context-kicker">{isEs ? "ÚLTIMAS EJECUCIONES" : "RECENT RUNS"}</span>{recentRuns.map((item) => <div key={item.id} className="reference-agent-history-row"><span>{item.id}</span><small>{item.status}</small></div>)}</div>}
        </section>
      )}
    </div>
  );
}

function translateAgentName(id: string) {
  return { "delivery-analyst": "Analista de entrega", "requirements-coach": "Coach de requisitos", "verification-planner": "Planificador de verificación", "change-radar": "Radar de cambios", "agreement-analyst": "Analista de acuerdos", "qa-explorer": "Explorador QA", "evidence-curator": "Curador de evidencias", "acceptance-assistant": "Asistente de aceptación" }[id] || id;
}

function translateAgentDescription(id: string) {
  return { "delivery-analyst": "Explica qué bloquea el release y cuál es la siguiente decisión.", "requirements-coach": "Propone criterios de aceptación atómicos y verificables.", "verification-planner": "Convierte un requisito en un plan de verificación acotado.", "change-radar": "Explica qué señales de cambio necesitan revisión humana.", "agreement-analyst": "Encuentra compromisos, ambigüedades y criterios faltantes.", "qa-explorer": "Comprueba la aplicación levantada y captura observaciones.", "evidence-curator": "Encuentra evidencias débiles, obsoletas o ausentes.", "acceptance-assistant": "Prepara un resumen para el cliente sin decidir por él." }[id] || "";
}
