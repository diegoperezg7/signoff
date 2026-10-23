import { Suspense } from 'react';
import { ReferenceDashboard } from '../../components/dashboard/reference-dashboard';

export default function BaselinesPage() {
  return <Suspense fallback={<div /> }><ReferenceDashboard /></Suspense>;
}
