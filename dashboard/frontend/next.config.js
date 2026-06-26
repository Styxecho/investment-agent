/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8742/api/:path*',
      },
    ]
  },
  images: {
    unoptimized: true,
  },
}

module.exports = nextConfig
