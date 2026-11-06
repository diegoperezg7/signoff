"use client";

import { useRef, useState, type FormEvent, type ReactNode } from "react";
import { CheckCircle2, CircleAlert, FileStack, RefreshCw, Upload } from "lucide-react";
import { api, type Actor, type FileInspection, type Tone } from "../../lib/api";
import { useProjectMutation } from "../../lib/queries";
import { label, pillClass, toneClass, useCopy } from "./copy";

export function Avatar({ actor, size = "md" }: { actor?: Pick<Actor, "initials" | "kind" | "name">; size?: "sm" | "md" }) {
  const initials = actor?.initials || (actor?.name || "?").slice(0, 2).toUpperCase();
  return (
    <span className={`reference-avatar avatar-${actor?.kind || "member"} avatar-${size}`} aria-hidden="true">
      <span>{initials}</span>
    </span>
  );
}

export function Pill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={pillClass(tone)}>{children}</span>;
}

export function StatusText({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className="reference-verification-status">
      <span className={`status-dot ${toneClass[tone]}`} />
      {children}
    </span>
  );
}

export function Spinner({ size = 14 }: { size?: number }) {
  return <RefreshCw size={size} className="reference-spin" aria-hidden="true" />;
}

/** Uploads a file as evidence for a requirement; CSVs come back with the file inspector's verdict. */
export function EvidenceUpload({
  projectId,
  requirementIds,
  defaultRequirementId,
  notify,
  compact = false,
}: {
  projectId: string;
  requirementIds: string[];
  defaultRequirementId: string | null;
  notify: (message: string) => void;
  compact?: boolean;
}) {
  const { c } = useCopy();
  const [file, setFile] = useState<File | null>(null);
  const [requirementId, setRequirementId] = useState(defaultRequirementId || requirementIds[0] || "");
  const [description, setDescription] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const upload = useProjectMutation(projectId, (vars: { file: File; requirementId: string; description: string }) =>
    api.uploadEvidence(projectId, vars),
  );
  const target = requirementIds.includes(requirementId) ? requirementId : defaultRequirementId || requirementIds[0] || "";

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !target) return;
    upload.mutate(
      { file, requirementId: target, description },
      {
        onSuccess: () => {
          notify(c.evidenceUploaded);
          setFile(null);
          setDescription("");
          if (input.current) input.current.value = "";
        },
        onError: () => notify(c.evidenceFailed),
      },
    );
  }

  return (
    <form className={`signoff-upload${compact ? " is-compact" : ""}`} onSubmit={submit}>
      <label className="reference-file-picker">
        <FileStack size={15} />
        <span>{file ? file.name : c.chooseFile}</span>
        <input ref={input} type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} />
      </label>
      {!compact && (
        <label className="signoff-field">
          <span>{c.forRequirement}</span>
          <select value={target} onChange={(event) => setRequirementId(event.target.value)}>
            {requirementIds.map((id) => (
              <option key={id} value={id}>
                {id}
              </option>
            ))}
          </select>
        </label>
      )}
      <label className="signoff-field signoff-field-grow">
        <span>{c.descriptionLabel}</span>
        <input
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder={c.descriptionPlaceholder}
        />
      </label>
      <button className="reference-secondary-button" type="submit" disabled={!file || !target || upload.isPending}>
        {upload.isPending ? <Spinner /> : <Upload size={14} />}
        {upload.isPending ? c.uploading : c.uploadEvidence}
      </button>
      {upload.data?.inspection && <InspectionResult inspection={upload.data.inspection} />}
    </form>
  );
}

export function InspectionResult({ inspection }: { inspection: FileInspection }) {
  const { c } = useCopy();
  const ok = inspection.assessment === "demonstrated" || (inspection.valid !== false && !inspection.assessment);
  const failedChecks = Object.entries(inspection.checks || {}).filter(([, passed]) => !passed);
  return (
    <div className={`reference-inspection-result signoff-inspection${ok ? "" : " is-warning"}`}>
      {ok ? <CheckCircle2 size={15} /> : <CircleAlert size={15} />}
      <span>
        <strong>{c.inspection}</strong>
        {inspection.assessment && (
          <Pill tone={ok ? "success" : "warning"}>{label(c.evidenceState, inspection.assessment)}</Pill>
        )}
        {typeof inspection.row_count === "number" && <small>{c.rows(inspection.row_count)}</small>}
        {inspection.columns?.length ? (
          <small>
            {c.columns}: {inspection.columns.join(", ")}
          </small>
        ) : null}
        {failedChecks.length > 0 && <small>{failedChecks.map(([key]) => key.replaceAll("_", " ")).join(" · ")}</small>}
      </span>
    </div>
  );
}

export function downloadJson(filename: string, payload: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
