/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  output: 'export',
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || '/api',
  },
  async rewrites() {
    // Only add rewrites if API_GATEWAY_URL is defined
    if (process.env.API_GATEWAY_URL) {
      return [
        {
          source: '/api/:path*',
          destination: `${process.env.API_GATEWAY_URL}/:path*`,
        },
      ];
    }
    return [];
  },
};

module.exports = nextConfig;
