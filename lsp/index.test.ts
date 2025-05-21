import { spawn } from "node:child_process";
import { describe, it, expect } from "vitest";

describe("LSP Server", () => {
  it("should start and be killable", async () => {
    const process = spawn("node", ["./dist/index.cjs"]);

    // Give it a moment to start
    await new Promise((resolve) => setTimeout(resolve, 1000));

    // Kill the process
    process.kill();

    // Wait for process to die
    await new Promise<void>((resolve) => {
      process.on("exit", () => resolve());
    });

    expect(process.killed).toBe(true);
  });
});
