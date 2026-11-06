'use client';

// Signoff mark: two interlocking shards on a rounded tile. Colors come from
// --brand-tile / --brand-shard so the mark inverts between light and dark.
export function BrandMark({ size = 28 }: { size?: number }) {
  return (
    <svg className="brand-mark-svg" width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <rect width="64" height="64" rx="16" fill="var(--brand-tile)" />
      <path d="M18 18h23L26 33H14c-3.2 0-4.8-3.9-2.5-6.2l6.5-6.6A6 6 0 0 1 22.2 18Z" fill="var(--brand-shard)" />
      <path d="M46 46H23l15-15h12c3.2 0 4.8 3.9 2.5 6.2l-6.5 6.6A6 6 0 0 1 46 46Z" fill="var(--brand-shard)" />
    </svg>
  );
}

export function BrandLockup({ compact = false }: { compact?: boolean; priority?: boolean }) {
  return (
    <span className={compact ? 'brand-lockup-frame brand-lockup-frame-compact' : 'brand-lockup-frame'} role="img" aria-label="Signoff">
      <BrandMark size={compact ? 28 : 32} />
      <span className="brand-wordmark" aria-hidden="true">signoff</span>
    </span>
  );
}
