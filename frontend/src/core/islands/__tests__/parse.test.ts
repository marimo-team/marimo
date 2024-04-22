/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { MarimoIslandApp, createMarimoFile } from "../parse";

describe("createMarimoFile", () => {
  it("should return a string", () => {
    const app: MarimoIslandApp = {
      id: "1",
      cells: [
        {
          output: "Hello, World!",
          code: 'print("Hello, World!")',
        },
      ],
    };
    const result = createMarimoFile(app);
    expect(typeof result).toBe("string");
  });

  it("should correctly format a single cell", () => {
    const app: MarimoIslandApp = {
      id: "1",
      cells: [
        {
          output: "Hello, World!",
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
    const app: MarimoIslandApp = {
      id: "1",
      cells: [
        {
          output: "",
          code: 'print("Hello, World!")',
        },
        {
          output: "",
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
