"""Read models derived from project facts.

Every function here is pure: it receives a ``ProjectState`` (plus the global
agent proposals or audit events when needed) and a locale, and returns plain
JSON-ready data. No number shown by the product is stored; it is computed here.
"""
from __future__ import annotations

from typing import Any

from .domain import calculate_readiness
from .seed import ProjectState

VERIFICATION_ORDER = ("passed", "failed", "in_progress", "not_started")
VERIFICATION_TONE = {"passed": "success", "failed": "error", "in_progress": "progress", "not_started": "neutral"}
SCOPE_TONE = {"agreed": "success", "pending": "warning", "out_of_scope": "neutral"}
CHANGE_TONE = {"approved": "success", "proposed": "warning", "rejected": "error"}
EVIDENCE_STATUS = {"passed": "demonstrated", "in_progress": "partially_demonstrated", "failed": "not_demonstrated", "not_started": "not_demonstrated"}
PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}
COMPONENT_ES = {
    "Users": "Usuarios", "Billing": "Facturación", "Exports": "Exportaciones", "Notifications": "Notificaciones", "Security": "Seguridad", "Reporting": "Informes",
    "Authentication": "Autenticación", "Core workflow": "Flujo principal", "Compliance": "Cumplimiento", "Non-functional": "No funcional", "Support": "Soporte",
}


def normalize_locale(locale: str | None) -> str:
    return "es" if (locale or "").lower().startswith("es") else "en"


def loc(value: Any, locale: str) -> Any:
    """Resolve bilingual ``{"en", "es"}`` values recursively."""
    if isinstance(value, dict):
        if set(value.keys()) == {"en", "es"}:
            return value.get(locale) or value.get("en")
        return {key: loc(item, locale) for key, item in value.items()}
    if isinstance(value, list):
        return [loc(item, locale) for item in value]
    return value


def T(locale: str, en: str, es: str, **params: Any) -> str:
    return (es if locale == "es" else en).format(**params)


def component_name(component: str, locale: str) -> str:
    """Components are stored by their English name; Spanish is a display translation."""
    return COMPONENT_ES.get(component, component) if locale == "es" else component


def plural(locale: str, n: int, en_one: str, en_many: str, es_one: str, es_many: str) -> str:
    """Pick the singular or plural template for ``n`` in the active locale."""
    if locale == "es":
        return (es_one if n == 1 else es_many).format(n=n)
    return (en_one if n == 1 else en_many).format(n=n)


def pct(part: int, total: int) -> int:
    return round(part * 100 / total) if total else 0


# --- Actors --------------------------------------------------------------

AGENT_NAMES = {
    "delivery-analyst": ("Delivery analyst", "Analista de entrega"),
    "requirements-coach": ("Requirements coach", "Coach de requisitos"),
    "verification-planner": ("Verification planner", "Planificador de verificación"),
    "change-radar": ("Change radar", "Radar de cambios"),
    "agreement-analyst": ("Agreement analyst", "Analista del acuerdo"),
    "qa-explorer": ("QA explorer", "Explorador QA"),
    "evidence-curator": ("Evidence curator", "Curador de evidencias"),
    "acceptance-assistant": ("Acceptance assistant", "Asistente de aceptación"),
}


def agent_ref(agent_id: str, locale: str = "en") -> dict[str, str]:
    en, es = AGENT_NAMES.get(agent_id, (agent_id, agent_id))
    return {"id": agent_id, "name": es if locale == "es" else en}


def actor(state: ProjectState, actor_id: str | None, locale: str = "en") -> dict[str, Any]:
    if actor_id and actor_id.startswith("agent:"):
        agent = agent_ref(actor_id.split(":", 1)[1], locale)
        return {"id": actor_id, "name": agent["name"], "initials": "AI", "kind": "agent", "role": "agent"}
    member = state.member(actor_id or "")
    if member:
        return {key: member[key] for key in ("id", "name", "initials", "kind", "role")}
    return {"id": "system", "name": T(locale, "System", "Sistema"), "initials": "SY", "kind": "system", "role": "system"}


def team(state: ProjectState) -> list[dict[str, Any]]:
    return [dict(item) for item in state.members]


# --- Counting helpers ------------------------------------------------------

def in_scope(state: ProjectState) -> list[dict[str, Any]]:
    return [item for item in state.requirements if item["scope_status"] != "out_of_scope"]


