"""Agent tool execution and proposal building over the live project facts.

Tools read the project state (readiness, requirements, evidence, changes) and
return ``(output, summary, refs)``. Summaries are bilingual and resolved when
the run's events are streamed. Every agent run ends with one draft proposal,
built by ``build_proposal`` from the tool outputs.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from . import projections as P
from .seed import L, ProjectState

TOOL_LABELS: dict[str, tuple[str, str]] = {
    "get_delivery_readiness": ("Calculate delivery readiness", "Calcular la preparación de la entrega"),
    "list_attention_items": ("List attention items", "Listar puntos de atención"),
    "inspect_requirement": ("Inspect requirement", "Revisar el requisito"),
    "analyze_requirement": ("Analyze requirement", "Analizar el requisito"),
    "generate_acceptance_criteria": ("Draft acceptance criteria", "Redactar criterios de aceptación"),
    "plan_verification": ("Plan verification", "Planificar la verificación"),
    "classify_change": ("Classify the change", "Clasificar el cambio"),
    "summarize_delivery": ("Summarize delivery", "Resumir la entrega"),
    "inspect_scope": ("Inspect baseline", "Revisar la línea base"),
    "list_requirements": ("List requirements", "Listar requisitos"),
    "discover_routes": ("Discover routes", "Descubrir rutas"),
    "run_smoke_check": ("Run smoke check", "Ejecutar prueba de humo"),
    "list_evidence": ("List evidence", "Listar evidencias"),
}

DEFAULT_INPUT = "Review the active delivery context."

ROLE_NAMES = {
    "owner": ("the project owner", "responsable del proyecto"),
    "delivery_lead": ("a delivery lead", "responsable de entrega"),
    "qa": ("a QA engineer", "ingeniero de QA"),
    "client_reviewer": ("a client reviewer", "revisor del cliente"),
}


def tool_label(tool: str) -> dict[str, str]:
    en, es = TOOL_LABELS.get(tool, (tool, tool))
    return L(en, es)


def req_ref(requirement: dict[str, Any]) -> dict[str, str]:
    return {"type": "requirement", "id": requirement["id"], "label": requirement["id"]}


def pick_requirement(state: ProjectState, requirement_id: str | None) -> dict[str, Any] | None:
    if requirement_id:
        return state.requirement(requirement_id)
    scoped = [item for item in state.requirements if item["scope_status"] != "out_of_scope"]
    return sorted(scoped, key=P.attention_rank)[0] if scoped else None


def _require(ctx: dict[str, Any]) -> dict[str, Any]:
    requirement = ctx.get("requirement")
    if requirement is None:
        raise ValueError("Requirement not found")
    return requirement


def _related_requirements(state: ProjectState, text: str, limit: int = 3) -> list[dict[str, Any]]:
    words = {word.strip(".,;:!?()").lower() for word in text.split() if len(word) > 3}
    scored = []
    for item in state.requirements:
        haystack = f"{item['title']['en']} {item['title']['es']} {item['description']['en']} {item['description']['es']}".lower()
        score = sum(word in haystack for word in words)
        if score:
            scored.append((score, item["id"], item))
    scored.sort(key=lambda entry: (-entry[0], entry[1]))
    return [entry[2] for entry in scored[:limit]]


def _simulated_smoke(ctx: dict[str, Any]) -> dict[str, Any]:
    requirement = ctx.get("requirement")
    routes = ctx.get("routes") or [ctx["target_url"]]
    failing = bool(requirement and requirement.get("defect"))
    observations = [{"route": route, "status_code": 200, "passed": not failing, "summary": "Page rendered and the expected controls were present." if not failing else "Page rendered but the expected outcome was not observed."} for route in routes]
    return {"target_url": ctx["target_url"], "routes_checked": len(routes), "observations": observations, "state": "not_demonstrated" if failing else "demonstrated", "simulated": True}


def execute(tool: str, ctx: dict[str, Any], outputs: dict[str, Any]) -> tuple[Any, dict[str, str], list[dict[str, str]]]:
    state: ProjectState = ctx["state"]
    provider = ctx["provider"]
    if tool == "get_delivery_readiness":
        result = P.readiness(state)
        summary = L(
            f"Readiness {result['score']}/100: {result['demonstrated']} demonstrated, {result['not_demonstrated']} not demonstrated, {result['without_evidence']} without evidence.",
            f"Preparación {result['score']}/100: {result['demonstrated']} demostrados, {result['not_demonstrated']} sin demostrar, {result['without_evidence']} sin evidencia.",
        )
        return result, summary, []
    if tool == "list_attention_items":
        items_en = P.attention(state, ctx["proposals"], "en")
        items_es = P.attention(state, ctx["proposals"], "es")
        if not items_en:
            return [], L("Nothing needs attention.", "Nada requiere atención."), []
        summary = L(f"{len(items_en)} attention items; top: {items_en[0]['title']}.", f"{len(items_es)} puntos de atención; el principal: {items_es[0]['title']}.")
        refs = [{"type": "requirement", "id": item["target"]["requirement_id"], "label": item["target"]["requirement_id"]} for item in items_en if item["target"].get("requirement_id")][:3]
        return items_en, summary, refs
    if tool == "inspect_requirement":
        requirement = _require(ctx)
        detail = P.requirement_detail(state, requirement, "en")
        summary = L(
            f"{requirement['id']} · {requirement['title']['en']}: " + P.plural("en", len(requirement["criteria"]), "{n} criterion", "{n} criteria", "", "") + ", " + P.plural("en", detail["evidence_count"], "{n} evidence item", "{n} evidence items", "", "") + f", verification {requirement['verification'].replace('_', ' ')}.",
            f"{requirement['id']} · {requirement['title']['es']}: " + P.plural("es", len(requirement["criteria"]), "", "", "{n} criterio", "{n} criterios") + ", " + P.plural("es", detail["evidence_count"], "", "", "{n} evidencia", "{n} evidencias") + f", verificación {({'passed': 'superada', 'failed': 'fallida', 'in_progress': 'en curso', 'not_started': 'sin empezar'})[requirement['verification']]}.",
        )
        return detail, summary, [req_ref(requirement)]
    if tool == "analyze_requirement":
        requirement = _require(ctx)
        base = provider.analyze_requirement({"title": requirement["title"]["en"], "description": requirement["description"]["en"]})
        gaps_en, gaps_es = [], []
        if len(requirement["criteria"]) < 3:
            gaps_en.append(f"only {len(requirement['criteria'])} acceptance criteria")
            gaps_es.append(f"solo {len(requirement['criteria'])} criterios de aceptación")
        if not P.evidence_for(state, requirement["id"]):
            gaps_en.append("no evidence yet")
            gaps_es.append("todavía sin evidencia")
        open_count = len(P.open_comments(state, requirement["id"]))
        if open_count:
            gaps_en.append(P.plural("en", open_count, "{n} open comment", "{n} open comments", "", ""))
            gaps_es.append(P.plural("es", open_count, "", "", "{n} comentario abierto", "{n} comentarios abiertos"))
        if requirement["scope_status"] == "pending":
            gaps_en.append("scope not agreed")
            gaps_es.append("alcance sin acordar")
        result = {**base, "missing_criteria": len(requirement["criteria"]) < 3, "gaps": gaps_en}
        summary = L(
            f"{requirement['id']}: " + (", ".join(gaps_en) if gaps_en else "no gaps found") + ".",
            f"{requirement['id']}: " + (", ".join(gaps_es) if gaps_es else "sin carencias detectadas") + ".",
        )
        return result, summary, [req_ref(requirement)]
    if tool == "generate_acceptance_criteria":
        requirement = _require(ctx)
        title = requirement["title"]
        before = [item["text"] for item in requirement["criteria"]]
        pool = [
            L(f"Error states for “{title['en']}” show a clear, translated message", f"Los errores de «{title['es']}» muestran un mensaje claro y traducido"),
            L(f"“{title['en']}” is recorded in the audit log with actor and timestamp", f"«{title['es']}» queda registrado en la auditoría con autor y fecha"),
            L(f"“{title['en']}” completes in under 2 seconds for 95% of requests", f"«{title['es']}» se completa en menos de 2 segundos en el 95 % de las peticiones"),
        ]
        existing = {item["en"] for item in before}
        added = [item for item in pool if item["en"] not in existing][: max(1, 4 - len(before))]
        request = ctx["input"].strip()
        if request and request != DEFAULT_INPUT:
            added.append(L(f"Covers the request: {request}", f"Cubre la petición: {request}"))
        after = before + added
        result = {"criteria": [{"text": item["en"], "type": "semantic", "automated": True} for item in after], "before": before, "after": after, "status": "draft"}
        summary = L(P.plural("en", len(added), "Drafted {n} new criterion", "Drafted {n} new criteria", "", "") + f"; {len(after)} in total for {requirement['id']}.", P.plural("es", len(added), "", "", "Redactado {n} criterio nuevo", "Redactados {n} criterios nuevos") + f"; {len(after)} en total para {requirement['id']}.")
        return result, summary, [req_ref(requirement)]
    if tool == "plan_verification":
        requirement = _require(ctx)
        owner = state.member(requirement["owner_id"]) or {"role": "member"}
        role_en, role_es = ROLE_NAMES.get(owner["role"], (owner["role"], owner["role"]))
        component_es = P.COMPONENT_ES.get(requirement["component"], requirement["component"])
        steps = [L(f"Open {requirement['component']} in the portal as {role_en}", f"Abrir {component_es} en el portal como {role_es}")]
        steps += [L(f"Verify: {item['text']['en']}", f"Verificar: {item['text']['es']}") for item in requirement["criteria"]]
        if not requirement["criteria"]:
            steps.append(L(f"Verify the described behaviour: {requirement['description']['en']}", f"Verificar el comportamiento descrito: {requirement['description']['es']}"))
        steps.append(L("Capture screenshot and DOM snapshot as evidence", "Capturar pantalla e instantánea del DOM como evidencia"))
        result = {"provider": "BrowserAgent", "steps": steps, "requires_human_confirmation": not requirement["criteria"]}
        summary = L(f"{len(steps)}-step browser plan for {requirement['id']}.", f"Plan de navegador de {len(steps)} pasos para {requirement['id']}.")
        return result, summary, [req_ref(requirement)]
    if tool == "classify_change":
        request = ctx["input"]
        baseline = P.active_baseline(state)
        result = provider.classify_change(baseline, request)
        related = _related_requirements(state, request)
        result["related_requirement_ids"] = [item["id"] for item in related]
        result["baseline"] = baseline
        label = {"possible_scope_change": ("possible scope change", "posible cambio de alcance"), "clarification": ("clarification", "aclaración")}.get(result["classification"], (result["classification"], result["classification"]))
        summary = L(f"Classified as {label[0]} against {baseline}; related: {', '.join(result['related_requirement_ids']) or 'none'}.", f"Clasificado como {label[1]} frente a {baseline}; relacionados: {', '.join(result['related_requirement_ids']) or 'ninguno'}.")
        return result, summary, [req_ref(item) for item in related]
    if tool == "summarize_delivery":
        story = {"en": P.story(state, "en"), "es": P.story(state, "es")}
        result = provider.summarize_delivery({"question": ctx["input"], **story["en"]})
        return {**result, "story": story}, L(story["en"]["delivered"] + " " + story["en"]["remaining"], story["es"]["delivered"] + " " + story["es"]["remaining"]), []
    if tool == "inspect_scope":
        versions = sorted(state.scope_versions, key=lambda item: item["created_at"], reverse=True)
        active = P.active_baseline(state)
        drafts = sum(item["status"] == "draft" for item in versions)
        result = {"active_version": active, "versions": [{"version": item["version"], "status": item["status"]} for item in versions]}
        return result, L(f"Active baseline {active}; {len(versions)} versions, {drafts} drafts.", f"Línea base activa {active}; {len(versions)} versiones, {drafts} borradores."), [{"type": "scope_version", "id": active, "label": active}]
    if tool == "list_requirements":
        items = [{"human_id": item["id"], "title": item["title"]["en"], "scope_status": item["scope_status"], "verification": item["verification"], "criteria": len(item["criteria"])} for item in state.requirements]
        pending = sum(item["scope_status"] == "pending" for item in items)
        thin = sum(item["criteria"] < 2 and item["scope_status"] != "out_of_scope" for item in items)
        return items, L(f"{len(items)} requirements: {pending} pending agreement, {thin} with fewer than 2 criteria.", f"{len(items)} requisitos: {pending} pendientes de acuerdo, {thin} con menos de 2 criterios."), []
    if tool == "list_evidence":
        scoped = P.in_scope(state)
        covered = {item["requirement_id"] for item in state.evidence}
        missing = [item["id"] for item in sorted(scoped, key=P.attention_rank) if item["id"] not in covered]
        weak = sorted({item["requirement_id"] for item in P.latest_evidence(state) if item["state"] != "demonstrated"})
        result = {"total": len(state.evidence), "covered": len(covered & {item["id"] for item in scoped}), "in_scope": len(scoped), "missing": missing, "weak": weak}
        refs = [{"type": "requirement", "id": key, "label": key} for key in (missing + weak)[:4]]
        return result, L(f"{len(state.evidence)} evidence items; {len(missing)} requirements without evidence, {len(weak)} with weak evidence.", f"{len(state.evidence)} evidencias; {len(missing)} requisitos sin evidencia, {len(weak)} con evidencia débil."), refs
    if tool == "discover_routes":
        try:
            result = ctx["qa"].discover(ctx["target_url"], max_routes=ctx["max_steps"])
        except httpx.HTTPError:
            if not ctx["mock"]:
                raise
            result = {"target_url": ctx["target_url"], "routes": ctx.get("routes") or [ctx["target_url"]], "simulated": True}
        routes = result.get("routes", [])
        return result, L(f"Found {len(routes)} reachable routes.", f"Encontradas {len(routes)} rutas accesibles."), []
    if tool == "run_smoke_check":
        try:
            result = ctx["qa"].smoke_check(ctx["target_url"], routes=ctx.get("routes") or None, max_steps=ctx["max_steps"])
        except httpx.HTTPError:
            if not ctx["mock"]:
                raise
            result = _simulated_smoke(ctx)
        requirement = ctx.get("requirement")
        if requirement and requirement.get("defect"):
            result["state"] = "not_demonstrated"
        key = f"agent-runs/{ctx['run_id']}/qa-observations.json"
        content = json.dumps(result, ensure_ascii=False, sort_keys=True, default=str).encode()
        stored = ctx["storage"].put_object(key, content, "application/json")
        result["evidence_artifact"] = key
        result["evidence_sha256"] = stored.get("sha256", ctx["storage"].compute_hash(content))
        passed = sum(bool(item.get("passed")) for item in result.get("observations", []))
        total = len(result.get("observations", []))
        refs = [{"type": "evidence", "id": key, "label": "qa-observations.json"}] + ([req_ref(requirement)] if requirement else [])
        return result, L(f"{passed} of {total} observations passed; state {result.get('state', 'inconclusive').replace('_', ' ')}.", f"{passed} de {total} observaciones superadas; estado {result.get('state', 'inconclusive').replace('_', ' ')}."), refs
    raise ValueError(f"Unsupported agent tool: {tool}")


# --- Proposals -----------------------------------------------------------------

def build_proposal(agent_id: str, ctx: dict[str, Any], outputs: dict[str, Any]) -> dict[str, Any]:
    state: ProjectState = ctx["state"]
    requirement = ctx.get("requirement")
    rid = requirement["id"] if requirement else None
    if agent_id == "requirements-coach":
        data = outputs["generate_acceptance_criteria"]
        added = len(data["after"]) - len(data["before"])
        return {"kind": "criteria", "requirement_id": rid, "title": L(f"Acceptance criteria for {rid}", f"Criterios de aceptación para {rid}"), "summary": L(P.plural("en", added, "Adds {n} criterion", "Adds {n} criteria", "", "") + f" to {rid}: {requirement['title']['en']}.", P.plural("es", added, "", "", "Añade {n} criterio", "Añade {n} criterios") + f" a {rid}: {requirement['title']['es']}."), "payload": {"before": data["before"], "after": data["after"]}}
    if agent_id == "verification-planner":
        data = outputs["plan_verification"]
        return {"kind": "verification_plan", "requirement_id": rid, "title": L(f"Verification plan for {rid}", f"Plan de verificación para {rid}"), "summary": L(f"{len(data['steps'])} steps to verify {requirement['title']['en']}.", f"{len(data['steps'])} pasos para verificar {requirement['title']['es']}."), "payload": {"steps": data["steps"]}}
    if agent_id == "qa-explorer":
        data = outputs["run_smoke_check"]
        observations = [str(item.get("summary") or f"{item.get('route', '')} -> {item.get('status_code', '')}") for item in data.get("observations", [])]
        state_value = data.get("state", "inconclusive")
        if state_value not in {"demonstrated", "partially_demonstrated", "not_demonstrated"}:
            state_value = "partially_demonstrated"
        text = {"demonstrated": ("The smoke check observed the expected behaviour.", "La prueba de humo observó el comportamiento esperado."), "partially_demonstrated": ("The smoke check observed part of the expected behaviour.", "La prueba de humo observó parte del comportamiento esperado."), "not_demonstrated": ("The smoke check did not observe the expected behaviour.", "La prueba de humo no observó el comportamiento esperado.")}[state_value]
        return {"kind": "evidence", "requirement_id": rid, "title": L(f"QA observations for {rid}", f"Observaciones QA para {rid}"), "summary": L(text[0], text[1]), "payload": {"artifact": data["evidence_artifact"], "sha256": data.get("evidence_sha256", ""), "summary": L(text[0], text[1]), "state": state_value, "observations": observations}}
    if agent_id == "change-radar":
        data = outputs["classify_change"]
        request = ctx["input"].strip()
        related = [state.requirement(key) for key in data.get("related_requirement_ids", [])]
        related = [item for item in related if item]
        title = request if len(request) <= 80 else request[:77] + "..."
        original = related[0]["description"] if related else L(f"Not covered by baseline {data['baseline']}.", f"No está cubierto por la línea base {data['baseline']}.")
        impact = "High" if data["classification"] == "possible_scope_change" else "Low"
        return {"kind": "change", "requirement_id": related[0]["id"] if related else None, "title": L(f"Change request: {title}", f"Petición de cambio: {title}"), "summary": L(f"Classified as {data['classification'].replace('_', ' ')} with {round(data.get('confidence', 0) * 100)}% confidence.", f"Clasificado como {({'possible_scope_change': 'posible cambio de alcance', 'clarification': 'aclaración'}).get(data['classification'], data['classification'])} con un {round(data.get('confidence', 0) * 100)} % de confianza."), "payload": {"title": title, "original": original, "proposed": request, "classification": data["classification"], "impact": impact, "requirement_ids": [item["id"] for item in related]}}
    if agent_id == "agreement-analyst":
        items = []
        for item in sorted(P.in_scope(state), key=P.attention_rank):
            if item["scope_status"] == "pending":
                items.append({"requirement_id": item["id"], "text": L(f"Scope of “{item['title']['en']}” is not agreed yet; confirm it before sign-off.", f"El alcance de «{item['title']['es']}» aún no está acordado; confirmadlo antes de la aprobación.")})
            elif len(item["criteria"]) < 2:
                items.append({"requirement_id": item["id"], "text": L(f"Only {len(item['criteria'])} acceptance criteria; add measurable thresholds.", f"Solo {len(item['criteria'])} criterios de aceptación; añadid umbrales medibles.")})
            if len(items) == 3:
                break
        if requirement and all(entry["requirement_id"] != rid for entry in items) and len(items) < 3:
            items.append({"requirement_id": rid, "text": L(f"Review the wording of “{requirement['title']['en']}” against the agreement.", f"Revisad la redacción de «{requirement['title']['es']}» frente al acuerdo.")})
        return {"kind": "comments", "requirement_id": items[0]["requirement_id"] if items else None, "title": L(f"{len(items)} review comments on the baseline", f"{len(items)} comentarios de revisión sobre la línea base"), "summary": L("Comments on ambiguous or unagreed requirements.", "Comentarios sobre requisitos ambiguos o sin acordar."), "payload": {"items": items}}
    return _report(agent_id, ctx, outputs)


def _report(agent_id: str, ctx: dict[str, Any], outputs: dict[str, Any]) -> dict[str, Any]:
    state: ProjectState = ctx["state"]
    readiness = P.readiness(state)
    sections: list[dict[str, Any]] = []
    refs: list[dict[str, str]] = []
    if agent_id == "evidence-curator":
        data = outputs.get("list_evidence") or execute("list_evidence", ctx, outputs)[0]
        sections = [
            {"title": L("Coverage", "Cobertura"), "body": L(f"{data['covered']} of {data['in_scope']} in-scope requirements have evidence.", f"{data['covered']} de {data['in_scope']} requisitos en alcance tienen evidencia.")},
            {"title": L("Missing evidence", "Evidencias que faltan"), "body": L(", ".join(data["missing"]) or "None.", ", ".join(data["missing"]) or "Ninguna.")},
            {"title": L("Weak evidence", "Evidencias débiles"), "body": L(", ".join(data["weak"]) or "None.", ", ".join(data["weak"]) or "Ninguna.")},
        ]
        refs = [{"type": "requirement", "id": key, "label": key} for key in (data["missing"] + data["weak"])[:6]]
        title, summary = L("Evidence health report", "Informe del estado de las evidencias"), L(f"{len(data['missing'])} without evidence, {len(data['weak'])} weak.", f"{len(data['missing'])} sin evidencia, {len(data['weak'])} débiles.")
    elif agent_id == "acceptance-assistant":
        story_en, story_es = P.story(state, "en"), P.story(state, "es")
        names = {"promised": ("Promised", "Prometido"), "delivered": ("Delivered", "Entregado"), "changed": ("Changed", "Cambiado"), "remaining": ("Remaining", "Pendiente"), "approval": ("Approval", "Aprobación")}
        sections = [{"title": L(*names[key]), "body": L(story_en[key], story_es[key])} for key in names]
        title, summary = L("Client acceptance summary", "Resumen de aceptación para el cliente"), L(story_en["delivered"], story_es["delivered"])
    else:
        items_en = P.attention(state, ctx["proposals"], "en")
        items_es = P.attention(state, ctx["proposals"], "es")
        request = ctx["input"].strip()
        sections = [
            {"title": L("Readiness", "Preparación"), "body": L(f"Score {readiness['score']}/100 with {readiness['demonstrated']} of {readiness['total_requirements']} requirements demonstrated.", f"Puntuación {readiness['score']}/100 con {readiness['demonstrated']} de {readiness['total_requirements']} requisitos demostrados.")},
            {"title": L("Blockers", "Bloqueos"), "body": L("; ".join(item["title"] for item in items_en if item["severity"] != "info") or "No blockers.", "; ".join(item["title"] for item in items_es if item["severity"] != "info") or "Sin bloqueos.")},
            {"title": L("Next decision", "Próxima decisión"), "body": L(items_en[0]["title"] if items_en else "Send the release for acceptance.", items_es[0]["title"] if items_es else "Enviar la release a aceptación.")},
        ]
        if request and request != "Review the active delivery context.":
            sections.insert(0, {"title": L("Question", "Pregunta"), "body": L(request, request)})
        refs = [{"type": "requirement", "id": item["target"]["requirement_id"], "label": item["target"]["requirement_id"]} for item in items_en if item["target"].get("requirement_id")]
        title, summary = L("Delivery status report", "Informe del estado de la entrega"), L(f"Readiness {readiness['score']}/100; {len(items_en)} attention items.", f"Preparación {readiness['score']}/100; {len(items_es)} puntos de atención.")
    return {"kind": "report", "requirement_id": None, "title": title, "summary": summary, "payload": {"sections": sections, "refs": refs}}
