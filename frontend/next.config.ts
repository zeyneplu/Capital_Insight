import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The Docker image sets NEXT_OUTPUT=standalone for a minimal server.js bundle;
  // local builds are unchanged (standalone symlinks need extra privileges on Windows).
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  // Dev server only: let Cloudflare quick tunnels (cloudflared tunnel --url ...) load dev assets.
  allowedDevOrigins: ["*.trycloudflare.com"],
  // Production-like demo: no Next.js development badge, even under `next dev`.
  devIndicators: false,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
