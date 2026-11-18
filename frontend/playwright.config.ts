import { defineConfig, devices } from "@playwright/test";

// Smoke tests run against an isolated stack:
//   backend  → 127.0.0.1:8001 with a freshly reset "<db>_e2e" database
//   frontend → 127.0.0.1:3001 pointed at that backend
// PostgreSQL (docker compose) must already be running.
const API_URL = "http://127.0.0.1:8001/api/v1";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  reporter: [["list"]],
  timeout: 60_000,
  use: {
    baseURL: "http://127.0.0.1:3001",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, grep: /@mobile/ },
  ],
  webServer: [
    {
      command: "../backend/scripts/run_e2e_server.sh",
      url: `${API_URL}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "npx next dev -H 127.0.0.1 -p 3001",
      url: "http://127.0.0.1:3001",
      env: { NEXT_PUBLIC_API_BASE_URL: API_URL, NEXT_DIST_DIR: ".next-e2e" },
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});
