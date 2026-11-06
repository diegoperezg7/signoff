"""Deterministic, coherent seed for the two demo projects.

The seed stores facts only: requirements, criteria, evidence, verification
runs, changes, comments, scope versions and audit events. Every number shown
by the API is derived from these facts in ``projections.py``.

Visible text is stored as ``{"en": ..., "es": ...}`` and resolved per request.
Timestamps are relative to the moment the store is created so the demo always
reads as a live release.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

ORG_ID = "org_demo"
ACME_PROJECT_ID = "project_acme"
ACME_RELEASE_ID = "release_2_3"
CUSTOMER_PROJECT_ID = "project_demo"
CUSTOMER_RELEASE_ID = "release_1_0"


def L(en: str, es: str) -> dict[str, str]:
    return {"en": en, "es": es}


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def stable_uuid(*parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, "sda:" + ":".join(parts)))


class ProjectState:
    """All facts of one project. Mutated only under ``DemoStore.lock``."""

    def __init__(self, project: dict[str, Any], release: dict[str, Any], members: list[dict[str, Any]]) -> None:
        self.project = project
        self.release = release
        self.members = members
        self.requirements: list[dict[str, Any]] = []
        self.evidence: list[dict[str, Any]] = []
        self.runs: list[dict[str, Any]] = []
        self.changes: list[dict[str, Any]] = []
        self.comments: list[dict[str, Any]] = []
        self.scope_versions: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []

    @property
    def id(self) -> str:
        return self.project["id"]

    def requirement(self, key: str) -> dict[str, Any] | None:
        return next((item for item in self.requirements if key in (item["id"], item["uuid"])), None)

    def member(self, member_id: str) -> dict[str, Any] | None:
        return next((item for item in self.members if item["id"] == member_id), None)

    def member_by_role(self, role: str) -> dict[str, Any]:
        return next(item for item in self.members if item["role"] == role)


def _member(member_id: str, name: str, role: str, email: str) -> dict[str, Any]:
    initials = "".join(part[0] for part in name.split()[:2]).upper()
    return {"id": member_id, "name": name, "initials": initials, "kind": "client" if role == "client_reviewer" else "member", "role": role, "email": email}


# --- Criteria templates -----------------------------------------------------

GENERIC_CRITERIA = [
    L("“{en}” is available to every role allowed by the permissions matrix", "«{es}» está disponible para todos los roles autorizados en la matriz de permisos"),
    L("The result persists after a page refresh", "El resultado se mantiene al recargar la página"),
]

COMPONENT_CRITERIA: dict[str, list[dict[str, str]]] = {
    "Users": [L("Changes to the user record are visible in the user list within 5 seconds", "Los cambios en el usuario se ven en la lista de usuarios en menos de 5 segundos"), L("Validation errors are shown next to the affected field", "Los errores de validación se muestran junto al campo afectado")],
    "Billing": [L("Amounts match the billing provider to the cent", "Los importes coinciden al céntimo con el proveedor de pagos"), L("Every billing action is recorded with actor and timestamp", "Cada acción de facturación queda registrada con autor y fecha")],
    "Exports": [L("The file downloads from the admin panel", "El fichero se descarga desde el panel de administración"), L("Exported columns match the data dictionary", "Las columnas exportadas coinciden con el diccionario de datos")],
    "Notifications": [L("The notification is delivered within 2 minutes of the event", "El aviso se entrega en menos de 2 minutos desde el evento"), L("The message is shown in the user's language", "El mensaje se muestra en el idioma del usuario")],
    "Security": [L("Unauthorized attempts are rejected and logged", "Los intentos no autorizados se rechazan y se registran"), L("The control is enforced server side, not only in the UI", "El control se aplica en el servidor, no solo en la interfaz")],
    "Reporting": [L("Report totals match the source data", "Los totales del informe coinciden con los datos de origen"), L("The report loads in under 3 seconds with 12 months of data", "El informe carga en menos de 3 segundos con 12 meses de datos")],
}


def _criteria(project_id: str, human_id: str, title: dict[str, str], component: str, count: int) -> list[dict[str, Any]]:
    pool = [GENERIC_CRITERIA[0], *COMPONENT_CRITERIA.get(component, []), GENERIC_CRITERIA[1]]
    items = []
    for index, template in enumerate(pool[:count], 1):
        items.append({"id": stable_uuid(project_id, human_id, "criterion", str(index)), "text": L(template["en"].format(en=title["en"]), template["es"].format(es=title["es"])), "source": "baseline"})
    return items


def _explicit_criteria(project_id: str, human_id: str, texts: list[dict[str, str]]) -> list[dict[str, Any]]:
    return [{"id": stable_uuid(project_id, human_id, "criterion", str(index)), "text": text, "source": "baseline"} for index, text in enumerate(texts, 1)]


# --- Acme Inc. -----------------------------------------------------------

ACME_REQUIREMENTS: list[tuple[str, str, str, str, str]] = [
    ("Users", "User can sign in with email and password", "El usuario puede iniciar sesión con correo y contraseña", "Portal users sign in with their work email and a password.", "Los usuarios del portal inician sesión con su correo de trabajo y una contraseña."),
    ("Users", "User can sign in with SSO (SAML)", "El usuario puede iniciar sesión con SSO (SAML)", "Enterprise customers sign in through their SAML identity provider.", "Los clientes empresa inician sesión a través de su proveedor de identidad SAML."),
    ("Users", "User can edit profile details", "El usuario puede editar los datos de su perfil", "Users update their name, job title and phone number.", "Los usuarios actualizan su nombre, cargo y teléfono."),
    ("Users", "User can upload an avatar", "El usuario puede subir un avatar", "Users upload a PNG or JPG avatar up to 2 MB.", "Los usuarios suben un avatar PNG o JPG de hasta 2 MB."),
    ("Users", "Admin can invite users by email", "El administrador puede invitar usuarios por correo", "Admins invite new users and choose their initial role.", "Los administradores invitan a nuevos usuarios y eligen su rol inicial."),
    ("Users", "Invitation links expire after 7 days", "Los enlaces de invitación caducan a los 7 días", "Unused invitation links stop working after seven days.", "Los enlaces de invitación sin usar dejan de funcionar a los siete días."),
    ("Users", "Admin can deactivate a user", "El administrador puede desactivar un usuario", "Deactivated users cannot sign in and keep their history.", "Los usuarios desactivados no pueden entrar y conservan su historial."),
    ("Users", "Admin can assign roles", "El administrador puede asignar roles", "Admins switch users between viewer, editor and admin roles.", "Los administradores cambian a los usuarios entre los roles lector, editor y administrador."),
    ("Security", "Role permissions matrix is enforced", "Se aplica la matriz de permisos por rol", "Every screen and API call follows the agreed permissions matrix.", "Cada pantalla y llamada a la API sigue la matriz de permisos acordada."),
    ("Users", "User can switch organization", "El usuario puede cambiar de organización", "Users who belong to several organizations switch without signing out.", "Los usuarios que pertenecen a varias organizaciones cambian sin cerrar sesión."),
    ("Users", "User directory search", "Búsqueda en el directorio de usuarios", "Admins search users by name, email or team.", "Los administradores buscan usuarios por nombre, correo o equipo."),
    ("Users", "User list can be filtered by role and status", "La lista de usuarios se puede filtrar por rol y estado", "The user list filters by role and by active or inactive status.", "La lista de usuarios se filtra por rol y por estado activo o inactivo."),
    ("Users", "User can set language preference", "El usuario puede elegir su idioma", "Users choose English or Spanish for the whole portal.", "Los usuarios eligen inglés o español para todo el portal."),
    ("Users", "User can set time zone", "El usuario puede configurar su zona horaria", "Dates and times are shown in the user's time zone.", "Las fechas y horas se muestran en la zona horaria del usuario."),
    ("Billing", "Customer can view current plan", "El cliente puede ver su plan actual", "The billing page shows plan name, price and renewal date.", "La página de facturación muestra el plan, el precio y la fecha de renovación."),
    ("Billing", "Customer can upgrade or downgrade plan", "El cliente puede cambiar de plan", "Billing admins move between plans from the portal.", "Los administradores de facturación cambian de plan desde el portal."),
    ("Billing", "Customer can update payment method", "El cliente puede actualizar el método de pago", "Card details are replaced through the payment provider's secure form.", "Los datos de la tarjeta se sustituyen mediante el formulario seguro del proveedor de pagos."),
    ("Billing", "Invoices are listed with status", "Las facturas se listan con su estado", "Invoices show paid, pending or overdue status.", "Las facturas muestran si están pagadas, pendientes o vencidas."),
    ("Billing", "Invoice PDF can be downloaded", "Se puede descargar la factura en PDF", "Each invoice can be downloaded as a PDF with the legal details.", "Cada factura se puede descargar en PDF con los datos legales."),
    ("Billing", "VAT number is validated", "Se valida el número de IVA", "EU VAT numbers are validated before they are saved.", "Los números de IVA europeos se validan antes de guardarse."),
    ("Billing", "Failed payments trigger a retry", "Los pagos fallidos se reintentan", "A failed charge is retried three times over five days.", "Un cobro fallido se reintenta tres veces en cinco días."),
    ("Billing", "Billing contact can be changed", "Se puede cambiar el contacto de facturación", "Admins change the person who receives invoices.", "Los administradores cambian la persona que recibe las facturas."),
    ("Users", "User can reset password", "El usuario puede restablecer su contraseña", "Users request a reset link by email and choose a new password.", "Los usuarios piden un enlace por correo y eligen una nueva contraseña."),
    ("Billing", "Seat usage is shown against plan limits", "El uso de licencias se muestra frente al límite del plan", "Admins see used and available seats for their plan.", "Los administradores ven las licencias usadas y disponibles de su plan."),
    ("Billing", "Proration is applied on plan changes", "Se aplica prorrateo al cambiar de plan", "Mid-cycle plan changes are prorated on the next invoice.", "Los cambios de plan a mitad de ciclo se prorratean en la siguiente factura."),
    ("Billing", "Credit notes are issued for refunds", "Se emiten abonos por los reembolsos", "Every refund generates a credit note linked to its invoice.", "Cada reembolso genera un abono vinculado a su factura."),
    ("Billing", "Billing history covers 24 months", "El historial de facturación cubre 24 meses", "The billing history shows the last 24 months of invoices.", "El historial de facturación muestra las facturas de los últimos 24 meses."),
    ("Exports", "Export invoices to CSV", "Exportar facturas a CSV", "Billing admins export the invoice list to CSV.", "Los administradores de facturación exportan la lista de facturas a CSV."),
    ("Exports", "Export usage report to XLSX", "Exportar el informe de uso a XLSX", "The usage report can be downloaded as an Excel workbook.", "El informe de uso se puede descargar como libro de Excel."),
    ("Exports", "Scheduled exports run nightly", "Las exportaciones programadas se ejecutan cada noche", "Admins schedule an export that runs every night at 02:00.", "Los administradores programan una exportación que se ejecuta cada noche a las 02:00."),
    ("Exports", "Export respects active filters", "La exportación respeta los filtros activos", "Only the rows visible with the current filters are exported.", "Solo se exportan las filas visibles con los filtros actuales."),
    ("Exports", "Large exports are processed in the background", "Las exportaciones grandes se procesan en segundo plano", "Exports above 5,000 rows run as background jobs.", "Las exportaciones de más de 5.000 filas se ejecutan como tareas en segundo plano."),
    ("Exports", "User is notified when an export is ready", "Se avisa al usuario cuando la exportación está lista", "Users get an in-app and email notice with the download link.", "Los usuarios reciben un aviso en la aplicación y por correo con el enlace de descarga."),
    ("Exports", "Export files expire after 72 hours", "Los ficheros exportados caducan a las 72 horas", "Download links stop working 72 hours after generation.", "Los enlaces de descarga dejan de funcionar 72 horas después de generarse."),
    ("Exports", "Export column selection", "Selección de columnas en la exportación", "Users choose which columns to include before exporting.", "Los usuarios eligen qué columnas incluir antes de exportar."),
    ("Exports", "Exports use UTF-8 with BOM", "Las exportaciones usan UTF-8 con BOM", "CSV files open correctly in Excel with accents preserved.", "Los CSV se abren bien en Excel y conservan los acentos."),
    ("Exports", "Export includes generated-at timestamp", "La exportación incluye la fecha de generación", "Every export states when and by whom it was generated.", "Cada exportación indica cuándo y quién la generó."),
    ("Exports", "Export history per user", "Historial de exportaciones por usuario", "Users see their last 20 exports and can download them again.", "Los usuarios ven sus últimas 20 exportaciones y pueden volver a descargarlas."),
    ("Exports", "Export API endpoint with pagination", "Endpoint de exportación paginado en la API", "Integrators fetch export data through a paginated API.", "Los integradores obtienen los datos exportados mediante una API paginada."),
    ("Exports", "Exported dates follow the user's locale", "Las fechas exportadas siguen el formato del usuario", "Dates in exports use the user's language and time zone.", "Las fechas de las exportaciones usan el idioma y la zona horaria del usuario."),
    ("Exports", "Admin can export user data", "El administrador puede exportar datos de usuarios", "As an admin, I want to export user data in CSV format so that I can perform external analysis.", "Como administrador, quiero exportar los datos de usuarios en CSV para poder analizarlos fuera del portal."),
    ("Exports", "Export of audit log to CSV", "Exportación del registro de auditoría a CSV", "Compliance officers export the audit log for a date range.", "Los responsables de cumplimiento exportan el registro de auditoría de un rango de fechas."),
    ("Notifications", "Email notification on new invoice", "Aviso por correo de nueva factura", "Billing contacts receive an email when an invoice is issued.", "Los contactos de facturación reciben un correo cuando se emite una factura."),
    ("Notifications", "In-app notification centre", "Centro de notificaciones en la aplicación", "A bell menu lists the latest notifications for the user.", "Un menú con campana lista los últimos avisos del usuario."),
    ("Notifications", "Users can mute notification types", "Los usuarios pueden silenciar tipos de aviso", "Users switch off notification types they do not need.", "Los usuarios desactivan los tipos de aviso que no necesitan."),
    ("Notifications", "Weekly digest email", "Resumen semanal por correo", "Admins receive a weekly summary of account activity.", "Los administradores reciben un resumen semanal de la actividad de la cuenta."),
    ("Notifications", "Notification for failed payment", "Aviso de pago fallido", "Billing contacts are told immediately when a charge fails.", "Se avisa de inmediato a los contactos de facturación cuando falla un cobro."),
    ("Notifications", "Notification when a role changes", "Aviso cuando cambia un rol", "Users are notified when an admin changes their role.", "Se avisa a los usuarios cuando un administrador cambia su rol."),
    ("Notifications", "Unread badge count", "Contador de avisos sin leer", "The bell shows the number of unread notifications.", "La campana muestra el número de avisos sin leer."),
    ("Notifications", "Mark all notifications as read", "Marcar todos los avisos como leídos", "One action clears every unread notification.", "Una sola acción marca como leídos todos los avisos."),
    ("Notifications", "Email templates are localized ES/EN", "Las plantillas de correo están en ES/EN", "Every transactional email exists in English and Spanish.", "Cada correo transaccional existe en inglés y en español."),
    ("Notifications", "Webhook for notification events", "Webhook para eventos de notificación", "Customers subscribe an HTTPS endpoint to notification events.", "Los clientes suscriben un endpoint HTTPS a los eventos de notificación."),
    ("Security", "Session expires after 30 minutes idle", "La sesión caduca tras 30 minutos de inactividad", "Idle sessions end after 30 minutes and require a new sign-in.", "Las sesiones inactivas terminan a los 30 minutos y piden volver a entrar."),
    ("Security", "Password policy enforcement", "Se aplica la política de contraseñas", "Passwords need 12 characters and are checked against known leaks.", "Las contraseñas necesitan 12 caracteres y se comprueban contra filtraciones conocidas."),
    ("Security", "Account lockout after failed attempts", "Bloqueo de cuenta tras intentos fallidos", "Five failed sign-ins lock the account for 15 minutes.", "Cinco intentos fallidos bloquean la cuenta durante 15 minutos."),
    ("Security", "Login attempts are rate limited", "Los intentos de inicio de sesión tienen límite de frecuencia", "The sign-in endpoint limits attempts per IP address.", "El endpoint de inicio de sesión limita los intentos por dirección IP."),
    ("Security", "Two-factor authentication", "Autenticación en dos pasos", "Users protect their account with an authenticator app code.", "Los usuarios protegen su cuenta con un código de una app de autenticación."),
    ("Security", "Recovery codes for 2FA", "Códigos de recuperación para 2FA", "Users download ten single-use recovery codes.", "Los usuarios descargan diez códigos de recuperación de un solo uso."),
    ("Security", "Admin can force sign-out of all sessions", "El administrador puede cerrar todas las sesiones", "Admins end every active session of a user at once.", "Los administradores cierran a la vez todas las sesiones activas de un usuario."),
    ("Security", "Active sessions list", "Lista de sesiones activas", "Users see their active sessions with device and location.", "Los usuarios ven sus sesiones activas con dispositivo y ubicación."),
    ("Security", "IP allowlist for admin access", "Lista de IP permitidas para acceso de administrador", "Admin screens are only reachable from approved IP ranges.", "Las pantallas de administración solo son accesibles desde rangos de IP aprobados."),
    ("Security", "Data is encrypted at rest", "Los datos se cifran en reposo", "Databases and file storage use AES-256 encryption.", "Las bases de datos y el almacenamiento de ficheros usan cifrado AES-256."),
    ("Security", "Audit log for data changes", "Registro de auditoría de cambios de datos", "Every change to customer data records who, what and when.", "Cada cambio en los datos del cliente registra quién, qué y cuándo."),
    ("Security", "Security headers on every response", "Cabeceras de seguridad en todas las respuestas", "Responses include HSTS, CSP and frame protection headers.", "Las respuestas incluyen las cabeceras HSTS, CSP y de protección contra frames."),
    ("Security", "Personal data can be erased on request", "Los datos personales se pueden borrar a petición", "Admins erase a user's personal data within 30 days of a request.", "Los administradores borran los datos personales de un usuario en menos de 30 días desde la petición."),
    ("Security", "API tokens can be revoked", "Los tokens de API se pueden revocar", "Revoked API tokens stop working immediately.", "Los tokens de API revocados dejan de funcionar al instante."),
    ("Reporting", "Dashboard shows active users", "El panel muestra los usuarios activos", "The home dashboard shows daily and monthly active users.", "El panel de inicio muestra los usuarios activos diarios y mensuales."),
    ("Reporting", "Monthly revenue report", "Informe mensual de ingresos", "Finance sees revenue per month, plan and region.", "Finanzas ve los ingresos por mes, plan y región."),
    ("Reporting", "Report filters by date range", "Filtros de informe por rango de fechas", "Every report can be filtered by a custom date range.", "Cada informe se puede filtrar por un rango de fechas personalizado."),
    ("Reporting", "Charts render in under 2 seconds", "Los gráficos se muestran en menos de 2 segundos", "Report charts are interactive within two seconds.", "Los gráficos de los informes son interactivos en menos de dos segundos."),
    ("Users", "Support bulk user import", "Importación masiva de usuarios", "Admins import up to 5,000 users from a CSV file.", "Los administradores importan hasta 5.000 usuarios desde un fichero CSV."),
    ("Reporting", "Usage by feature report", "Informe de uso por funcionalidad", "Product owners see which features each team uses.", "Los responsables de producto ven qué funcionalidades usa cada equipo."),
    ("Reporting", "Saved report views", "Vistas de informe guardadas", "Users save filters and columns as a named view.", "Los usuarios guardan filtros y columnas como una vista con nombre."),
    ("Reporting", "Report sharing by link", "Compartir informes mediante enlace", "Users share a read-only report link with colleagues.", "Los usuarios comparten un enlace de solo lectura con sus compañeros."),
    ("Reporting", "Churn report by cohort", "Informe de bajas por cohorte", "Finance sees cancellations grouped by signup month.", "Finanzas ve las bajas agrupadas por mes de alta."),
    ("Reporting", "Report data refreshes hourly", "Los datos de los informes se actualizan cada hora", "Report data is never more than one hour old.", "Los datos de los informes nunca tienen más de una hora de antigüedad."),
    ("Reporting", "Report totals match billing", "Los totales de los informes cuadran con la facturación", "Revenue totals reconcile with issued invoices.", "Los totales de ingresos cuadran con las facturas emitidas."),
    ("Reporting", "Print-friendly report layout", "Diseño de informe apto para impresión", "Reports print on A4 without cut-off charts.", "Los informes se imprimen en A4 sin gráficos cortados."),
    ("Reporting", "Report access follows role permissions", "El acceso a informes sigue los permisos por rol", "Viewers only see the reports their role allows.", "Los lectores solo ven los informes que su rol permite."),
    ("Reporting", "Login activity report", "Informe de actividad de inicio de sesión", "Admins review sign-ins per user, date and device.", "Los administradores revisan los inicios de sesión por usuario, fecha y dispositivo."),
    ("Users", "Bulk import validation report", "Informe de validación de la importación masiva", "After an import, admins see accepted and rejected rows with reasons.", "Tras una importación, los administradores ven las filas aceptadas y rechazadas con el motivo."),
    ("Reporting", "Custom date presets for reports", "Rangos de fechas predefinidos en informes", "Reports offer last 7 days, 30 days and quarter presets.", "Los informes ofrecen rangos de últimos 7 días, 30 días y trimestre."),
    ("Users", "Dark mode for the portal", "Modo oscuro para el portal", "Users switch the portal to a dark colour theme.", "Los usuarios cambian el portal a un tema de color oscuro."),
    ("Notifications", "Mobile push notifications", "Notificaciones push en el móvil", "Users receive push notifications on a mobile app.", "Los usuarios reciben notificaciones push en una app móvil."),
    ("Users", "Real-time chat support", "Soporte por chat en tiempo real", "Users chat with support agents from inside the portal.", "Los usuarios hablan con el equipo de soporte por chat desde el portal."),
    ("Billing", "Multi-currency invoicing", "Facturación en varias monedas", "Invoices can be issued in EUR, USD and GBP.", "Las facturas se pueden emitir en EUR, USD y GBP."),
]

ACME_EXPLICIT_CRITERIA: dict[str, list[dict[str, str]]] = {
    "REQ-041": [
        L("Export includes all user fields as defined in the data dictionary", "La exportación incluye todos los campos de usuario definidos en el diccionario de datos"),
        L("CSV file is downloadable from the admin panel", "El fichero CSV se puede descargar desde el panel de administración"),
        L("Export includes data filters (date range, role, status)", "La exportación permite filtrar por rango de fechas, rol y estado"),
        L("System handles up to 10k records per export", "El sistema admite hasta 10.000 registros por exportación"),
    ],
    "REQ-023": [
        L("Reset link is sent within one minute of the request", "El enlace de restablecimiento llega en menos de un minuto"),
        L("Reset link expires after 60 minutes", "El enlace de restablecimiento caduca a los 60 minutos"),
        L("The new password must follow the password policy", "La nueva contraseña debe cumplir la política de contraseñas"),
    ],
    "REQ-057": [
        L("Users can enrol an authenticator app by scanning a QR code", "Los usuarios pueden registrar una app de autenticación escaneando un código QR"),
        L("Sign-in asks for a 6-digit code after the password", "El inicio de sesión pide un código de 6 dígitos tras la contraseña"),
        L("Admins can require 2FA for the whole organization", "Los administradores pueden exigir 2FA a toda la organización"),
    ],
    "REQ-063": [
        L("Every create, update and delete stores actor, field, old and new value", "Cada alta, cambio y baja guarda autor, campo, valor anterior y nuevo"),
        L("Audit entries cannot be edited or deleted", "Las entradas de auditoría no se pueden editar ni borrar"),
        L("Audit entries are kept for 13 months", "Las entradas de auditoría se conservan 13 meses"),
    ],
    "REQ-071": [],
}

ACME_SCOPE = {
    # 8 pending (linked to the two proposed changes) and 4 out of scope.
    "pending": {39, 52, 58, 61, 71, 74, 78, 81},
    "out_of_scope": {83, 84, 85, 86},
}
ACME_VERIFICATION = {
    "failed": {21, 30, 46, 55, 70, 77, 52, 61, 78},
    "in_progress": {33, 57, 58, 74},
    "not_started": {39, 71, 81, 83, 84, 85, 86},
}
# In-progress requirements with a partial observation already captured.
ACME_PARTIAL_EVIDENCE = {57, 74}
ACME_ACCEPTED = {1, 2, 3, 5, 7, 8, 15, 23}

ACME_CHANGES: list[dict[str, Any]] = [
    {"n": 10, "title": L("Clarify password reset link lifetime", "Aclarar la validez del enlace de restablecimiento"), "original": L("Users can reset their password by email.", "Los usuarios pueden restablecer la contraseña por correo."), "proposed": L("Reset links expire after 60 minutes.", "Los enlaces de restablecimiento caducan a los 60 minutos."), "classification": "clarification", "status": "approved", "impact": "Low", "reqs": [23], "source": "client", "days": 25, "decider": "u_laura"},
    {"n": 11, "title": L("Add date-range filter to user export", "Añadir filtro por fechas a la exportación de usuarios"), "original": L("Admins export all users to CSV.", "Los administradores exportan todos los usuarios a CSV."), "proposed": L("Admins filter the export by date range, role and status.", "Los administradores filtran la exportación por fechas, rol y estado."), "classification": "clarification", "status": "approved", "impact": "Medium", "reqs": [41], "source": "client", "days": 23, "decider": "u_laura"},
    {"n": 12, "title": L("Include role column in invoice export", "Incluir la columna de rol en la exportación de facturas"), "original": L("Invoice export contains invoice fields only.", "La exportación de facturas solo contiene campos de factura."), "proposed": L("Add the requesting user's role to each exported invoice row.", "Añadir el rol del usuario solicitante a cada fila exportada."), "classification": "clarification", "status": "approved", "impact": "Low", "reqs": [28], "source": "member", "days": 21, "decider": "u_tom"},
    {"n": 13, "title": L("Dark mode and mobile push notifications", "Modo oscuro y notificaciones push en el móvil"), "original": L("Release 2.3 covers the web portal with the light theme.", "La release 2.3 cubre el portal web con el tema claro."), "proposed": L("Add a dark theme and push notifications through a mobile app.", "Añadir un tema oscuro y notificaciones push mediante una app móvil."), "classification": "possible_scope_change", "status": "rejected", "impact": "High", "reqs": [83, 84], "source": "client", "days": 19, "decider": "u_laura"},
    {"n": 14, "title": L("Shorten idle session timeout to 30 minutes", "Reducir la caducidad de sesión inactiva a 30 minutos"), "original": L("Idle sessions expire after 60 minutes.", "Las sesiones inactivas caducan a los 60 minutos."), "proposed": L("Idle sessions expire after 30 minutes.", "Las sesiones inactivas caducan a los 30 minutos."), "classification": "clarification", "status": "approved", "impact": "Low", "reqs": [53], "source": "client", "days": 17, "decider": "u_laura"},
    {"n": 15, "title": L("Localize email templates to Spanish", "Traducir las plantillas de correo al español"), "original": L("Transactional emails are sent in English.", "Los correos transaccionales se envían en inglés."), "proposed": L("Every transactional email is available in English and Spanish.", "Cada correo transaccional está disponible en inglés y en español."), "classification": "possible_scope_change", "status": "approved", "impact": "Medium", "reqs": [51], "source": "client", "days": 15, "decider": "u_tom"},
    {"n": 16, "title": L("Live chat support and multi-currency invoicing", "Chat de soporte en directo y facturación en varias monedas"), "original": L("Support is handled by email; invoices are issued in EUR.", "El soporte se atiende por correo; las facturas se emiten en EUR."), "proposed": L("Add in-portal live chat and invoices in USD and GBP.", "Añadir chat en directo en el portal y facturas en USD y GBP."), "classification": "possible_scope_change", "status": "rejected", "impact": "High", "reqs": [85, 86], "source": "client", "days": 13, "decider": "u_laura"},
    {"n": 17, "title": L("Retry failed payments three times", "Reintentar tres veces los pagos fallidos"), "original": L("A failed payment marks the invoice as overdue.", "Un pago fallido marca la factura como vencida."), "proposed": L("Retry the charge three times over five days before marking it overdue.", "Reintentar el cobro tres veces en cinco días antes de marcarla como vencida."), "classification": "clarification", "status": "approved", "impact": "Medium", "reqs": [21], "source": "member", "days": 11, "decider": "u_tom"},
    {"n": 18, "title": L("Bulk user import and shareable reports", "Importación masiva de usuarios e informes compartibles"), "original": L("Users are invited one by one; reports are viewed inside the portal.", "Los usuarios se invitan uno a uno; los informes se ven dentro del portal."), "proposed": L("Import users from CSV with a validation report, and share or print reports.", "Importar usuarios desde CSV con informe de validación, y compartir o imprimir informes."), "classification": "possible_scope_change", "status": "proposed", "impact": "High", "reqs": [71, 81, 74, 78], "source": "client", "days": 6, "decider": None},
    {"n": 19, "title": L("Weekly digest sent on Monday mornings", "Enviar el resumen semanal los lunes por la mañana"), "original": L("A weekly digest is sent to admins.", "Se envía un resumen semanal a los administradores."), "proposed": L("The digest is sent every Monday at 08:00 in the admin's time zone.", "El resumen se envía cada lunes a las 08:00 en la zona horaria del administrador."), "classification": "clarification", "status": "approved", "impact": "Low", "reqs": [46], "source": "client", "days": 5, "decider": "u_laura"},
    {"n": 20, "title": L("Admin hardening and integration hooks", "Refuerzo de seguridad de administración y webhooks"), "original": L("Admin access is protected by password and session timeout.", "El acceso de administración se protege con contraseña y caducidad de sesión."), "proposed": L("Add 2FA recovery codes, an IP allowlist, notification webhooks and a paginated export API.", "Añadir códigos de recuperación 2FA, lista de IP permitidas, webhooks de avisos y una API de exportación paginada."), "classification": "possible_scope_change", "status": "proposed", "impact": "High", "reqs": [58, 61, 52, 39], "source": "member", "days": 3, "decider": None},
    {"n": 21, "title": L("Audit log retention of 13 months", "Conservar el registro de auditoría 13 meses"), "original": L("Audit entries are kept for 90 days.", "Las entradas de auditoría se conservan 90 días."), "proposed": L("Keep audit entries for 13 months to cover the yearly review.", "Conservar las entradas de auditoría 13 meses para cubrir la revisión anual."), "classification": "clarification", "status": "approved", "impact": "Medium", "reqs": [63], "source": "client", "days": 0.09, "decider": "u_tom"},
]

ACME_COMMENTS: list[dict[str, Any]] = [
    {"req": 23, "author": "u_tom", "text": L("The reset email arrives in Spanish for English users.", "El correo de restablecimiento llega en español a usuarios en inglés."), "hours": 400, "resolved": True},
    {"req": 53, "author": "u_laura", "text": L("Confirmed the 30-minute timeout with the client.", "Confirmado con el cliente el tiempo de 30 minutos."), "hours": 380, "resolved": True},
    {"req": 19, "author": "u_tom", "text": L("The invoice PDF must show our VAT number.", "El PDF de la factura debe mostrar nuestro número de IVA."), "hours": 300, "resolved": True},
    {"req": 30, "author": "u_irene", "text": L("The scheduled export failed twice on staging; checking the cron time zone.", "La exportación programada falló dos veces en staging; reviso la zona horaria del cron."), "hours": 70, "resolved": False},
    {"req": 70, "author": "u_marcos", "text": L("The revenue chart takes 3.4 s with 12 months of data.", "El gráfico de ingresos tarda 3,4 s con 12 meses de datos."), "hours": 30, "resolved": False},
    {"req": 57, "author": "u_tom", "text": L("We need SMS as a fallback for two-factor codes.", "Necesitamos SMS como alternativa para los códigos de dos pasos."), "hours": 20, "resolved": False},
    {"req": 41, "author": "u_tom", "text": L("Can the export include the last login date?", "¿Puede la exportación incluir la fecha del último acceso?"), "hours": 26, "resolved": False},
]

# Days ago for each verification run, oldest first.
ACME_RUN_DAYS = [24, 22, 20, 18, 16, 14, 11, 9, 7, 4, 2, 0.21]
ACME_RUN_CHUNKS = [50, 3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2]


# --- Northstar ------------------------------------------------------------

NORTHSTAR_REQUIREMENTS: list[tuple[str, str, str, str, str, str]] = [
    ("Authentication", "high", "Customer login", "Inicio de sesión de clientes", "Users can sign in with email and password.", "Los usuarios pueden iniciar sesión con correo y contraseña."),
    ("Security", "high", "Role-based access", "Acceso por roles", "Operators and managers see the correct navigation.", "Operadores y responsables ven la navegación que les corresponde."),
    ("Core workflow", "high", "Operations dashboard", "Panel de operaciones", "The dashboard shows open orders and attention items.", "El panel muestra los pedidos abiertos y los puntos de atención."),
    ("Core workflow", "medium", "Order search", "Búsqueda de pedidos", "Users can search orders by customer, status and date.", "Los usuarios pueden buscar pedidos por cliente, estado y fecha."),
    ("Core workflow", "high", "Order detail", "Detalle del pedido", "Users can inspect the complete order history.", "Los usuarios pueden consultar el historial completo del pedido."),
    ("Reporting", "medium", "CSV export", "Exportación a CSV", "Managers can export filtered order data.", "Los responsables pueden exportar los pedidos filtrados."),
    ("Notifications", "medium", "Email alerts", "Alertas por correo", "Managers receive alerts for overdue orders.", "Los responsables reciben alertas de pedidos retrasados."),
    ("Compliance", "high", "Audit history", "Historial de auditoría", "Every status change is visible in an audit timeline.", "Cada cambio de estado se ve en una línea de tiempo de auditoría."),
    ("Non-functional", "medium", "Responsive layout", "Diseño adaptable", "Core workflows work on tablet widths.", "Los flujos principales funcionan en anchuras de tableta."),
    ("Non-functional", "medium", "Performance budget", "Presupuesto de rendimiento", "Dashboard becomes interactive within two seconds.", "El panel es interactivo en menos de dos segundos."),
    ("Core workflow", "low", "Bulk status update", "Actualización masiva de estado", "Managers can update multiple orders at once.", "Los responsables pueden actualizar varios pedidos a la vez."),
    ("Support", "low", "Help centre link", "Enlace al centro de ayuda", "Users can reach support documentation from the app.", "Los usuarios pueden acceder a la documentación de soporte desde la aplicación."),
]

NORTHSTAR_CRITERIA = [
    L("A user can complete the {en} flow and see a clear success state.", "Un usuario puede completar el flujo «{es}» y ve un estado de éxito claro."),
    L("The {en} outcome is available after refresh.", "El resultado de «{es}» sigue disponible al recargar la página."),
]


# --- Builders --------------------------------------------------------------

def _evidence(project_id: str, requirement_id: str, artifact: str, state: str, summary: dict[str, str], at: datetime, run_id: str | None, kind: str = "screenshot", source: str = "verification") -> dict[str, Any]:
    digest = hashlib.sha256(f"{project_id}:{artifact}".encode()).hexdigest()
    return {
        "id": stable_uuid(project_id, "evidence", artifact),
        "requirement_id": requirement_id,
        "artifact": artifact,
        "storage_key": f"{project_id}/evidence/{artifact}",
        "kind": kind,
        "source": source,
        "state": state,
        "summary": summary,
        "sha256": digest,
        "size": 40_000 + int(digest[:4], 16),
        "created_at": iso(at),
        "run_id": run_id,
    }


RESULT_STATE = {"passed": "demonstrated", "failed": "not_demonstrated", "in_progress": "partially_demonstrated"}
RESULT_SUMMARY = {
    "passed": L("All acceptance criteria were observed in the browser run.", "Todos los criterios de aceptación se observaron en la ejecución del navegador."),
    "failed": L("At least one acceptance criterion was not met; see the captured screenshot.", "Al menos un criterio de aceptación no se cumplió; ver la captura."),
    "in_progress": L("Part of the criteria were observed; the run is still being reviewed.", "Se observó parte de los criterios; la ejecución sigue en revisión."),
}


def _seed_runs(state: ProjectState, anchor: datetime, run_days: list[float], chunks: list[int], ordered: list[dict[str, Any]], actor_id: str) -> None:
    """Assign each requirement with evidence to one historical verification run."""
    cursor = 0
    for number, (days, size) in enumerate(zip(run_days, chunks), 1):
        at = anchor - timedelta(days=days)
        run_id = stable_uuid(state.id, "run", str(number))
        results = []
        for requirement in ordered[cursor:cursor + size]:
            result = requirement["verification"]
            total = len(requirement["criteria"])
            covered = total if result == "passed" else max(0, total - 1) if result == "failed" else total // 2
            artifact = f"{requirement['id'].lower()}-run-{number:02d}.png"
            evidence = _evidence(state.id, requirement["id"], artifact, RESULT_STATE[result], RESULT_SUMMARY[result], at, run_id)
            state.evidence.append(evidence)
            results.append({"requirement_id": requirement["id"], "result": result, "criteria_covered": covered, "criteria_total": total, "evidence_ids": [evidence["id"]]})
        cursor += size
        state.runs.append({"id": run_id, "number": number, "at": iso(at), "actor_id": actor_id, "results": results})
        passed = sum(item["result"] == "passed" for item in results)
        failed = sum(item["result"] == "failed" for item in results)
        state.events.append({"event": "verification_run", "actor_id": actor_id, "created_at": iso(at), "params": {"count": len(results), "passed": passed, "failed": failed, "run": number}, "ref": None})


def _seed_changes(state: ProjectState, anchor: datetime, items: list[dict[str, Any]], prefix: str = "CHG") -> None:
    for item in items:
        at = anchor - timedelta(days=item["days"])
        code = f"{prefix}-{item['n']:03d}"
        reqs = [f"REQ-{n:03d}" for n in item["reqs"]]
        proposer = state.member_by_role("client_reviewer")["id"] if item["source"] == "client" else state.member_by_role("delivery_lead")["id"]
        created = at - timedelta(days=2) if item["decider"] else at
        change = {
            "id": stable_uuid(state.id, "change", code), "code": code, "title": item["title"], "original": item["original"], "proposed": item["proposed"],
            "classification": item["classification"], "status": item["status"], "impact": item["impact"], "requirement_ids": reqs, "source": item["source"],
            "created_at": iso(created), "created_by": proposer, "decided_by": item["decider"], "decided_at": iso(at) if item["decider"] else None,
        }
        state.changes.append(change)
        ref = {"type": "change", "id": change["id"], "label": code}
        state.events.append({"event": "change_proposed", "actor_id": proposer, "created_at": iso(created), "params": {"code": code}, "ref": ref})
        if item["decider"]:
            state.events.append({"event": f"change_{item['status']}", "actor_id": item["decider"], "created_at": iso(at), "params": {"code": code}, "ref": ref})


def _seed_comments(state: ProjectState, anchor: datetime, items: list[dict[str, Any]]) -> None:
    for index, item in enumerate(items, 1):
        at = anchor - timedelta(hours=item["hours"])
        requirement_id = f"REQ-{item['req']:03d}"
        comment = {"id": f"comment_{state.project['slug']}_{index:03d}", "requirement_id": requirement_id, "author_id": item["author"], "text": item["text"], "created_at": iso(at), "resolved": item["resolved"], "resolved_at": iso(at + timedelta(hours=20)) if item["resolved"] else None}
        state.comments.append(comment)
        ref = {"type": "requirement", "id": requirement_id, "label": requirement_id}
        state.events.append({"event": "comment_added", "actor_id": item["author"], "created_at": comment["created_at"], "params": {"requirement_id": requirement_id}, "ref": ref})
        if item["resolved"]:
            state.events.append({"event": "comment_resolved", "actor_id": state.member_by_role("owner")["id"], "created_at": comment["resolved_at"], "params": {"requirement_id": requirement_id}, "ref": ref})


def _acme(anchor: datetime) -> ProjectState:
    members = [
        _member("u_laura", "Laura Medina", "owner", "laura.medina@signoff.example"),
        _member("u_marcos", "Marcos Vidal", "delivery_lead", "marcos.vidal@signoff.example"),
        _member("u_irene", "Irene Sato", "qa", "irene.sato@signoff.example"),
        _member("u_tom", "Tom Becker", "client_reviewer", "reviewer@acme.example"),
    ]
    created = anchor - timedelta(days=27)
    project = {"id": ACME_PROJECT_ID, "organization_id": ORG_ID, "slug": "acme", "name": "Acme Inc.", "client": "Acme Inc.", "description": L("Client Portal delivery assurance workspace.", "Espacio de aseguramiento de entrega del portal de clientes."), "review_token": "acme-review-token"}
    release = {"id": ACME_RELEASE_ID, "name": "Release 2.3", "version": "2.3.0", "status": "in_signoff", "created_at": iso(created), "target_date": iso(anchor + timedelta(days=9))}
    state = ProjectState(project, release, members)
    owners = ["u_marcos", "u_irene", "u_laura"]
    baseline_at = anchor - timedelta(days=26)
    for index, (component, title_en, title_es, desc_en, desc_es) in enumerate(ACME_REQUIREMENTS, 1):
        human_id = f"REQ-{index:03d}"
        title = L(title_en, title_es)
        scope = "pending" if index in ACME_SCOPE["pending"] else "out_of_scope" if index in ACME_SCOPE["out_of_scope"] else "agreed"
        verification = next((key for key, ids in ACME_VERIFICATION.items() if index in ids), "passed")
        if human_id in ACME_EXPLICIT_CRITERIA:
            criteria = _explicit_criteria(ACME_PROJECT_ID, human_id, ACME_EXPLICIT_CRITERIA[human_id])
        else:
            criteria = _criteria(ACME_PROJECT_ID, human_id, title, component, 2 + index % 3)
        priority = "high" if component == "Security" or index % 4 == 0 or human_id in {"REQ-023", "REQ-041"} else "low" if index % 5 == 0 else "medium"
        state.requirements.append({
            "uuid": stable_uuid(ACME_PROJECT_ID, human_id), "id": human_id, "title": title, "description": L(desc_en, desc_es), "component": component,
            "type": "functional", "priority": priority, "owner_id": owners[index % 3], "scope_status": scope, "verification": verification,
            "acceptance": "accepted" if index in ACME_ACCEPTED else "pending", "defect": verification == "failed", "criteria": criteria,
            "verification_plan": None, "baseline": "BR-1.4", "version": "v1.2" if human_id == "REQ-041" else "v1.0",
            "created_at": iso(baseline_at - timedelta(days=8)), "agreed_at": iso(baseline_at) if scope == "agreed" else None,
        })
    with_evidence = [item for item in state.requirements if item["verification"] in {"passed", "failed"} or int(item["id"][4:]) in ACME_PARTIAL_EVIDENCE]
    first = [item for item in with_evidence if item["verification"] == "passed"][:ACME_RUN_CHUNKS[0]]
    rest = [item for item in with_evidence if item not in first]
    _seed_runs(state, anchor, ACME_RUN_DAYS, ACME_RUN_CHUNKS, first + rest, "u_irene")
    state.scope_versions = [
        {"version": "BR-1.3", "status": "superseded", "source": "Acme Client Portal Agreement", "summary": L("Initial baseline with 78 requirements.", "Línea base inicial con 78 requisitos."), "created_at": iso(anchor - timedelta(days=40)), "created_by": "u_laura", "diff": None},
        {"version": "BR-1.4", "status": "approved", "source": "Acme Client Portal Agreement", "summary": L("Frozen baseline for Release 2.3.", "Línea base congelada para la release 2.3."), "created_at": iso(baseline_at), "created_by": "u_laura", "diff": None},
    ]
    state.events.append({"event": "scope_approved", "actor_id": "u_laura", "created_at": iso(baseline_at), "params": {"version": "BR-1.4"}, "ref": {"type": "scope_version", "id": "BR-1.4", "label": "BR-1.4"}})
    _seed_changes(state, anchor, ACME_CHANGES)
    _seed_comments(state, anchor, ACME_COMMENTS)
    return state


def _northstar(anchor: datetime) -> ProjectState:
    members = [
        _member("u_demo", "Demo Owner", "owner", "owner@demo.sda"),
        _member("u_priya", "Priya Nair", "delivery_lead", "priya.nair@signoff.example"),
        _member("u_jon", "Jon Arribas", "qa", "jon.arribas@signoff.example"),
        _member("u_hana", "Hana Kowalski", "client_reviewer", "client@northstar.example"),
    ]
    created = anchor - timedelta(days=14)
    project = {"id": CUSTOMER_PROJECT_ID, "organization_id": ORG_ID, "slug": "customer-operations", "name": "Customer Operations Portal v1", "client": "Northstar Logistics", "description": L("Functional end-to-end demo with Change Radar and File Inspector.", "Demo funcional de punta a punta con Change Radar y File Inspector."), "review_token": "demo-review-token"}
    release = {"id": CUSTOMER_RELEASE_ID, "name": "Release 1.0", "version": "1.0.0", "status": "in_signoff", "created_at": iso(created), "target_date": iso(anchor + timedelta(days=6))}
    state = ProjectState(project, release, members)
    owners = ["u_priya", "u_jon", "u_demo"]
    baseline_at = anchor - timedelta(days=13)
    verification = {7: "in_progress", 10: "failed", 11: "not_started"}
    for index, (component, priority, title_en, title_es, desc_en, desc_es) in enumerate(NORTHSTAR_REQUIREMENTS, 1):
        human_id = f"REQ-{index:03d}"
        criteria = [{"id": stable_uuid(CUSTOMER_PROJECT_ID, human_id, "criterion", str(n)), "text": L(t["en"].format(en=title_en.lower()), t["es"].format(es=title_es)), "source": "baseline"} for n, t in enumerate(NORTHSTAR_CRITERIA, 1)]
        status = verification.get(index, "passed")
        scope = "pending" if index == 11 else "agreed"
        state.requirements.append({
            "uuid": stable_uuid(CUSTOMER_PROJECT_ID, human_id), "id": human_id, "title": L(title_en, title_es), "description": L(desc_en, desc_es), "component": component,
            "type": "non_functional" if component == "Non-functional" else "functional", "priority": priority, "owner_id": owners[index % 3], "scope_status": scope,
            "verification": status, "acceptance": "accepted" if index <= 8 and status == "passed" else "pending", "defect": status == "failed", "criteria": criteria,
            "verification_plan": None, "baseline": "v1", "version": "v1.0", "created_at": iso(baseline_at - timedelta(days=3)), "agreed_at": iso(baseline_at) if scope == "agreed" else None,
        })
    ordered = [item for item in state.requirements if item["verification"] != "not_started"]
    _seed_runs(state, anchor, [10, 8, 6, 4, 2, 0.25], [4, 2, 2, 1, 1, 1], ordered, "u_jon")
    # Keep the historical artifact name of the first login observation.
    login = next(item for item in state.evidence if item["requirement_id"] == "REQ-001")
    login.update({"artifact": "login-success.png", "storage_key": "login-success.png", "summary": L("Login completed and dashboard loaded with the expected account context.", "El inicio de sesión se completó y el panel cargó con el contexto de cuenta esperado.")})
    state.scope_versions = [{"version": "v1", "status": "approved", "source": "Customer Operations Portal SOW", "summary": L("Approved baseline with 12 requirements.", "Línea base aprobada con 12 requisitos."), "created_at": iso(baseline_at), "created_by": "u_demo", "diff": None}]
    state.events.append({"event": "scope_approved", "actor_id": "u_demo", "created_at": iso(baseline_at), "params": {"version": "v1"}, "ref": {"type": "scope_version", "id": "v1", "label": "v1"}})
    _seed_changes(state, anchor, [
        {"n": 1, "title": L("Add warehouse manager role", "Añadir el rol de responsable de almacén"), "original": L("Two roles: operator and manager.", "Dos roles: operador y responsable."), "proposed": L("Warehouse managers need a separate view with bulk actions.", "Los responsables de almacén necesitan una vista propia con acciones masivas."), "classification": "possible_scope_change", "status": "proposed", "impact": "High", "reqs": [2, 11], "source": "client", "days": 3, "decider": None},
        {"n": 2, "title": L("Add export timestamp", "Añadir la fecha de generación a la exportación"), "original": L("CSV export includes filtered order data.", "La exportación CSV incluye los pedidos filtrados."), "proposed": L("Add a time-zone-aware generated-at timestamp to exports.", "Añadir a las exportaciones la fecha de generación con zona horaria."), "classification": "clarification", "status": "approved", "impact": "Low", "reqs": [6], "source": "client", "days": 7, "decider": "u_demo"},
        {"n": 3, "title": L("Dark theme for the operations dashboard", "Tema oscuro para el panel de operaciones"), "original": L("The portal ships with the corporate light theme.", "El portal se entrega con el tema claro corporativo."), "proposed": L("Add a dark theme for night shifts.", "Añadir un tema oscuro para los turnos de noche."), "classification": "possible_scope_change", "status": "rejected", "impact": "Medium", "reqs": [], "source": "client", "days": 5, "decider": "u_demo"},
    ])
    _seed_comments(state, anchor, [
        {"req": 1, "author": "u_priya", "text": L("Login works with the client's test accounts.", "El inicio de sesión funciona con las cuentas de prueba del cliente."), "hours": 200, "resolved": True},
        {"req": 7, "author": "u_hana", "text": L("Please confirm the delivery timing for email alerts.", "Confirmad el horario de envío de las alertas por correo."), "hours": 18, "resolved": False},
    ])
    return state


def seed_projects(anchor: datetime | None = None) -> dict[str, ProjectState]:
    anchor = (anchor or datetime.now(timezone.utc)).replace(microsecond=0)
    return {ACME_PROJECT_ID: _acme(anchor), CUSTOMER_PROJECT_ID: _northstar(anchor)}
