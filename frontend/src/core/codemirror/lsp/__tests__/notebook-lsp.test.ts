/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect } from "vitest";
import { createNotebookLens } from "../lens";
import type * as LSP from "vscode-languageserver-protocol";

describe("createNotebookLens", () => {
  it("should calculate correct line offsets", () => {
    const cell = "line1\nline2";
    const allCode = ["fileA\nfileB", cell, "fileC"];
    const lens = createNotebookLens(cell, allCode);

    const pos: LSP.Position = { line: 0, character: 0 };
    const transformed = lens.transformPosition(pos);
    expect(transformed.line).toBe(2); // After fileA\nfileB
    expect(transformed.character).toBe(0);
  });

  it("should transform ranges to merged doc", () => {
    const cell = "cell1\ncell2";
    const allCode = ["before\ntext", cell];
    const lens = createNotebookLens(cell, allCode);

    const range: LSP.Range = {
      start: { line: 0, character: 0 },
      end: { line: 1, character: 5 },
    };

    const transformed = lens.transformRange(range);
    expect(transformed.start.line).toBe(2);
    expect(transformed.end.line).toBe(3);
  });

  it("should reverse ranges from merged doc", () => {
    const cell = "test\ncode";
    const allCode = ["header", cell];
    const lens = createNotebookLens(cell, allCode);

    const range: LSP.Range = {
      start: { line: 1, character: 0 },
      end: { line: 2, character: 4 },
    };

    const reversed = lens.reverseRange(range);
    expect(reversed.start.line).toBe(0);
    expect(reversed.end.line).toBe(1);
  });

  it("should check if range is within cell bounds", () => {
    const cell = "line1\nline2\nline3";
    const lens = createNotebookLens(cell, [cell]);

    expect(
      lens.isInRange({
        start: { line: 0, character: 0 },
        end: { line: 2, character: 5 },
      }),
    ).toBe(true);

    expect(
      lens.isInRange({
        start: { line: 0, character: 0 },
        end: { line: 3, character: 0 },
      }),
    ).toBe(false);
  });

  it("should join all code into merged text", () => {
    const cell = "cell";
    const allCode = ["a", cell, "b"];
    const lens = createNotebookLens(cell, allCode);

    expect(lens.mergedText).toBe("a\ncell\nb");
  });
});
