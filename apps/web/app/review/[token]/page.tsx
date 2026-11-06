'use client';

import { use, useState } from 'react';
import { CheckCircle2, CircleAlert, MessageSquare, ShieldCheck, TriangleAlert } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import '../../globals.css';
import { BrandLockup } from '../../../components/brand-lockup';
import { formatDate, label, releaseTone, useCopy } from '../../../components/dashboard/copy';
import { api, keys } from '../../../lib/api';

type Decision = 'accepted' | 'rejected' | 'revision_requested';

export default function ReviewPage({ params }: { params: Promise<{ token: string }> }) {
  const { c, locale, resolvedTheme } = useCopy();
  const { token } = use(params);
  const queryClient = useQueryClient();
  const [message, setMessage] = useState('');
  const review = useQuery({ queryKey: keys.review(token, locale), queryFn: () => api.review(token, locale), retry: 1 });
  const submit = useMutation({
    mutationFn: (decision: Decision) => api.submitReview(token, decision, message),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['review', token] }),
  });
  const pack = review.data;

  if (review.isError && !pack) {
    return (
      <main className={`landing review-page reference-${resolvedTheme}`}>
        <div className="eyebrow">{c.portal}</div>
        <h1>{c.packUnavailable}</h1>
        <p className="lede">{c.packUnavailableBody}</p>
      </main>
    );
  }
  if (!pack) {
    return (
      <main className={`landing review-page reference-${resolvedTheme}`}>
        <div className="eyebrow">{c.portal}</div>
        <h1>{c.loadingPack}</h1>
      </main>
    );
  }

  const decision = pack.decision;
  const statusTone = releaseTone[pack.release_status] || 'neutral';
  const stateClass = (tone: string) => (tone === 'success' ? 'good' : tone === 'error' ? 'bad' : 'warn');

  return (
    <main className={`landing review-page reference-${resolvedTheme}`}>
      <div className="review-brand">
        <BrandLockup compact />
      </div>
      <div className="eyebrow">
        {c.portal} · {pack.project.release}
      </div>
      <h1>{pack.story.promised}</h1>
      <p className="lede">{c.summaryFor(pack.project.client.replace(/\.+$/, ''))}</p>
      <div className="review-status-line">
        <small>{c.releaseStatusLabel}</small>
        <span className={`state ${stateClass(statusTone)}`}>{label(c.release, pack.release_status)}</span>
      </div>
      <div className="review-summary">
        <div>
          <small>{c.delivered}</small>
          <strong>{pack.story.delivered}</strong>
        </div>
        <div>
          <small>{c.scopeChanges}</small>
          <strong>{pack.story.changed}</strong>
        </div>
        <div>
          <small>{c.openItems}</small>
          <strong>{pack.story.remaining}</strong>
        </div>
      </div>
      <section className="panel review-panel">
        <div className="panel-title">
          <div>
            <span className="eyebrow">{c.evidenceIndex}</span>
            <h3>{c.evidenceStatus}</h3>
          </div>
          <ShieldCheck className="muted" />
        </div>
        {pack.evidence.map((item) => {
          const demonstrated = item.state === 'demonstrated';
          const partial = item.state === 'partially_demonstrated';
          const StateIcon = demonstrated ? CheckCircle2 : partial ? TriangleAlert : CircleAlert;
          const tone = demonstrated ? 'good' : partial ? 'warn' : 'bad';
          return (
            <div className="evidence-row" key={item.id}>
              <div className={`evidence-thumb evidence-${tone}`}>
                <StateIcon size={20} />
              </div>
              <div>
                <strong>
                  {item.requirement_id} · {item.artifact}
                </strong>
                <small>{item.summary}</small>
              </div>
              <span className={`state ${tone}`}>{label(c.evidenceState, item.state)}</span>
            </div>
          );
        })}
      </section>
      <section className="review-actions">
        <div>
          <MessageSquare size={18} />
          <div>
            <strong>{c.recordReview}</strong>
            <small>
              {decision
                ? `${label(c.acceptance, decision.decision)} · ${c.decisionOn(formatDate(decision.at, locale))}${decision.comment ? ` · "${decision.comment}"` : ''}`
                : c.recordHint}
            </small>
          </div>
        </div>
        <textarea
          aria-label={c.reviewComment}
          placeholder={c.reviewPlaceholder}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
        />
        <div className="review-buttons">
          <button className="button ghost review-reject" disabled={submit.isPending} onClick={() => submit.mutate('rejected')}>
            {c.rejectDelivery}
          </button>
          <button className="button ghost" disabled={submit.isPending} onClick={() => submit.mutate('revision_requested')}>
            {c.requestRevision}
          </button>
          <button className="button primary" disabled={submit.isPending} onClick={() => submit.mutate('accepted')}>
            {c.acceptDelivery}
          </button>
        </div>
        {submit.isSuccess && <span className="state good">{c.decisionRecorded}</span>}
        {submit.isError && <small className="notice">{c.reviewFailed}</small>}
      </section>
    </main>
  );
}
