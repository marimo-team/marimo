/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { createMarimoFile } from "../parse";

describe("createMarimoFile", () => {
  it("should return a string", () => {
    const app = {
      cells: [
        {
          code: 'print("Hello, World!")',
        },
      ],
    };
    const result = createMarimoFile(app);
    expect(typeof result).toBe("string");
  });

  it("should correctly format a single cell", () => {
    const app = {
      cells: [
        {
          code: 'print("Hello, World!")',
        },
      ],
    };
    const result = createMarimoFile(app);
    const expected = [
      "import marimo",
      "app = marimo.App()",
      "@app.cell",
      "def __():",
      '    print("Hello, World!")',
      "    return",
    ].join("\n");
    expect(result).toBe(expected);
  });

  it("should correctly format multiple cells", () => {
    const app = {
      cells: [
        {
          code: 'print("Hello, World!")',
        },
        {
          code: 'print("Goodbye, World!")',
        },
      ],
    };
    const result = createMarimoFile(app);
    const expected = [
      "import marimo",
      "app = marimo.App()",
      "@app.cell",
      "def __():",
      '    print("Hello, World!")',
      "    return",
      "@app.cell",
      "def __():",
      '    print("Goodbye, World!")',
      "    return",
    ].join("\n");
    expect(result).toBe(expected);
  });
});
