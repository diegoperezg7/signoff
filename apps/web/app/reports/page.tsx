import { Suspense } from 'react';
import { ReferenceDashboard } from '../../components/dashboard/reference-dashboard';

export default function ReportsPage() {
  return <Suspense fallback={<div /> }><ReferenceDashboard /></Suspense>;
}
