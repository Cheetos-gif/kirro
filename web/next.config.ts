import './src/env';

import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  reactCompiler: true,
  // Emits `.next/standalone` — a server bundle with only the traced runtime dependencies, which is
  // what web/Dockerfile's runtime stage copies. Vercel ignores it; it is for the local
  // docker-compose image (ADR-021).
  output: 'standalone',
};

export default nextConfig;
