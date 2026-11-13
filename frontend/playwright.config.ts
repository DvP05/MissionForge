import { defineConfig, devices } from "@playwright/test";

const FRONTEND_URL = "http://localhost:3000";
const BACKEND_URL = "http://127.0.0.1:8000";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: FRONTEND_URL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      // PW_CHANNEL=chrome|msedge uses an installed browser when the bundled
      // Chromium binary cannot be launched on this machine.
      use: { ...devices["Desktop Chrome"], channel: process.env.PW_CHANNEL || undefined },
    },
  ],
  webServer: [
    {
      command: "uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
      cwd: "../backend",
      url: `${BACKEND_URL}/api/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "corepack pnpm@10.18.3 dev --port 3000",
      url: FRONTEND_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 180_000,
      env: { NEXT_PUBLIC_API_BASE_URL: BACKEND_URL },
    },
  ],
});
