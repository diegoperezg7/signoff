'use client';

import { use, useState } from 'react';
import { CheckCircle2, CircleAlert, MessageSquare, ShieldCheck, TriangleAlert } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import '../../globals.css';
import { BrandLockup } from '../../../components/brand-lockup';
import { useAppPreferences } from '../../../components/app-providers';

const API = process.env.NEXT_PUBLIC_SDA_API_URL || process.env.SDA_API_URL || 'http://127.0.0.1:8000';

type PackEvidence = { id: string; artifact: string; summary: string; state?: string };
type DeliveryPack = {
  project?: { name?: string; client?: string; release?: string };
  release?: string;
  story: { promised: string; delivered: string; changed: string; remaining: string };
  evidence: PackEvidence[];
};

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`Signoff API request failed (${response.status})`);
  return response.json() as Promise<T>;
}

export default function ReviewPage({ params }: { params: Promise<{ token: string }> }) {
  const { locale, resolvedTheme } = useAppPreferences();
  const { token } = use(params);
  const [message, setMessage] = useState('');
  const [sent, setSent] = useState(false);
  const [actionError, setActionError] = useState('');
  const reviewQuery = useQuery({
    queryKey: ['review-pack', token],
    queryFn: () => fetchJson<DeliveryPack>(`${API}/api/v1/review/${token}`),
    retry: 1,
  });
  const pack = reviewQuery.data ?? null;
  const error = actionError || (reviewQuery.error ? (locale === 'es' ? 'El delivery pack no está disponible.' : 'The delivery pack is unavailable.') : '');

  async function submit(decision: 'accepted' | 'rejected' | 'revision_requested') {
    try {
      await fetchJson(`${API}/api/v1/review/${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision, comment: message }),
      });
      setSent(true);
    } catch {
      setActionError(locale === 'es' ? 'No se ha podido registrar tu revisión. Inténtalo de nuevo.' : 'Your review could not be recorded. Please try again.');
    }
  }

  if (error && !pack) return <main className={`landing review-page reference-${resolvedTheme}`}><div className="eyebrow">{locale === 'es' ? 'PORTAL DE REVISIÓN' : 'CLIENT REVIEW PORTAL'}</div><h1>{locale === 'es' ? 'Delivery pack no disponible' : 'Delivery pack unavailable'}</h1><p className="lede">{error}</p></main>;
  if (reviewQuery.isPending || !pack) return <main className={`landing review-page reference-${resolvedTheme}`}><div className="eyebrow">{locale === 'es' ? 'PORTAL DE REVISIÓN' : 'CLIENT REVIEW PORTAL'}</div><h1>{locale === 'es' ? 'Cargando delivery pack…' : 'Loading delivery pack…'}</h1></main>;

  return <main className={`landing review-page reference-${resolvedTheme}`}>
    <div className="review-brand"><BrandLockup compact /><span>Signoff</span></div>
    <div className="eyebrow">{locale === 'es' ? `PORTAL DE REVISIÓN · ${pack.release || 'RELEASE'}` : `CLIENT REVIEW PORTAL · ${pack.release || 'RELEASE'}`}</div>
    <h1>{pack.story.promised}</h1>
    <p className="lede">{locale === 'es' ? `Un resumen transparente preparado para ${pack.project?.client || 'tu cliente'}. Revisa la evidencia y registra tu decisión.` : `A transparent delivery summary prepared for ${pack.project?.client || 'your client'}. Review the evidence and record your decision.`}</p>
    <div className="review-summary"><div><small>{locale === 'es' ? 'ENTREGADO' : 'DELIVERED'}</small><strong>{pack.story.delivered}</strong></div><div><small>{locale === 'es' ? 'CAMBIOS DE ALCANCE' : 'SCOPE CHANGES'}</small><strong>{pack.story.changed}</strong></div><div><small>{locale === 'es' ? 'PENDIENTES' : 'OPEN ITEMS'}</small><strong>{pack.story.remaining}</strong></div></div>
    <section className="panel review-panel"><div className="panel-title"><div><span className="eyebrow">{locale === 'es' ? 'ÍNDICE DE EVIDENCIA' : 'EVIDENCE INDEX'}</span><h3>{locale === 'es' ? 'Estado de la evidencia' : 'Evidence status'}</h3></div><ShieldCheck className="muted"/></div>{pack.evidence.map(e => { const state = e.state || 'demonstrated'; const demonstrated = state === 'demonstrated'; const partial = state === 'partially_demonstrated'; const StateIcon = demonstrated ? CheckCircle2 : partial ? TriangleAlert : CircleAlert; return <div className="evidence-row" key={e.id}><div className={`evidence-thumb evidence-${demonstrated ? 'good' : partial ? 'warn' : 'bad'}`}><StateIcon size={20}/></div><div><strong>{e.artifact}</strong><small>{e.summary}</small></div><span className={`state ${demonstrated ? 'good' : partial ? 'warn' : 'bad'}`}>{locale === 'es' ? (demonstrated ? 'Superado' : partial ? 'Parcial' : 'Sin demostrar') : (demonstrated ? 'Demonstrated' : partial ? 'Partial' : 'Not demonstrated')}</span></div>})}</section>
    <section className="review-actions">
      <div><MessageSquare size={18}/><div><strong>{locale === 'es' ? 'Registra tu revisión' : 'Record your review'}</strong><small>{sent ? (locale === 'es' ? 'Tu decisión se ha registrado en el audit log.' : 'Your decision has been recorded in the audit log.') : (locale === 'es' ? 'Acepta la entrega, solicita cambios o recházala.' : 'Accept the release, request changes or reject it.')}</small></div></div>
      {!sent && <textarea aria-label={locale === 'es' ? 'Comentario de revisión' : 'Review comment'} placeholder={locale === 'es' ? 'Añade un comentario (opcional)' : 'Add a comment (optional)'} value={message} onChange={event => setMessage(event.target.value)} />}
      {sent ? <span className="state good">{locale === 'es' ? 'Decisión registrada' : 'Decision recorded'}</span> : <div className="review-buttons"><button className="button ghost" onClick={() => submit('revision_requested')}>{locale === 'es' ? 'Solicitar revisión' : 'Request revision'}</button><button className="button primary" onClick={() => submit('accepted')}>{locale === 'es' ? 'Aceptar entrega' : 'Accept delivery'}</button></div>}
      {error && <small className="notice">{error}</small>}
    </section>
  </main>;
}
