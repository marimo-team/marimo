import * as childProcess from "node:child_process";
import * as os from "node:os";
import * as path from "node:path";

import { describe, expect, it } from "vitest";

describe("LSP Server", () => {
  it("should start and be killable", async () => {
    const process = childProcess.spawn("node", [
      "./dist/index.cjs",
      "--lsp",
      "echo hello",
      "--log-file",
      path.join(os.tmpdir(), "lsp-server-test.log"),
    ]);

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
