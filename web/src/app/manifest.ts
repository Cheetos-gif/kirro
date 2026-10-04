import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'KIRRO',
    short_name: 'KIRRO',
    description:
      'KIRRO books scarce slots: courts, screenings, passes. Popular slots get a fair pick; the rest you can just buy, first come, first served.',
    start_url: '/',
    display: 'standalone',
    background_color: '#0a0a0a',
    theme_color: '#0a0a0a',
    icons: [
      { src: '/kirro-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/kirro-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
    ],
  };
}
