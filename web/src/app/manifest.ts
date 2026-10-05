import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: '/',
    name: 'KIRRO',
    short_name: 'KIRRO',
    description:
      'KIRRO books scarce slots: courts, screenings, passes. Popular slots get a fair pick; the rest you can just buy, first come, first served.',
    lang: 'en',
    categories: ['shopping', 'sports', 'entertainment'],
    start_url: '/',
    scope: '/',
    display: 'standalone',
    background_color: '#0a0a0a',
    theme_color: '#0a0a0a',
    icons: [
      { src: '/kirro-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/kirro-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
      // Android adaptive-icon safe zone (glyph inside the inner ~80% circle, asset generated from
      // the same artwork via `magick kirro-512.png -resize 70% -background "#0a0a0a" -gravity
      // center -extent 512x512`, so the mask never clips the sound-wave glyph).
      { src: '/kirro-192-maskable.png', sizes: '192x192', type: 'image/png', purpose: 'maskable' },
      { src: '/kirro-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
    ],
  };
}
