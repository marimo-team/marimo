/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable no-console */

import { exec } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(exec);

async function globalTeardown() {
  console.log("🧹 Cleaning up test environment...");

  try {
    // Kill any remaining marimo processes
    try {
      await execAsync("pkill -f 'marimo.*--headless' || true");
      console.log("✅ Cleaned up marimo processes");
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
