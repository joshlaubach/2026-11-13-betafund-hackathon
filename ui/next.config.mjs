/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Self-contained server bundle for the page image (ui/Dockerfile runs node server.js).
  output: "standalone",
  // The Python server is a separate process; the page calls it directly (CORS allows localhost:3000).
};
export default nextConfig;
