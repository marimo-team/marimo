/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { StatefulOutputMessage } from "@/components/editor/output/ansi-reduce";
import type { OutputMessage } from "@/core/kernel/messages";
import {
  collapseConsoleOutputs,
  maybeMakeOutputStateful,
} from "../collapseConsoleOutputs";

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

  describe("ANSI escape sequences", () => {
    it("should handle cursor movement with collapse", () => {
      const consoleOutputs: OutputMessage[] = [
        {
          mimetype: "text/plain",
          channel: "output",
          data: "Hello",
          timestamp: 0,
        },
        {
          mimetype: "text/plain",
          channel: "output",
          data: "\u001B[5DWorld", // Move cursor back 5, write World
          timestamp: 0,
        },
      ];
      const result = collapseConsoleOutputs(consoleOutputs);
      expect(result[0].data).toBe("World");
    });

    it("should handle progress bar simulation", () => {
      // Simulate streaming: collapse is called after each new message
      let consoleOutputs: OutputMessage[] = [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Progress: 0%\r",
          timestamp: 0,
        },
      ];

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Progress: 50%\r",
          timestamp: 0,
        },
      ]);

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Progress: 100%",
          timestamp: 0,
        },
      ]);

      expect(consoleOutputs[0].data).toBe("Progress: 100%");
    });

    it("should handle tqdm-like progress bars", () => {
      // Simulate streaming: collapse is called after each new message
      let consoleOutputs: OutputMessage[] = [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Processing: |          | 0/100\r",
          timestamp: 0,
        },
      ];

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Processing: |█████     | 50/100\r",
          timestamp: 0,
        },
      ]);

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Processing: |██████████| 100/100",
          timestamp: 0,
        },
      ]);

      expect(consoleOutputs[0].data).toBe("Processing: |██████████| 100/100");
    });

    it("should handle cursor up/down movements", () => {
      // Test that cursor movements within a single message are handled
      const consoleOutputs: OutputMessage[] = [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Line 1\nLine 2\n\u001B[1AModified",
          timestamp: 0,
        },
      ];

      const result = collapseConsoleOutputs(consoleOutputs);
      // After moving up 1 line and writing "Modified", Line 2 gets overwritten
      expect(result[0].data).toBe("Line 1\nModified");
    });

    it("should handle clear screen sequence", () => {
      let consoleOutputs: OutputMessage[] = [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Old content\nMore old content\n",
          timestamp: 0,
        },
      ];

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "\u001B[2J", // Clear screen
          timestamp: 0,
        },
      ]);

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "New content",
          timestamp: 0,
        },
      ]);

      expect(consoleOutputs[0].data).toBe("New content");
    });

    it("should handle erase line sequences", () => {
      let consoleOutputs: OutputMessage[] = [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Hello World",
          timestamp: 0,
        },
      ];

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "\u001B[2K", // Erase entire line
          timestamp: 0,
        },
      ]);

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Goodbye",
          timestamp: 0,
        },
      ]);

      expect(consoleOutputs[0].data).toBe("           Goodbye");
    });

    it("should handle cursor positioning", () => {
      let consoleOutputs: OutputMessage[] = [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "abc",
          timestamp: 0,
        },
      ];

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "\u001B[1;2H", // Move to position (1,2)
          timestamp: 0,
        },
      ]);

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "XY",
          timestamp: 0,
        },
      ]);

      expect(consoleOutputs[0].data).toBe("aXY");
    });

    it("should handle complex multi-line progress updates", () => {
      // Test multi-line updates with ANSI sequences all in one message
      const consoleOutputs: OutputMessage[] = [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Task 1: 0%\nTask 2: 0%\n\u001B[2A\rTask 1: 100%\n\rTask 2: 100%\n",
          timestamp: 0,
        },
      ];
      const result = collapseConsoleOutputs(consoleOutputs);
      expect(result[0].data).toBe("Task 1: 100%\nTask 2: 100%\n");
    });

    it("should preserve ANSI state across multiple collapsed messages", () => {
      // Simulate streaming collapses
      let consoleOutputs: OutputMessage[] = [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Loading",
          timestamp: 0,
        },
      ];

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "\rLoading.",
          timestamp: 0,
        },
      ]);

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "\rLoading..",
          timestamp: 0,
        },
      ]);

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "\rLoading...",
          timestamp: 0,
        },
      ]);

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "\rComplete!  ",
          timestamp: 0,
        },
      ]);

      expect(consoleOutputs[0].data).toBe("Complete!  ");
    });
  });

  describe("StatefulOutputMessage", () => {
    it("should preserve StatefulOutputMessage through collapse", () => {
      const statefulMessage = StatefulOutputMessage.create({
        mimetype: "text/plain",
        channel: "stdout",
        data: "Hello\rWorld",
        timestamp: 0,
      });

      const consoleOutputs: OutputMessage[] = [
        statefulMessage,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: " Complete",
          timestamp: 0,
        },
      ];

      const result = collapseConsoleOutputs(consoleOutputs);
      expect(result.length).toBe(1);
      expect(result[0]).toBeInstanceOf(StatefulOutputMessage);
      expect(result[0].data).toBe("World Complete");
    });

    it("should handle mixing StatefulOutputMessage and regular messages", () => {
      let consoleOutputs: OutputMessage[] = [
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Line 1\n",
          timestamp: 0,
        },
      ];

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "Progress: 0%",
          timestamp: 0,
        },
      ]);

      consoleOutputs = collapseConsoleOutputs([
        ...consoleOutputs,
        {
          mimetype: "text/plain",
          channel: "stdout",
          data: "\rProgress: 100%",
          timestamp: 0,
        },
      ]);

      expect(consoleOutputs.length).toBe(1);
      expect(consoleOutputs[0]).toBeInstanceOf(StatefulOutputMessage);
      expect(consoleOutputs[0].data).toBe("Line 1\nProgress: 100%");
    });

    it("should handle StatefulOutputMessage with empty array input", () => {
      const consoleOutputs: OutputMessage[] = [];
      const result = collapseConsoleOutputs(consoleOutputs);
      expect(result).toEqual([]);
    });

    it("should handle StatefulOutputMessage with single message", () => {
      const statefulMessage = StatefulOutputMessage.create({
        mimetype: "text/plain",
        channel: "stdout",
        data: "Hello\rWorld",
        timestamp: 0,
      });

      const result = collapseConsoleOutputs([statefulMessage]);
      expect(result.length).toBe(1);
      expect(result[0]).toBeInstanceOf(StatefulOutputMessage);
      expect(result[0].data).toBe("World");
    });
  });

  describe("maybeMakeOutputStateful", () => {
    it("should convert regular string output to StatefulOutputMessage", () => {
      const output: OutputMessage = {
        mimetype: "text/plain",
        channel: "stdout",
        data: "Hello",
        timestamp: 0,
      };

      const result = maybeMakeOutputStateful(output);
      expect(result).toBeInstanceOf(StatefulOutputMessage);
      expect(result.data).toBe("Hello");
    });

    it("should preserve StatefulOutputMessage as-is", () => {
      const statefulMessage = StatefulOutputMessage.create({
        mimetype: "text/plain",
        channel: "stdout",
        data: "Hello",
        timestamp: 0,
      });

      const result = maybeMakeOutputStateful(statefulMessage);
      expect(result).toBe(statefulMessage);
    });

    it("should return non-string output as-is", () => {
      const output: OutputMessage = {
        mimetype: "application/json",
        channel: "output",
        data: { key: "value" },
        timestamp: 0,
      };

      const result = maybeMakeOutputStateful(output);
      expect(result).toBe(output);
      expect(result).not.toBeInstanceOf(StatefulOutputMessage);
    });
  });
});
