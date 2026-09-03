import { defineConfig, devices } from "@playwright/test";


export default defineConfig({
  testDir: "./specs",
  fullyParallel: true,
  forbidOnly: true,
  retries: 1,
  reporter: "line",
  use: {
    baseURL: process.env.FRONTEND_URL,
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
