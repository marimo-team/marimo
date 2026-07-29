/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable no-console -- for debugging */

import { exec } from "node:child_process";
import { promisify } from "node:util";
import { getTestPorts } from "../playwright.config";

const execAsync = promisify(exec);

/**
 * Kill a process and all of its descendants (e.g. orphaned kernel
 * workers spawned via multiprocessing).
 */
async function killProcessTree(pid: number): Promise<void> {
  try {
    const { stdout } = await execAsync(`pgrep -P ${pid}`);
    const childPids = stdout
      .split("\n")
      .map((line) => Number.parseInt(line.trim(), 10))
      .filter((childPid) => Number.isInteger(childPid));
    await Promise.all(childPids.map((childPid) => killProcessTree(childPid)));
  } catch {
    // No children found; pgrep exits non-zero in that case.
  }

  try {
    await execAsync(`kill -9 ${pid}`);
  } catch {
    // Process may have already exited.
  }
}

async function getCommand(pid: number): Promise<string> {
  try {
    const { stdout } = await execAsync(`ps -o command= -p ${pid}`);
    return stdout.trim();
  } catch {
    return "";
  }
}

/**
 * Kill whatever is listening on `port`, plus its parent process (`uv`,
 * which doesn't forward SIGTERM to the marimo process it spawns) and all
 * descendants (orphaned kernel workers).
 */
async function killServerOnPort(port: number): Promise<void> {
  let pids: number[] = [];
  try {
    const { stdout } = await execAsync(`lsof -ti tcp:${port} -sTCP:LISTEN -nP`);
    pids = stdout
      .split("\n")
      .map((line) => Number.parseInt(line.trim(), 10))
      .filter((pid) => Number.isInteger(pid));
  } catch {
    // Nothing listening on this port.
    return;
  }

  for (const pid of pids) {
    const command = await getCommand(pid);
    if (!command.includes("marimo")) {
      continue;
    }

    let targetPid = pid;
    try {
      const { stdout } = await execAsync(`ps -o ppid= -p ${pid}`);
      const parentPid = Number.parseInt(stdout.trim(), 10);
      if (Number.isInteger(parentPid) && parentPid > 1) {
        // Only promote to the parent if it's actually the `uv` wrapper;
        // otherwise leave it alone and just kill the marimo process itself.
        const parentCommand = await getCommand(parentPid);
        if (/(^|\/)uv(\s|$)/.test(parentCommand)) {
          targetPid = parentPid;
        }
      }
    } catch {
      // Fall back to killing just the pid bound to the port.
    }
    await killProcessTree(targetPid);
  }
}

async function globalTeardown() {
  console.log("🧹 Cleaning up test environment...");

  try {
    const ports = getTestPorts();
    await Promise.all(ports.map((port) => killServerOnPort(port)));
    console.log(`✅ Cleaned up marimo servers on ports: ${ports.join(", ")}`);

    // Small delay to ensure cleanup completes
    await new Promise((resolve) => setTimeout(resolve, 1000));

    console.log("🎉 Cleanup complete!");
  } catch (error) {
    console.error("❌ Error during cleanup:", error);
    // Don't throw - we don't want cleanup failures to fail the test run
  }
}

export default globalTeardown;
