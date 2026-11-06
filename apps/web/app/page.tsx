import { redirect } from 'next/navigation';

// No public landing: the root opens the workspace directly.
export default function Home() {
  redirect('/dashboard');
}
