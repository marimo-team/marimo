/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { createMarimoFile, parseIslandCode } from "../parse";

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

describe("parseIslandCode", () => {
  let codes = [
    `
  def __():
    print("Hello, World!")
    return
  `,
    `def __():\n    print("Hello, World!")\n    return`,
    `def __():
    print("Hello, World!")
    return`,
  ];

  codes = [...codes, ...codes.map(encodeURIComponent)];

  it.each(
    codes,
  )("should return the code without leading or trailing whitespace", (code) => {
    const result = parseIslandCode(code);
    const expected = 'def __():\n    print("Hello, World!")\n    return';
    expect(result).toBe(expected);
  });
});
