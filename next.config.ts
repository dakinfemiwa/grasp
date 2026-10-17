import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A stray package-lock.json in the user home dir confuses root detection.
  turbopack: { root: __dirname },
};

export default nextConfig;
