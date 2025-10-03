import * as childProcess from "node:child_process";
import * as os from "node:os";
import * as path from "node:path";

import { describe, expect, it } from "vitest";

// Import the parseTypedCommand function - we need to export it first
import { parseTypedCommand } from "./index";

describe("parseTypedCommand", () => {
  it("should parse copilot commands correctly", () => {
    const result = parseTypedCommand(
      "copilot:/path/to/copilot/language-server.js",
    );
    expect(result).toEqual([
      "node",
      "/path/to/copilot/language-server.js",
      "--stdio",
    ]);
  });

  it("should parse copilot commands with spaces in path", () => {
    const result = parseTypedCommand(
      "copilot:/path/with spaces/copilot/language-server.js",
    );
    expect(result).toEqual([
      "node",
      "/path/with spaces/copilot/language-server.js",
      "--stdio",
    ]);
  });

  it("should parse basedpyright commands correctly", () => {
    const result = parseTypedCommand("basedpyright:basedpyright-langserver");
    expect(result).toEqual(["basedpyright-langserver", "--stdio"]);
  });

  it("should parse ty commands correctly", () => {
    const result = parseTypedCommand("ty:/path/to/ty");
    expect(result).toEqual(["/path/to/ty", "server"]);
  });

  it("should parse ty commands with spaces in path", () => {
    const result = parseTypedCommand("ty:/path/with spaces/ty");
    expect(result).toEqual(["/path/with spaces/ty", "server"]);
  });

  it("should fallback to old format for commands without colon", () => {
    const result = parseTypedCommand("node /path/to/binary --stdio");
    expect(result).toEqual(["node", "/path/to/binary", "--stdio"]);
  });

  it("should throw error for unknown server types", () => {
    expect(() => parseTypedCommand("unknown:/path/to/binary")).toThrow(
      "Unknown LSP server type: unknown",
    );
  });

  it("should handle edge cases with multiple colons", () => {
    const result = parseTypedCommand(
      "copilot:C:/Program Files/Node.js/language-server.js",
    );
    expect(result).toEqual([
      "node",
      "C:/Program Files/Node.js/language-server.js",
      "--stdio",
    ]);
  });
});

describe("LSP Server Integration", () => {
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

  it("should start with typed copilot command", async () => {
    const process = childProcess.spawn("node", [
      "./dist/index.cjs",
      "--lsp",
      "copilot:echo copilot-test",
      "--log-file",
      path.join(os.tmpdir(), "lsp-server-copilot-test.log"),
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
