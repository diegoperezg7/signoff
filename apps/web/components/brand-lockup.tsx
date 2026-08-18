'use client';

import Image from 'next/image';
import { useAppPreferences } from './app-providers';

export function BrandLockup({ compact = false, priority = false }: { compact?: boolean; priority?: boolean }) {
  const { resolvedTheme } = useAppPreferences();
  const source = resolvedTheme === 'dark' ? '/brand/signoff-wordmark-dark-transparent.png' : '/brand/signoff-wordmark-light-transparent.png';
  return <Image className={compact ? 'brand-lockup brand-lockup-compact' : 'brand-lockup'} src={source} alt="Signoff" width={compact ? 142 : 420} height={compact ? 52 : 104} priority={priority} />;
}

export function FullBrandLockup({ priority = false }: { priority?: boolean }) {
  const { resolvedTheme } = useAppPreferences();
  const source = resolvedTheme === 'dark' ? '/brand/signoff-lockup-dark-transparent.png' : '/brand/signoff-lockup-light-transparent.png';
  return <Image className="marketing-lockup" src={source} alt="Signoff — Software Delivery Assurance" width={910} height={224} priority={priority} />;
}
