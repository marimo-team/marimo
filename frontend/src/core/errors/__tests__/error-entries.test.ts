/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import {
  type CellErrorEntry,
  formatCellError,
  getCellErrorEntries,
} from "../error-entries";

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

describe("getCellErrorEntries", () => {
  it("pairs an error with the source that raised it, not a later edit", () => {
    const id = cellId("c1");
    const store = createStore();
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: { [id]: { code: "print('fixed')" } },
        cellRuntime: {
          [id]: {
            output: {
              channel: "marimo-error",
              mimetype: "application/vnd.marimo+error",
              data: [
                {
                  type: "exception",
                  exception_type: "ZeroDivisionError",
                  msg: "division by zero",
                },
              ],
              timestamp: 0,
              code: "1 / 0",
            },
          },
        },
      }),
    );

    expect(getCellErrorEntries(store)[0]?.cellCode).toBe("1 / 0");
  });
});
