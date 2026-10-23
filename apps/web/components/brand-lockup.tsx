'use client';

import Image from 'next/image';
import { useAppPreferences } from './app-providers';

export function BrandLockup({ compact = false, priority = false }: { compact?: boolean; priority?: boolean }) {
  const { resolvedTheme } = useAppPreferences();
  const source = resolvedTheme === 'dark' ? '/brand/signoff-wordmark-dark-transparent.png' : '/brand/signoff-wordmark-light-transparent.png';
  return <span className={compact ? 'brand-lockup-frame brand-lockup-frame-compact' : 'brand-lockup-frame'} style={{ position: 'relative' }}><Image className={compact ? 'brand-lockup brand-lockup-compact' : 'brand-lockup'} src={source} alt="Signoff" fill sizes={compact ? '172px' : '420px'} priority={priority} /></span>;
}

export function FullBrandLockup({ priority = false }: { priority?: boolean }) {
  const { resolvedTheme } = useAppPreferences();
  const source = resolvedTheme === 'dark' ? '/brand/signoff-lockup-dark-transparent.png' : '/brand/signoff-lockup-light-transparent.png';
  return <Image className="marketing-lockup" src={source} alt="Signoff" width={910} height={224} priority={priority} />;
}
