/* Copyright 2024 Marimo. All rights reserved. */

import { exec } from "node:child_process";
import path from "node:path";
import type { PlaywrightTestConfig } from "@playwright/test";
import { devices } from "@playwright/test";

export type ServerOptions =
  | {
      readonly command: "run";
      readonly port: number;
      readonly baseUrl?: string | undefined;
    }
  | {
      readonly command: "edit";
      /**
       * @default EDIT_PORT (2718)
       */
      readonly port?: number;
    };

// Location of python files needed for testing
const pydir = path.join("e2e-tests", "py");

// Each app is served by a different server.
const EDIT_PORT = 2718;
let _port = 2719;
function port(): number {
  return _port++;
}

// Configuration for each app
const appToOptions = {
  // Edit
  "title.py": { command: "edit" },
  "streams.py": { command: "edit" },
  "bad_button.py": { command: "edit" },
  "bugs.py": { command: "edit" },
  "cells.py": { command: "edit" },
  "disabled_cells.py": { command: "edit" },
  "kitchen_sink.py": { command: "edit" },
  "layout_grid.py": { command: "edit" },
  "stdin.py": { command: "edit" },
  // Custom server for shutdown
  "shutdown.py": { command: "edit", port: port() },
  // Run
  "components.py": { port: port(), command: "run" },
  "layout_grid.py//run": { port: port(), command: "run" },
  "layout_grid_max_width.py//run": { port: port(), command: "run" },
  "output.py//run": {
    port: port(),
    command: "run",
    baseUrl: "/foo",
  },
} satisfies Record<string, ServerOptions>;

export type ApplicationNames = keyof typeof appToOptions;

function getUrl(port: number, baseUrl = "", queryParams = ""): string {
  return `http://127.0.0.1:${port}${baseUrl}${queryParams}`;
}

// For tests to lookup their url/server
export function getAppUrl(app: ApplicationNames): string {
  const options: ServerOptions = appToOptions[app];
  if (!options) {
    throw new Error(`No server options for app: ${app}`);
  }
  if (options.command === "edit") {
    const pathToApp = path.join(pydir, app);
    return getUrl(EDIT_PORT, "", `?file=${pathToApp}`);
  }
  return getUrl(options.port, options.baseUrl);
}
export function getAppMode(app: ApplicationNames): "edit" | "run" {
  const options: ServerOptions = appToOptions[app];
  if (!options) {
    throw new Error(`No server options for app: ${app}`);
  }
  return options.command;
}

// Reset file via git checkout
export async function resetFile(app: ApplicationNames): Promise<void> {
  const pathToApp = path.join(pydir, app);
  const cmd = `git checkout -- ${pathToApp}`;
  await new Promise((resolve, reject) => {
    exec(cmd, (error) => {
      if (error) {
        reject(error);
      } else {
        resolve(undefined);
      }
    });
  });
  return;
}

// Start marimo server for the given app
export function startServer(app: ApplicationNames): void {
  const options: ServerOptions = appToOptions[app];
  if (!options) {
    throw new Error(`No server options for app: ${app}`);
  }
  const port = options.port ?? EDIT_PORT;
  const pathToApp = path.join(pydir, app);
  const marimoCmd = `marimo -q ${options.command} ${pathToApp} -p ${port} --headless`;
  exec(marimoCmd);
}

const WASM_SERVER = {
  command: "PYODIDE=true vite --port 3000",
  url: "http://localhost:3000",
  reuseExistingServer: !!process.env.CI,
};

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
  // Number of workers to use. Defaults to 1.
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
      testIgnore: ["**/cells.spec.ts", "**/disabled.spec.ts"],
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
  webServer: [
    ...Object.entries(appToOptions).flatMap(([app, opts]) => {
      const options = opts as ServerOptions;
      app = app.replace("//edit", "").replace("//run", "");

      const { command, port } = options;
      if (!port) {
        return [];
      }

      const baseUrl = options.command === "run" ? options.baseUrl : undefined;

      const pathToApp = path.join(pydir, app);
      let marimoCmd = `marimo -q ${command} ${pathToApp} -p ${port} --headless --no-token`;
      if (baseUrl) {
        marimoCmd += ` --base-url=${baseUrl}`;
      }

      return {
        command: marimoCmd,
        url: getUrl(port, baseUrl),
        reuseExistingServer: false,
      };
    }),
    {
      command: `marimo -q edit -p ${EDIT_PORT} --headless --no-token`,
      url: getUrl(EDIT_PORT),
      reuseExistingServer: false,
    },
    // WASM_SERVER,
  ],
};

export default config;
