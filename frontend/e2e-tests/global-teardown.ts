/* Copyright 2026 Marimo. All rights reserved. */
/** biome-ignore-all lint/suspicious/noConsole: for debugging */

import { exec } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(exec);

async function globalTeardown() {
  console.log("🧹 Cleaning up test environment...");

  try {
    // Kill marimo processes, kernel workers, and parent uv processes.
    // uv doesn't forward SIGTERM to children, so Playwright's
    // webServer termination hangs waiting for the process to exit.
    // Using SIGKILL (-9) ensures processes die immediately.
    //
    // The character-class trick (e.g. [m]arimo) prevents pkill from
    // matching its own shell wrapper process.
    //
    // We kill broadly — any process with "marimo" in its command line —
    // to catch orphan kernel workers that survive the parent being killed.
    const killCmds = [
      "pkill -9 -f '[m]arimo' || true",
      "pkill -9 -f '[u]v.*run.*[m]arimo' || true",
    ];
    for (const cmd of killCmds) {
      // eslint-disable-next-line @typescript-eslint/no-empty-function
      await execAsync(cmd).catch(() => {});
    }
    console.log("✅ Cleaned up marimo/uv processes");

    // Small delay to ensure cleanup completes
    await new Promise((resolve) => setTimeout(resolve, 1000));

    console.log("🎉 Cleanup complete!");
  } catch (error) {
    console.error("❌ Error during cleanup:", error);
    // Don't throw - we don't want cleanup failures to fail the test run
  }
}

export default globalTeardown;