def evidence_for(state: ProjectState, requirement_id: str) -> list[dict[str, Any]]:
    return [item for item in state.evidence if item["requirement_id"] == requirement_id]


def open_comments(state: ProjectState, requirement_id: str | None = None) -> list[dict[str, Any]]:
    return [item for item in state.comments if not item["resolved"] and (requirement_id is None or item["requirement_id"] == requirement_id)]


def runs_for(state: ProjectState, requirement_id: str) -> list[dict[str, Any]]:
    items = []
    for run in state.runs:
        for result in run["results"]:
            if result["requirement_id"] == requirement_id:
                items.append({"id": run["id"], "at": run["at"], **result})
    return sorted(items, key=lambda item: item["at"], reverse=True)


def requirement_coverage(state: ProjectState, requirement: dict[str, Any]) -> int:
    runs = runs_for(state, requirement["id"])
    if not runs:
        return 0
    latest = runs[0]
    return pct(latest["criteria_covered"], latest["criteria_total"]) if latest["criteria_total"] else 0


def verification_counts(state: ProjectState) -> dict[str, int]:
    scoped = in_scope(state)
    return {key: sum(item["verification"] == key for item in scoped) for key in VERIFICATION_ORDER}


def coverage_value(state: ProjectState) -> int:
    scoped = in_scope(state)
    covered = {item["requirement_id"] for item in state.evidence}
    return pct(sum(item["id"] in covered for item in scoped), len(scoped))


def coverage_trend(state: ProjectState) -> list[dict[str, Any]]:
    """Coverage after each run, replayed from evidence timestamps."""
    scoped_ids = {item["id"] for item in in_scope(state)}
    points = []
    for index, run in enumerate(sorted(state.runs, key=lambda item: item["at"]), 1):
        covered = {item["requirement_id"] for item in state.evidence if item["created_at"] <= run["at"]} & scoped_ids
        points.append({"run": index, "value": pct(len(covered), len(scoped_ids)), "at": run["at"]})
    return points


def change_counts(state: ProjectState) -> dict[str, int]:
    return {key: sum(item["status"] == key for item in state.changes) for key in ("approved", "proposed", "rejected")}


def pending_proposals(state: ProjectState, proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in proposals if item["project_id"] == state.id and item["status"] == "draft"]


# --- Requirements -----------------------------------------------------------

def requirement_row(state: ProjectState, requirement: dict[str, Any], locale: str) -> dict[str, Any]:
    criteria = requirement["criteria"]
    return {
        "id": requirement["id"],
        "uuid": requirement["uuid"],
        "title": loc(requirement["title"], locale),
        "component": component_name(requirement["component"], locale),
        "component_key": requirement["component"],
        "priority": requirement["priority"],
        "owner": actor(state, requirement["owner_id"], locale),
        "scope_status": requirement["scope_status"],
        "verification": requirement["verification"],
        "coverage": requirement_coverage(state, requirement),
        "criteria_count": len(criteria),
        "evidence_count": len(evidence_for(state, requirement["id"])),
        "open_comments": len(open_comments(state, requirement["id"])),
        "acceptance": requirement["acceptance"],
        # Legacy fields kept for existing clients.
        "human_id": requirement["id"],
        "status": EVIDENCE_STATUS[requirement["verification"]],
        "description": loc(requirement["description"], locale),
        "category": component_name(requirement["component"], locale),
        "criteria": [{"id": item["id"], "text": loc(item["text"], locale), "source": item["source"], "type": "semantic", "automated": True} for item in criteria],
    }


def requirement_rows(state: ProjectState, locale: str) -> list[dict[str, Any]]:
    return [requirement_row(state, item, locale) for item in sorted(state.requirements, key=lambda item: item["id"])]


def evidence_view(item: dict[str, Any], locale: str) -> dict[str, Any]:
    return {key: loc(value, locale) for key, value in item.items() if key != "storage_key"}


def comment_view(state: ProjectState, item: dict[str, Any], locale: str) -> dict[str, Any]:
    return {"id": item["id"], "requirement_id": item["requirement_id"], "author": actor(state, item["author_id"], locale), "text": loc(item["text"], locale), "created_at": item["created_at"], "resolved": item["resolved"], "resolved_at": item.get("resolved_at")}


