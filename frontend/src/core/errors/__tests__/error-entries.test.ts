/* Copyright 2026 Marimo. All rights reserved. */

import { createStore } from "jotai";
import { describe, expect, it } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import { notebookAtom } from "@/core/cells/cells";
import {
  cell,
  document as documentOf,
  withCells,
} from "@/core/notebook/document/__tests__/fixtures";
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
  it("pairs an error with the source that raised it, not a later draft", () => {
    const id = cellId("c1");
    const store = createStore();
    store.set(
      notebookAtom,
      MockNotebook.notebookState({
        cellData: { [id]: { code: "print('fixed')" } },
      }),
    );
    MockExecutions.seed(
      store,
      [MockExecutions.failed(id, {}, { code_fingerprint: "ran" })],
      null,
      withCells(
        documentOf(),
        {
          c1: null,
          c2: null,
          [id]: cell(id, "1 / 0", { code_fingerprint: "ran" }),
        },
        [id],
      ),
    );

    expect(getCellErrorEntries(store)[0]?.cellCode).toBe("1 / 0");
  });

  it("falls back to the cell's current source once an edit is confirmed", () => {
    const id = cellId("c1");
    const store = createStore();
    MockNotebook.withErrors(store, [
      {
        cellId: id,
        cellName: "c1",
        code: "1 / 0",
        error: {
          kind: "exception",
          name: "ZeroDivisionError",
          message: "division by zero",
        },
      },
    ]);

    expect(getCellErrorEntries(store)).toEqual([
      expect.objectContaining({
        cellId: id,
        cellCode: "1 / 0",
        errorData: [
          expect.objectContaining({
            type: "exception",
            exception_type: "ZeroDivisionError",
            msg: "division by zero",
          }),
        ],
      }),
    ]);
  });
});
