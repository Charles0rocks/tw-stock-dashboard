/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: '/', destination: '/index.html' },
      { source: '/stock-review', destination: '/stock-review.html' },
      { source: '/stock', destination: '/stock-review.html' }
    ];
  }
};
export default nextConfig;
