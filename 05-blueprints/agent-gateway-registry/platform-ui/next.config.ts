import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async headers() {
    return [{ source: "/(.*)", headers: [{ key: "Content-Security-Policy", value: "frame-src 'self' https://cloud.langfuse.com" }] }]
  },
};

export default nextConfig;
