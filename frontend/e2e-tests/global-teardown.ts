/* Copyright 2026 Marimo. All rights reserved. */
/** biome-ignore-all lint/suspicious/noConsole: for debugging */

import { exec } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(exec);

async function globalTeardown() {
  console.log("🧹 Cleaning up test environment...");

  try {
    // Kill marimo processes and their parent uv processes.
    // uv doesn't forward SIGTERM to children, so Playwright's
    // webServer termination hangs waiting for the uv process to exit.
    // Using SIGKILL (-9) ensures processes die immediately.
    //
    // The [m] and [u] character-class trick prevents pkill from matching
    // its own shell wrapper process. Without it, `pkill -f 'marimo...'`
    // matches `sh -c "pkill -f 'marimo...'"` and kills the wrapper,
    // causing execAsync to reject before the second pkill can run.
    await execAsync("pkill -9 -f '[m]arimo.*--headless' || true").catch(
      () => {},
    );
    await execAsync("pkill -9 -f '[u]v.*run.*[m]arimo' || true").catch(
      () => {},
    );
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
