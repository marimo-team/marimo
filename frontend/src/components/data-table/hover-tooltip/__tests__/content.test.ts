/* Copyright 2026 Marimo. All rights reserved. */
import type { Cell } from "@tanstack/react-table";
import { describe, expect, it } from "vitest";
import { applyHoverTemplate, computeCellTooltipContent } from "../content";

function fakeCell(columnId: string, value: unknown, hoverTitle?: string) {
  return {
    column: { id: columnId },
    getValue: () => value,
    getHoverTitle: () => hoverTitle,
  } as unknown as Cell<unknown, unknown>;
}

describe("applyHoverTemplate", () => {
  it("substitutes column placeholders", () => {
    const cells = [fakeCell("first", "Michael"), fakeCell("last", "Scott")];
    expect(applyHoverTemplate("{{first}} {{last}}", cells)).toBe(
      "Michael Scott",
    );
  });

  it("renders nulls as empty strings", () => {
    const cells = [fakeCell("a", null)];
    expect(applyHoverTemplate("[{{a}}]", cells)).toBe("[]");
  });

  it("leaves unknown placeholders intact", () => {
    expect(applyHoverTemplate("{{missing}}", [fakeCell("a", 1)])).toBe(
      "{{missing}}",
    );
  });
});

describe("computeCellTooltipContent", () => {
  it("prefers cell-level hover title", () => {
    const cell = fakeCell("a", 1, "cell text");
    expect(computeCellTooltipContent(cell, "{{a}}")).toBe("cell text");
  });

  it("falls back to row template when no cell title", () => {
    const cell = {
      column: { id: "first" },
      getValue: () => "X",
      getHoverTitle: () => undefined,
      row: {
        getVisibleCells: () => [
          fakeCell("first", "Jim"),
          fakeCell("last", "Halpert"),
        ],
      },
    } as unknown as Cell<unknown, unknown>;
    expect(computeCellTooltipContent(cell, "{{first}} {{last}}")).toBe(
      "Jim Halpert",
    );
  });

  it("returns undefined with no title and no template", () => {
    expect(computeCellTooltipContent(fakeCell("a", 1), null)).toBeUndefined();
  });
});
