/* Copyright 2023 Marimo. All rights reserved. */

import { expect, describe, it } from "vitest";
import { collapseConsoleOutputs } from "../collapseConsoleOutputs";
import { OutputMessage } from "@/core/kernel/messages";

describe("collapseConsoleOutputs", () => {
  it("should collapse last two text/plain outputs on the same channel", () => {
    const consoleOutputs: OutputMessage[] = [
      { mimetype: "text/plain", channel: "1", data: "Hello ", timestamp: "" },
      { mimetype: "text/plain", channel: "1", data: "World", timestamp: "" },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result[0].data).toMatchInlineSnapshot('"Hello World"');
  });

  it("should not collapse outputs on different channels", () => {
    const consoleOutputs: OutputMessage[] = [
      { mimetype: "text/plain", channel: "1", data: "Hello ", timestamp: "" },
      { mimetype: "text/plain", channel: "2", data: "World", timestamp: "" },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result).toEqual(consoleOutputs);
  });

  it("should not collapse outputs of different mimetypes", () => {
    const consoleOutputs: OutputMessage[] = [
      { mimetype: "text/plain", channel: "1", data: "Hello ", timestamp: "" },
      { mimetype: "text/html", channel: "1", data: "World", timestamp: "" },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result).toEqual(consoleOutputs);
  });

  it("should handle carriage returns", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "1",
        data: "Hello\rWorld",
        timestamp: "",
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result[0].data).toMatchInlineSnapshot('"World"');
  });

  it("should handle multiple carriage returns", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "1",
        data: "Hello\rWorld\r!",
        timestamp: "",
      },
    ];
    const result = collapseConsoleOutputs(consoleOutputs);
    expect(result[0].data).toMatchInlineSnapshot('"!orld"');
  });

  it("should handle carriage returns with newlines", () => {
    const consoleOutputs: OutputMessage[] = [
      {
        mimetype: "text/plain",
        channel: "1",
        data: "Hello\nWorld\r!",
        timestamp: "",
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
