import type { NextConfig } from 'next';
const nextConfig: NextConfig = {
  output: 'standalone',
  distDir: process.env.NEXT_DIST_DIR || '.next',
  turbopack: { root: process.cwd() },
  agentRules: false,
};
export default nextConfig;
