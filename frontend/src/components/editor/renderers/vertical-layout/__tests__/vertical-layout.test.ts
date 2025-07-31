/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, expect, it } from "vitest";
import type { OutputMessage } from "@/core/kernel/messages";
import { groupCellsByColumn, shouldHideCode } from "../vertical-layout";

describe("groupCellsByColumn", () => {
  it("should group cells by column and maintain order", () => {
    const cells = [
      { config: { column: 0 }, id: "1" },
      { config: { column: 1 }, id: "2" },
      { config: { column: 0 }, id: "3" },
      { config: { column: 2 }, id: "4" },
      { config: { column: 1 }, id: "5" },
    ] as any[];

    const result = groupCellsByColumn(cells);

    expect(result).toEqual([
      [0, [cells[0], cells[2]]],
      [1, [cells[1], cells[4]]],
      [2, [cells[3]]],
    ]);
  });

  it("should use last seen column when column not specified", () => {
    const cells = [
      { config: { column: 0 }, id: "1" },
      { config: {}, id: "2" },
      { config: { column: 1 }, id: "3" },
      { config: {}, id: "4" },
    ] as any[];

    const result = groupCellsByColumn(cells);

    expect(result).toEqual([
      [0, [cells[0], cells[1]]],
      [1, [cells[2], cells[3]]],
    ]);
  });
});

describe("shouldHideCode", () => {
  // Helper function to create valid OutputMessage
  const createOutput = (
    data: any = "some output",
    mimetype: OutputMessage["mimetype"] = "text/plain",
  ): OutputMessage => ({
    channel: "output",
    mimetype,
    data,
    timestamp: Date.now(),
  });

  describe("empty/whitespace code", () => {
    it("should return true for empty string", () => {
      expect(shouldHideCode("", null)).toBe(true);
      expect(shouldHideCode("", createOutput())).toBe(true);
    });

    it("should return true for whitespace-only strings", () => {
      expect(shouldHideCode("   ", null)).toBe(true);
      expect(shouldHideCode("   ", createOutput())).toBe(true);
      expect(shouldHideCode("\n\n", null)).toBe(true);
      expect(shouldHideCode("\n\n", createOutput())).toBe(true);
      expect(shouldHideCode("  \n  \t  ", null)).toBe(true);
      expect(shouldHideCode("  \n  \t  ", createOutput())).toBe(true);
      expect(shouldHideCode("\r\n  \r\n", null)).toBe(true);
      expect(shouldHideCode("\r\n  \r\n", createOutput())).toBe(true);
    });
  });

  describe("markdown code with output", () => {
    it("should return true for basic markdown with output", () => {
      const markdownCode = 'mo.md("# Hello World")';
      expect(shouldHideCode(markdownCode, createOutput())).toBe(true);
    });

    it("should return true for multi-line markdown with output", () => {
      const markdownCode = 'mo.md("""\n# Hello\nThis is content\n""")';
      expect(shouldHideCode(markdownCode, createOutput())).toBe(true);
    });

    it("should return true for f-string markdown with output", () => {
      const markdownCode = 'mo.md(f"# Hello {name}")';
      expect(shouldHideCode(markdownCode, createOutput())).toBe(true);
    });

    it("should return true for raw string markdown with output", () => {
      const markdownCode = 'mo.md(r"# Hello World")';
      expect(shouldHideCode(markdownCode, createOutput())).toBe(true);
    });

    it("should return true for rf-string markdown with output", () => {
      const markdownCode = 'mo.md(rf"# Hello {name}")';
      expect(shouldHideCode(markdownCode, createOutput())).toBe(true);
    });

    it("should return true for markdown with various output types", () => {
      const markdownCode = 'mo.md("# Hello")';

      expect(
        shouldHideCode(markdownCode, createOutput("text", "text/plain")),
      ).toBe(true);
      expect(
        shouldHideCode(
          markdownCode,
          createOutput({ key: "value" }, "application/json"),
        ),
      ).toBe(true);
      expect(
        shouldHideCode(
          markdownCode,
          createOutput("<div>html</div>", "text/html"),
        ),
      ).toBe(true);
      expect(
        shouldHideCode(markdownCode, createOutput("base64image", "image/png")),
      ).toBe(true);
    });
  });

  describe("markdown code without output", () => {
    it("should return false for different markdown formats without output", () => {
      const markdownCodes = [
        'mo.md("# Hello")',
        'mo.md(f"# Hello {name}")',
        'mo.md(r"# Hello")',
        'mo.md(rf"# Hello {name}")',
        'mo.md("""\n# Multi\nline\n""")',
        "mo.md('''# Single quotes''')",
      ];

      markdownCodes.forEach((code) => {
        expect(shouldHideCode(code, null)).toBe(false);
        expect(shouldHideCode(code, createOutput(""))).toBe(false);
      });
    });
  });

  describe("non-markdown code", () => {
    it("should return false for Python code with output", () => {
      const pythonCode = 'print("Hello World")';
      expect(shouldHideCode(pythonCode, createOutput())).toBe(false);
    });

    it("should return false for Python code without output", () => {
      const pythonCode = 'print("Hello World")';
      expect(shouldHideCode(pythonCode, null)).toBe(false);
      expect(shouldHideCode(pythonCode, createOutput(""))).toBe(false);
    });
  });

  describe("combination edge cases", () => {
    it("should prioritize empty code over markdown detection", () => {
      // Even if we somehow had markdown that was just whitespace, empty code should win
      expect(shouldHideCode("   ", createOutput())).toBe(true);
      expect(shouldHideCode("\n\t  \n", createOutput())).toBe(true);
    });

    it("should handle mo.md with only whitespace content", () => {
      const emptyMarkdown = 'mo.md("   ")';
      expect(shouldHideCode(emptyMarkdown, createOutput())).toBe(true);
      expect(shouldHideCode(emptyMarkdown, null)).toBe(false);
    });

    it("should handle mo.md with newlines only", () => {
      const newlineMarkdown = 'mo.md("\\n\\n\\n")';
      expect(shouldHideCode(newlineMarkdown, createOutput())).toBe(true);
      expect(shouldHideCode(newlineMarkdown, null)).toBe(false);
    });
  });
});
