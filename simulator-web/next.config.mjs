/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export: no API routes, middleware or server actions. Reads only the REST API in contract/openapi.yaml.
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
  // lib/api.ts imports ../../contract/fixtures/*.json in mock mode (outside web/).
  experimental: { externalDir: true },
};

export default nextConfig;
