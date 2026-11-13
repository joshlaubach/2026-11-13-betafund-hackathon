/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The Python server is a separate process; the page calls it directly (CORS allows localhost:3000).
};
export default nextConfig;
