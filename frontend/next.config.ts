import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      { source: "/attempts", destination: "/exams", permanent: false },
      { source: "/imports", destination: "/exams?tab=drafts", permanent: false },
      { source: "/reviews", destination: "/exams", permanent: false },
      { source: "/mistakes", destination: "/analytics/jlpt?tab=mistakes", permanent: false },
    ];
  },
  // Playwright runs its own dev server in a separate build directory so it can run
  // alongside `npm run dev` (Next refuses two dev servers sharing one directory).
  distDir: process.env.NEXT_DIST_DIR || ".next",
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
