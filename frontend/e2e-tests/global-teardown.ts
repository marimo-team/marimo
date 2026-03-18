/* Copyright 2026 Marimo. All rights reserved. */
/** biome-ignore-all lint/suspicious/noConsole: for debugging */

import { exec } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(exec);

async function globalTeardown() {
  console.log("🧹 Cleaning up test environment...");

  try {
    // Kill marimo processes and their parent uv processes.
    // On macOS, uv doesn't forward SIGTERM to children, so Playwright's
    // webServer termination hangs waiting for the uv process to exit.
    // Using SIGKILL (-9) ensures processes die immediately.
    try {
      await execAsync("pkill -9 -f 'marimo.*--headless' || true");
      await execAsync("pkill -9 -f 'uv.*marimo' || true");
      console.log("✅ Cleaned up marimo/uv processes");
    } catch {
      // Ignore errors - processes might not exist
      console.log("⚠️  No marimo processes to clean up");
    }

    // Small delay to ensure cleanup completes
    await new Promise((resolve) => setTimeout(resolve, 1000));

    console.log("🎉 Cleanup complete!");
  } catch (error) {
    console.error("❌ Error during cleanup:", error);
    // Don't throw - we don't want cleanup failures to fail the test run
  }
}

export default globalTeardown;
