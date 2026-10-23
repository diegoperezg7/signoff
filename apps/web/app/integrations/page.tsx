import { Suspense } from 'react';
import { ReferenceDashboard } from '../../components/dashboard/reference-dashboard';

export default function IntegrationsPage() {
  return <Suspense fallback={<div /> }><ReferenceDashboard /></Suspense>;
}
