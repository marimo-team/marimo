/* Copyright 2024 Marimo. All rights reserved. */
import type { PlaywrightTestConfig } from "@playwright/test";
import { devices } from "@playwright/test";
import path from "node:path";
import { exec } from "node:child_process";

export interface ServerOptions {
  command: "edit" | "run";
  port: number;
  baseUrl?: string | undefined;
}

// Read environment variables from file. See https://github.com/motdotla/dotenv
// require('dotenv').config();

// Location of python files needed for testing
const pydir = path.join("e2e-tests", "py");

// Mapping from Python app name to { browserName => port } object.
//
// Each app is served by a different server.
let _port = 2718;
function port(): number {
  return _port++;
}

const appToOptions = {
  "title.py": { port: port(), command: "edit" },
  "streams.py": { port: port(), command: "edit" },
  "bad_button.py": { port: port(), command: "edit" },
  "shutdown.py": { port: port(), command: "edit" },
  "components.py": { port: port(), command: "run" },
  "cells.py": { port: port(), command: "edit" },
  "bugs.py": { port: port(), command: "edit" },
  "layout_grid.py//edit": { port: port(), command: "edit" },
  "layout_grid.py//run": { port: port(), command: "run" },
  "layout_grid_max_width.py//run": { port: port(), command: "run" },
  "output.py//run": {
    port: port(),
    command: "run",
    baseUrl: "/foo",
  },
  "kitchen_sink.py//edit": { port: port(), command: "edit" },
  "stdin.py//edit": { port: port(), command: "edit" },
} satisfies Record<string, ServerOptions>;

export type ApplicationNames = keyof typeof appToOptions;

function getUrl(port: number, baseUrl = ""): string {
  return `http://127.0.0.1:${port}${baseUrl}`;
}

// For tests to lookup their url/server
export function getAppUrl(app: ApplicationNames): string {
  const options: ServerOptions = appToOptions[app];
  return getUrl(options.port, options.baseUrl);
}

// Reset file via git checkout
export async function resetFile(app: ApplicationNames): Promise<void> {
  const pathToApp = path.join(pydir, app);
  const cmd = `git checkout -- ${pathToApp}`;
  await exec(cmd);
  return;
}

// Start marimo server for the given app
export function startServer(app: ApplicationNames): void {
  const { command, port } = appToOptions[app];
  const pathToApp = path.join(pydir, app);
  const marimoCmd = `marimo -q ${command} ${pathToApp} -p ${port} --headless`;
  exec(marimoCmd);
}

// See https://playwright.dev/docs/test-configuration.
const config: PlaywrightTestConfig = {
  testDir: "./e2e-tests",
  // Maximum time one test can run for
  timeout: 30 * 1000,
  expect: {
    // Maximum time expect() should wait for the condition to be met.
    // For example in `await expect(locator).toHaveText();`
    timeout: 5000,
  },
  // Run tests in files in parallel
  fullyParallel: false,
  // Fail the build on CI if you accidentally left test.only in the source
  forbidOnly: !!process.env.CI,
  // Retry on CI only
  retries: process.env.CI ? 2 : 0,
  // Opt out of parallel tests until marimo server can support multiple edit
  // connections.
  workers: 1,
  // Reporter to use. See https://playwright.dev/docs/test-reporters
  reporter: "html",
  // Suppress tests stdout/stderr.
  quiet: true,
  // Shared settings for all the projects below. See
  // https://playwright.dev/docs/api/class-testoptions.
  use: {
    // Max time each action (eg `click()`) can take. Defaults to 0 (no limit).
    actionTimeout: 0,
    // Collect trace when retrying the failed test. See
    // https://playwright.dev/docs/trace-viewer
    trace: "on-first-retry",
  },

  // TODO(akshayka): Consider testing on firefox
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    //    Re-enable later ...
    //    {
    //      name: "webkit",
    //      use: { ...devices["Desktop Safari"] },
    //      testIgnore: [
    //        // This test uses keyboard shortcuts which seem to work locally with webkit, but not on CI
    //        // Disable this test until we can figure out why
    //        "**/cells.spec.ts",
    //      ],
    //    },
    //    {
    //      name: "ios",
    //      use: { ...devices["iPhone 13"] },
    //      // Just run the cells tests for read-only apps
    //      testMatch: ["**/components.spec.ts", "**/mode.spec.ts"],
    //    },
  ],

  // Run marimo servers before starting the tests, one for each app/test
  webServer: Object.entries(appToOptions).map(([app, options]) => {
    app = app.replace("//edit", "").replace("//run", "");

    const { command, port, baseUrl } = options as ServerOptions;
    const pathToApp = path.join(pydir, app);
    let marimoCmd = `marimo -q ${command} ${pathToApp} -p ${port} --headless`;
    if (baseUrl) {
      marimoCmd += ` --base-url=${baseUrl}`;
    }

    return {
      command: marimoCmd,
      url: getUrl(port, baseUrl),
      reuseExistingServer: false,
    };
  }),
};

export default config;
