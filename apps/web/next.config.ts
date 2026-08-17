import type { NextConfig } from "next";

// Docker needs the standalone server bundle. Vercel performs its own output
// tracing and packaging, so asking Next.js for both formats can leave Vercel
// looking for a trace file that has already been moved into the standalone tree.
const nextConfig: NextConfig = process.env.VERCEL
  ? {}
  : { output: "standalone" };

export default nextConfig;
