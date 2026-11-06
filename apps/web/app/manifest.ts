import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Signoff — Software delivery assurance',
    short_name: 'Signoff',
    description: 'From agreement to acceptance.',
    start_url: '/dashboard',
    display: 'standalone',
    background_color: '#000000',
    theme_color: '#000000',
    icons: [
      { src: '/brand/signoff-mark-512.png', sizes: '512x512', type: 'image/png' },
    ],
  };
}