def change_view(state: ProjectState, item: dict[str, Any], locale: str) -> dict[str, Any]:
    return {
        "id": item["id"], "code": item["code"], "title": loc(item["title"], locale), "original": loc(item["original"], locale), "proposed": loc(item["proposed"], locale),
        "classification": item["classification"], "status": item["status"], "impact": item["impact"], "requirement_ids": list(item["requirement_ids"]),
        "source": item["source"], "created_at": item["created_at"], "decided_by": actor(state, item["decided_by"], locale) if item.get("decided_by") else None,
        "decided_at": item.get("decided_at"),
    }


def requirement_detail(state: ProjectState, requirement: dict[str, Any], locale: str) -> dict[str, Any]:
    row = requirement_row(state, requirement, locale)
    runs = runs_for(state, requirement["id"])
    evidence = sorted(evidence_for(state, requirement["id"]), key=lambda item: item["created_at"], reverse=True)
    plan = requirement.get("verification_plan")
    return {
        **row,
        "type": requirement["type"],
        "baseline": requirement["baseline"],
        "version": requirement["version"],
        "created_at": requirement["created_at"],
        "agreed_at": requirement["agreed_at"],
        "verification_plan": loc(plan, locale) if plan else None,
        "runs": [{"id": item["id"], "at": item["at"], "result": item["result"], "criteria_covered": item["criteria_covered"], "criteria_total": item["criteria_total"], "coverage": pct(item["criteria_covered"], item["criteria_total"]), "evidence_ids": item["evidence_ids"]} for item in runs],
        "evidence": [evidence_view(item, locale) for item in evidence],
        "comments": [comment_view(state, item, locale) for item in sorted(state.comments, key=lambda item: item["created_at"]) if item["requirement_id"] == requirement["id"]],
        "changes": [{"id": item["id"], "code": item["code"], "title": loc(item["title"], locale), "status": item["status"]} for item in state.changes if requirement["id"] in item["requirement_ids"]],
    }


def attention_rank(requirement: dict[str, Any]) -> tuple:
    if requirement["scope_status"] == "out_of_scope":
        bucket = 4
    elif requirement["verification"] == "failed":
        bucket = 0
    elif requirement["verification"] in {"in_progress", "not_started"} and requirement["priority"] == "high":
        bucket = 1
    elif requirement["scope_status"] == "pending":
        bucket = 2
    elif requirement["verification"] in {"in_progress", "not_started"}:
        bucket = 3
    else:
        bucket = 5
    return (bucket, PRIORITY_RANK[requirement["priority"]], requirement["id"])


# --- Readiness, attention, activity -------------------------------------------

def readiness(state: ProjectState) -> dict[str, Any]:
    result = calculate_readiness(
        [{"id": item["id"], "status": EVIDENCE_STATUS[item["verification"]]} for item in state.requirements],
        [{"requirement_id": item["requirement_id"]} for item in state.evidence],
        [{"status": item["status"]} for item in state.changes],
        unresolved_comments=len(open_comments(state)),
        accepted=sum(item["acceptance"] == "accepted" for item in state.requirements),
    )
    return {"release": state.release["name"], **result.model_dump()}


