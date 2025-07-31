/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { indentOneTab } from "../utils/indentOneTab";

describe("indentOneTab", () => {
  it("should indent non-empty lines by one tab", () => {
    const input = "line1\nline2\nline3";
    const expected = "    line1\n    line2\n    line3";
    expect(indentOneTab(input)).toBe(expected);
  });

  it("should not indent empty lines", () => {
    const input = "line1\n\nline2\n\nline3";
    const expected = "    line1\n\n    line2\n\n    line3";
    expect(indentOneTab(input)).toBe(expected);
  });

  it("should handle lines with only whitespace", () => {
    const input = "line1\n  \nline2\n\t\nline3";
    const expected = "    line1\n  \n    line2\n\t\n    line3";
    expect(indentOneTab(input)).toBe(expected);
  });

  it("should handle empty string", () => {
    expect(indentOneTab("")).toBe("");
  });

  it("should handle single line", () => {
    expect(indentOneTab("single line")).toBe("    single line");
  });
});
