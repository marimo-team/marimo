/* Copyright 2026 Marimo. All rights reserved. */

import type { PlaywrightTestConfig } from "@playwright/test";
import { devices } from "@playwright/test";

const config: PlaywrightTestConfig = {
  testDir: ".",
  testMatch: "visual-regression.spec.ts",
  outputDir: "../test-results/visual-regression",
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  fullyParallel: false,
  forbidOnly: true,
  workers: 1,
  reporter: "html",
  use: {
    actionTimeout: 5_000,
    navigationTimeout: 10_000,
    screenshot: "only-on-failure",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 720 },
      },
    },
  ],
  webServer: [
    {
      command: "node playwright-container-proxy.cjs 2718 2738",
      url: "http://127.0.0.1:2718",
      reuseExistingServer: true,
    },
    {
      command: "node playwright-container-proxy.cjs 2725 2739",
      url: "http://127.0.0.1:2725",
      reuseExistingServer: true,
    },
  ],
};

export default config;
