import { Suspense } from 'react';
import { ReferenceDashboard } from '../../components/dashboard/reference-dashboard';

export default function ProjectsPage() {
  return <Suspense fallback={<div /> }><ReferenceDashboard /></Suspense>;
}
