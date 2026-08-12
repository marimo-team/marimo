/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import { type CellErrorEntry, formatCellError } from "../error-entries";

describe("formatCellError", () => {
  it("formats current tracebacks without notebook source", () => {
    const entry: CellErrorEntry = {
      cellId: cellId("cell-1"),
      cellName: "Cell 1",
      cellCode: "password = 'private'",
      errorData: [],
      tracebackHtml:
        '<span class="gr">ValueError</span>: <span class="n">bad value</span>',
    };

    const text = formatCellError(entry);

    expect(text).toContain("Cell 1");
    expect(text).toContain("ValueError: bad value");
    expect(text).not.toContain("password");
    expect(text).not.toContain("<span");
  });
});
