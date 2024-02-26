/* Copyright 2024 Marimo. All rights reserved. */

import { expect, describe, it } from "vitest";
import { collapseConsoleOutputs } from "../collapseConsoleOutputs";
import { OutputMessage } from "@/core/kernel/messages";

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
});