def attention(state: ProjectState, proposals: list[dict[str, Any]], locale: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    scoped = in_scope(state)
    failed = sorted((item for item in scoped if item["verification"] == "failed"), key=lambda item: item["id"])
    proposed = [item for item in state.changes if item["status"] == "proposed"]
    comments = sorted(open_comments(state), key=lambda item: item["created_at"], reverse=True)
    drafts = pending_proposals(state, proposals)
    covered = {item["requirement_id"] for item in state.evidence}
    missing = sorted((item for item in scoped if item["id"] not in covered), key=attention_rank)
    status = state.release["status"]
    if status in {"rejected", "revision_requested"}:
        decision = state.decisions[-1] if state.decisions else {}
        title = T(locale, "The client rejected the release", "El cliente rechazó la release") if status == "rejected" else T(locale, "The client requested a revision", "El cliente pidió una revisión")
        items.append({"id": "client_decision", "severity": "critical", "title": title, "source": T(locale, "Client portal", "Portal del cliente"), "count": 1, "detail": decision.get("comment", ""), "target": {"tab": "signoff"}})
    if failed:
        items.append({"id": "failed_verifications", "severity": "critical", "title": T(locale, "{n} verification results failed", "{n} verificaciones fallidas", n=len(failed)) if len(failed) != 1 else T(locale, "{id} failed verification", "{id} no superó la verificación", id=failed[0]["id"]), "source": T(locale, "Verification", "Verificación"), "count": len(failed), "target": {"tab": "verification", "requirement_id": failed[0]["id"]}})
    if proposed:
        items.append({"id": "proposed_changes", "severity": "warning", "title": T(locale, "{n} changes are pending decision", "{n} cambios pendientes de decisión", n=len(proposed)) if len(proposed) != 1 else T(locale, "{code} is pending decision", "{code} está pendiente de decisión", code=proposed[0]["code"]), "source": T(locale, "Change radar", "Radar de cambios"), "count": len(proposed), "target": {"tab": "changes"}})
    if comments:
        items.append({"id": "open_comments", "severity": "warning", "title": T(locale, "{n} unresolved comments", "{n} comentarios sin resolver", n=len(comments)) if len(comments) != 1 else T(locale, "1 unresolved comment on {id}", "1 comentario sin resolver en {id}", id=comments[0]["requirement_id"]), "source": T(locale, "Comments", "Comentarios"), "count": len(comments), "target": {"tab": "requirements", "requirement_id": comments[0]["requirement_id"]}})
    if drafts:
        items.append({"id": "pending_proposals", "severity": "info", "title": plural(locale, len(drafts), "{n} agent proposal awaits review", "{n} agent proposals await review", "{n} propuesta de agente pendiente de revisión", "{n} propuestas de agentes pendientes de revisión"), "source": T(locale, "Agents", "Agentes"), "count": len(drafts), "target": {"tab": "agents"}})
    if missing:
        items.append({"id": "missing_evidence", "severity": "warning", "title": plural(locale, len(missing), "{n} requirement has no evidence", "{n} requirements have no evidence", "{n} requisito sin evidencia", "{n} requisitos sin evidencia"), "source": T(locale, "Evidence", "Evidencias"), "count": len(missing), "target": {"tab": "evidence", "requirement_id": missing[0]["id"]}})
    if status == "ready":
        items.append({"id": "client_decision", "severity": "info", "title": T(locale, "Waiting for the client decision", "Esperando la decisión del cliente"), "source": T(locale, "Client portal", "Portal del cliente"), "count": 1, "target": {"tab": "signoff"}})
    if status == "accepted":
        items.append({"id": "client_decision", "severity": "info", "title": T(locale, "The client accepted the release", "El cliente aceptó la release"), "source": T(locale, "Client portal", "Portal del cliente"), "count": 1, "target": {"tab": "signoff"}})
    return items


RELEASE_STATUS_TEXT = {
    "in_signoff": ("in sign-off", "en validación"),
    "ready": ("ready for acceptance", "lista para aceptación"),
    "on_hold": ("on hold", "en pausa"),
    "accepted": ("accepted", "aceptada"),
    "revision_requested": ("revision requested", "revisión solicitada"),
    "rejected": ("rejected", "rechazada"),
}
DECISION_TEXT = {
    "accepted": ("accepted the release", "aceptó la release"),
    "revision_requested": ("requested a revision of the release", "solicitó una revisión de la release"),
    "rejected": ("rejected the release", "rechazó la release"),
}
ACTIVITY_TEXT: dict[str, tuple[str, str]] = {
    "change_proposed": ("proposed change {code}", "propuso el cambio {code}"),
    "change_approved": ("approved change {code}", "aprobó el cambio {code}"),
    "change_rejected": ("rejected change {code}", "rechazó el cambio {code}"),
    "comment_added": ("commented on {requirement_id}", "comentó en {requirement_id}"),
    "comment_resolved": ("resolved a comment on {requirement_id}", "resolvió un comentario en {requirement_id}"),
    "evidence_uploaded": ("uploaded {artifact} for {requirement_id}", "subió {artifact} para {requirement_id}"),
    "scope_draft_created": ("extracted draft baseline {version}", "extrajo el borrador de línea base {version}"),
    "scope_approved": ("approved baseline {version}", "aprobó la línea base {version}"),
    "requirement_updated": ("updated {requirement_id}", "actualizó {requirement_id}"),
    "criteria_generated": ("generated acceptance criteria for {requirement_id}", "generó criterios de aceptación para {requirement_id}"),
    "acceptance_decided": ("recorded {decision} for {requirement_id}", "registró {decision} para {requirement_id}"),
    "release_sent_for_acceptance": ("sent the release for client acceptance", "envió la release a aceptación del cliente"),
    "proposal_created": ("prepared a proposal: {title}", "preparó una propuesta: {title}"),
    "proposal_approved": ("approved the proposal: {title}", "aprobó la propuesta: {title}"),
    "proposal_rejected": ("rejected the proposal: {title}", "rechazó la propuesta: {title}"),
    "agent_run_failed": ("could not finish the run: {error}", "no pudo terminar la ejecución: {error}"),
}


def activity_text(event: dict[str, Any], locale: str) -> str | None:
    params = loc(event.get("params") or {}, locale)
    name = event["event"]
    index = 1 if locale == "es" else 0
    if name == "release_status_updated":
        status = RELEASE_STATUS_TEXT.get(params.get("status", ""), (params.get("status", ""),) * 2)[index]
        return T(locale, "set the release status to {s}", "cambió el estado de la release a {s}", s=status)
    if name == "verification_run":
        count, passed, failed = int(params.get("count", 0)), int(params.get("passed", 0)), int(params.get("failed", 0))
        return plural(locale, count, "ran verification on {n} requirement", "ran verification on {n} requirements", "verificó {n} requisito", "verificó {n} requisitos") + ": " + plural(locale, passed, "{n} passed", "{n} passed", "{n} superado", "{n} superados") + ", " + plural(locale, failed, "{n} failed", "{n} failed", "{n} fallido", "{n} fallidos")
    if name == "client_release_reviewed":
        return DECISION_TEXT.get(params.get("decision", ""), ("reviewed the release", "revisó la release"))[index]
    template = ACTIVITY_TEXT.get(name)
    if not template:
        return None
    try:
        return template[index].format(**params)
    except (KeyError, IndexError):
        return None


def activity(state: ProjectState, events: list[dict[str, Any]], locale: str, limit: int = 20) -> list[dict[str, Any]]:
    items = []
    for index, event in enumerate(events):
        if event.get("project_id") != state.id:
            continue
        text = activity_text(event, locale)
        if not text:
            continue
        items.append({"id": event.get("id") or f"event_{index}", "actor": actor(state, event.get("actor_id"), locale), "text": text, "at": event["created_at"], "ref": event.get("ref")})
    items.sort(key=lambda item: item["at"], reverse=True)
    return items[:limit]


# --- Dashboard, releases, projects ------------------------------------------

def project_header(state: ProjectState) -> dict[str, Any]:
    release = state.release
    return {"id": state.id, "name": state.project["name"], "client": state.project["client"], "release": release["name"], "version": release["version"], "status": release["status"], "created_at": release["created_at"], "target_date": release["target_date"]}


def active_baseline(state: ProjectState) -> str:
    approved = [item for item in state.scope_versions if item["status"] == "approved"]
    return approved[-1]["version"] if approved else ""


def dashboard(state: ProjectState, proposals: list[dict[str, Any]], events: list[dict[str, Any]], locale: str) -> dict[str, Any]:
    scoped = in_scope(state)
    counts = verification_counts(state)
    scope_counts = {key: sum(item["scope_status"] == key for item in state.requirements) for key in ("agreed", "pending", "out_of_scope")}
    changes = change_counts(state)
    trend = coverage_trend(state)
    delta = trend[-1]["value"] - trend[-2]["value"] if len(trend) > 1 else 0
    ranked = sorted(state.requirements, key=attention_rank)[:5]
    rows = [requirement_row(state, item, locale) for item in ranked]
    attention_items = attention(state, proposals, locale)
    return {
        "project": project_header(state),
        "metrics": {
            "requirements": {"value": len(state.requirements), "items": [{"key": key, "label": key, "value": value, "tone": SCOPE_TONE[key]} for key, value in scope_counts.items()]},
            "verification": {"value": pct(counts["passed"], len(scoped)), "suffix": "%", "items": [{"key": key, "label": key, "value": counts[key], "tone": VERIFICATION_TONE[key]} for key in VERIFICATION_ORDER]},
            "coverage": {"value": coverage_value(state), "suffix": "%", "items": [{"key": "vs_previous_run", "label": "vs_previous_run", "value": delta, "tone": "success" if delta > 0 else "error" if delta < 0 else "neutral"}]},
            "changes": {"value": len(state.changes), "items": [{"key": key, "label": key, "value": value, "tone": CHANGE_TONE[key]} for key, value in changes.items()]},
        },
        "requirements": rows,
        "selected_requirement": requirement_detail(state, ranked[0], locale) if ranked else None,
        "verification_status": [{"key": key, "name": key, "value": counts[key], "tone": VERIFICATION_TONE[key]} for key in VERIFICATION_ORDER],
        "coverage_trend": trend,
        "activity": activity(state, events, locale, 6),
        "attention_count": sum(item["count"] for item in attention_items if item["severity"] != "info"),
        "pending_proposals": len(pending_proposals(state, proposals)),
    }


def release_view(state: ProjectState) -> dict[str, Any]:
    scoped = in_scope(state)
    return {**state.release, "project_id": state.id, "baseline": active_baseline(state), "coverage": coverage_value(state), "verification": pct(verification_counts(state)["passed"], len(scoped))}


def project_view(state: ProjectState, locale: str = "en") -> dict[str, Any]:
    return {
        "id": state.id,
        "organization_id": state.project["organization_id"],
        "slug": state.project["slug"],
        "name": state.project["name"],
        "client": state.project["client"],
        "description": loc(state.project["description"], locale),
        "status": state.release["status"],
        "release_id": state.release["id"],
        "release_name": state.release["name"],
        "release": state.release["name"],
        "baseline": active_baseline(state),
        "requirements_count": len(state.requirements),
        "readiness": readiness(state)["score"],
    }


# --- Delivery ------------------------------------------------------------

def story(state: ProjectState, locale: str) -> dict[str, str]:
    scoped = in_scope(state)
    counts = verification_counts(state)
    changes = change_counts(state)
    pending = sum(item["scope_status"] == "pending" for item in state.requirements)
    status = state.release["status"]
    approval = {
        "accepted": T(locale, "The client accepted the release.", "El cliente aceptó la release."),
        "rejected": T(locale, "The client rejected the release.", "El cliente rechazó la release."),
        "revision_requested": T(locale, "The client requested a revision.", "El cliente pidió una revisión."),
        "ready": T(locale, "Waiting for the client decision.", "Esperando la decisión del cliente."),
    }.get(status, T(locale, "Client sign-off is pending.", "La aprobación del cliente está pendiente."))
    return {
        "promised": T(locale, "{n} requirements in baseline {v}.", "{n} requisitos en la línea base {v}.", n=len(scoped), v=active_baseline(state)),
        "delivered": T(locale, "{p} of {n} requirements demonstrated.", "{p} de {n} requisitos demostrados.", p=counts["passed"], n=len(scoped)),
        "changed": T(locale, "{t} changes tracked; {a} approved, {p} pending, {r} rejected.", "{t} cambios registrados; {a} aprobados, {p} pendientes, {r} rechazados.", t=len(state.changes), a=changes["approved"], p=changes["proposed"], r=changes["rejected"]),
        "remaining": T(locale, "{f} failed verifications, {i} still to verify and {p} requirements pending agreement.", "{f} verificaciones fallidas, {i} pendientes de verificar y {p} requisitos pendientes de acuerdo.", f=counts["failed"], i=counts["in_progress"] + counts["not_started"], p=pending),
        "approval": approval,
    }


def latest_evidence(state: ProjectState) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    scoped = {item["id"] for item in in_scope(state)}
    for item in sorted(state.evidence, key=lambda item: item["created_at"]):
        if item["requirement_id"] in scoped:
            latest[item["requirement_id"]] = item
    return [latest[key] for key in sorted(latest)]


def review(state: ProjectState, locale: str) -> dict[str, Any]:
    decision = state.decisions[-1] if state.decisions else None
    header = project_header(state)
    return {
        "project": header,
        "release": header["release"],
        "release_status": state.release["status"],
        "story": story(state, locale),
        "evidence": [{"id": item["id"], "artifact": item["artifact"], "summary": loc(item["summary"], locale), "state": item["state"], "requirement_id": item["requirement_id"]} for item in latest_evidence(state)],
        "requirements": [requirement_row(state, item, locale) for item in sorted(in_scope(state), key=lambda item: item["id"])],
        "decision": {"decision": decision["decision"], "comment": decision["comment"], "at": decision["at"]} if decision else None,
    }


def delivery_pack(state: ProjectState, locale: str, generated_at: str) -> dict[str, Any]:
    return {
        "release": state.release["name"],
        "project": project_view(state, locale),
        "story": story(state, locale),
        "readiness": readiness(state),
        "requirements": requirement_rows(state, locale),
        "evidence": [evidence_view(item, locale) for item in latest_evidence(state)],
        "generated_at": generated_at,
    }


def prepare_delivery_checks(state: ProjectState, proposals: list[dict[str, Any]], locale: str) -> dict[str, Any]:
    scoped = in_scope(state)
    counts = verification_counts(state)
    pending_scope = sum(item["scope_status"] == "pending" for item in state.requirements)
    proposed = change_counts(state)["proposed"]
    without_criteria = sum(not item["criteria"] for item in scoped)
    covered = {item["requirement_id"] for item in state.evidence}
    without_evidence = sum(item["id"] not in covered for item in scoped)
    comments = len(open_comments(state))
    drafts = len(pending_proposals(state, proposals))

    def check(key: str, label: tuple[str, str], count: int, bad: str, detail_ok: tuple[str, str], detail_bad: tuple[str, str, str, str]) -> dict[str, Any]:
        status = bad if count else "ready"
        detail = plural(locale, count, *detail_bad) if count else T(locale, *detail_ok, total=len(scoped))
        return {"key": key, "label": T(locale, *label), "status": status, "detail": detail, "count": count}

    checks = [
        check("requirements_agreed", ("Requirements agreed", "Requisitos acordados"), pending_scope, "attention", ("{total} in-scope requirements agreed", "{total} requisitos en alcance acordados"), ("{n} requirement pending agreement", "{n} requirements pending agreement", "{n} requisito pendiente de acuerdo", "{n} requisitos pendientes de acuerdo")),
        check("scope_changes_resolved", ("Scope changes resolved", "Cambios de alcance resueltos"), proposed, "blocked", ("No changes awaiting a decision", "Ningún cambio pendiente de decisión"), ("{n} change needs a decision", "{n} changes need a decision", "{n} cambio necesita una decisión", "{n} cambios necesitan una decisión")),
        check("acceptance_criteria", ("Acceptance criteria exist", "Existen criterios de aceptación"), without_criteria, "attention", ("Every in-scope requirement has criteria", "Todos los requisitos en alcance tienen criterios"), ("{n} requirement without criteria", "{n} requirements without criteria", "{n} requisito sin criterios", "{n} requisitos sin criterios")),
        check("verification_passed", ("Verification passed", "Verificación superada"), counts["failed"], "blocked", ("No failed verifications", "Ninguna verificación fallida"), ("{n} failed verification", "{n} failed verifications", "{n} verificación fallida", "{n} verificaciones fallidas")),
        check("verification_coverage", ("Verification coverage", "Cobertura de verificación"), without_evidence, "attention", ("Every in-scope requirement has evidence", "Todos los requisitos en alcance tienen evidencia"), ("{n} requirement without evidence", "{n} requirements without evidence", "{n} requisito sin evidencia", "{n} requisitos sin evidencia")),
        check("client_comments", ("Client comments", "Comentarios del cliente"), comments, "attention", ("No unresolved comments", "Ningún comentario sin resolver"), ("{n} unresolved comment", "{n} unresolved comments", "{n} comentario sin resolver", "{n} comentarios sin resolver")),
        check("agent_proposals", ("Agent proposals reviewed", "Propuestas de agentes revisadas"), drafts, "attention", ("No proposals awaiting review", "Ninguna propuesta pendiente de revisión"), ("{n} proposal awaiting review", "{n} proposals awaiting review", "{n} propuesta pendiente de revisión", "{n} propuestas pendientes de revisión")),
    ]
    return {
        "release": state.release["name"],
        "ready": all(item["status"] == "ready" for item in checks),
        "checks": checks,
        "next_actions": [item["title"] for item in attention(state, proposals, locale) if item["severity"] != "info"],
    }


def scope_version_view(state: ProjectState, item: dict[str, Any], locale: str) -> dict[str, Any]:
    view = {**loc({key: value for key, value in item.items() if key != "created_by"}, locale), "created_by": actor(state, item.get("created_by"), locale)}
    diff = view.get("diff")
    if diff and diff.get("added"):
        diff["added"] = [{**added, "component": component_name(added["component"], locale)} if added.get("component") else added for added in diff["added"]]
    return view


def proposal_view(item: dict[str, Any], locale: str, state: ProjectState | None = None) -> dict[str, Any]:
    view = loc({key: value for key, value in item.items() if key not in {"decided_by", "agent_id"}}, locale)
    view["agent"] = agent_ref(item["agent_id"], locale)
    view["decided_by"] = actor(state, item["decided_by"], locale) if state and item.get("decided_by") else None
    return view
