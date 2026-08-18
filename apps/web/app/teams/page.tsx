import { Suspense } from 'react';
import { ReferenceDashboard } from '../../components/dashboard/reference-dashboard';

export default function TeamsPage() {
  return <Suspense fallback={<div /> }><ReferenceDashboard /></Suspense>;
}
