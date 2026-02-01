/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // API proxy to Memoria backend
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8765/api/:path*',
      },
    ];
  },
};

module.exports = nextConfig;
