import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Signoff — Software delivery assurance',
    short_name: 'Signoff',
    description: 'From agreement to acceptance.',
    start_url: '/dashboard',
    display: 'standalone',
    background_color: '#050912',
    theme_color: '#6366F1',
    icons: [
      { src: '/brand/signoff-mark-transparent@2x.png', sizes: '512x512', type: 'image/png' },
    ],
  };
}
