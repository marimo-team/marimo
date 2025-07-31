/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { OutputMessage } from "@/core/kernel/messages";
import { collapseConsoleOutputs } from "../collapseConsoleOutputs";

describe("collapseConsoleOutputs", () => {
  it("should collapse last two text/plain outputs on the same channel", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "output",
        data: "Hello ",
        timestamp: 0,
      },
      {
        mimetype: "text/plain",
        channel: "output",
        data: "World",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result[0].data).toMatchInlineSnapshot(`"Hello World"`);
  });

  it("should collapse last two text/plain outputs on the same channel if they end in newlines", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "output",
        data: "Hello\n",
        timestamp: 0,
      },
      {
        mimetype: "text/plain",
        channel: "output",
        data: "World\n",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result[0].data).toMatchInlineSnapshot(`"Hello\nWorld\n"`);
  });

  it("should not collapse outputs on different channels", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "output",
        data: "Hello ",
        timestamp: 0,
      },
      {
        mimetype: "text/plain",
        channel: "stdout",
        data: "World",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result).toEqual(consoleOutputs);
  });

  it("should not collapse outputs of different mimetypes", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "output",
        data: "Hello ",
        timestamp: 0,
      },
      {
        mimetype: "text/html",
        channel: "output",
        data: "World",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result).toEqual(consoleOutputs);
  });

  it("should handle carriage returns", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "output",
        data: "Hello\rWorld",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result[0].data).toMatchInlineSnapshot('"World"');
  });

  it("should handle multiple carriage returns", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "output",
        data: "Hello\rWorld\r!",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result[0].data).toMatchInlineSnapshot('"!orld"');
  });

  it("should handle carriage returns with newlines", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "output",
        data: "Hello\nWorld\r!",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result).toHaveLength(1);
    expect(result[0].data).toMatchInlineSnapshot(`
      "Hello
      !orld"
    `);
  });

  it("doesn't mutate the input", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "output",
        data: "Hello ",
        timestamp: 0,
      },
      {
        mimetype: "text/plain",
        channel: "output",
        data: "World",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result).not.toBe(consoleOutputs);
    expect(result[0]).not.toBe(consoleOutputs[0]);
    expect(result[1]).not.toBe(consoleOutputs[1]);
  });

  it("should truncate head of text/plain single message", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "output",
        data: "Hello\nWorld\nBye\nWorld",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs, 2);
    expect(result.length).toBe(2);
    // First result is a warning re: truncation
    expect(result[0].data).toContain("Streaming output truncated");
    // First two lines are truncated
    expect(result[1].data).toBe("Bye\nWorld");
  });

  it("should truncate head of text/plain multiple channels", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "stdout",
        data: "A\nB\nC\nD\n",
        timestamp: 0,
      },
      {
        mimetype: "text/plain",
        channel: "stderr",
        data: "E\nF\nG\nH\n",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs, 7);
    expect(result.length).toBe(3);
    // First result is a warning re: truncation
    expect(result[0].data).toContain("Streaming output truncated");
    // First two lines are truncated, leaving 2 lines
    expect(result[1].data).toBe("D\n");
    // No truncation: 5 lines, for a total of 2 + 5 = 7 lines
    expect(result[2].data).toBe("E\nF\nG\nH\n");
  });

  it("should truncate head of text/plain same channel", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "stdout",
        data: "A\nB\nC\nD\n",
        timestamp: 0,
      },
      {
        mimetype: "text/plain",
        channel: "stdout",
        data: "E\nF\nG\nH\n",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs, 7);
    // 1 warning message, and 1 message containing merged stdout
    expect(result.length).toBe(2);
    // First result is a warning re: truncation
    expect(result[0].data).toContain("Streaming output truncated");
    // First two lines are truncated
    expect(result[1].data).toBe("C\nD\nE\nF\nG\nH\n");
  });

  it("should truncate head with text/html counting as one line", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "stdout",
        data: "A\nB\nC\nD\n",
        timestamp: 0,
      },
      {
        mimetype: "text/html",
        channel: "output",
        data: "<pre>E\nF\nG\nH\n</pre>",
        timestamp: 0,
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs, 3);
    // 1 warning message, and 1 message containing merged stdout
    expect(result.length).toBe(3);
    // First result is a warning re: truncation
    expect(result[0].data).toContain("Streaming output truncated");
    // 2 lines
    expect(result[1].data).toBe("D\n");
    // heuristic: non-text counts as 1 line ...
    expect(result[2].data).toBe("<pre>E\nF\nG\nH\n</pre>");
  });
});
