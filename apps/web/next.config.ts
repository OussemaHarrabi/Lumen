import type { NextConfig } from "next";

// The API keeps its session in an httpOnly cookie and its images are read back
// pixel by pixel on a canvas: both need a same-origin path from the browser.
// Everything under /lum-api is proxied to the FastAPI app.
const apiOrigin = process.env.NEXT_PUBLIC_API_URL ?? "";

const nextConfig: NextConfig = {
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
  async rewrites() {
    if (!apiOrigin) return [];
    return [
      {
        source: "/lum-api/:path*",
        destination: `${apiOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
