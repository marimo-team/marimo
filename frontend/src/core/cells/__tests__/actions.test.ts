/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { scrollAndHighlightCell } from "@/components/editor/links/cell-link";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { createCellRuntimeState } from "@/core/cells/types";
import { store } from "@/core/state/jotai";
import { notebookScrollToRunning } from "../actions";

vi.mock("@/components/editor/links/cell-link", () => ({
  scrollAndHighlightCell: vi.fn(),
}));

describe("notebookScrollToRunning", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    store.set(notebookAtom, MockNotebook.notebookState({ cellData: {} }));
  });

  it("scrolls to the first running cell in notebook order", () => {
    const runtimeOnlyCellId = "runtime-only" as CellId;
    const idleCellId = "idle-cell" as CellId;
    const runningCellId = "running-cell" as CellId;

    const notebook = MockNotebook.notebookState({
      cellData: {
        [idleCellId]: {},
        [runningCellId]: {},
      },
      cellRuntime: {
        [idleCellId]: { status: "idle" },
        [runningCellId]: { status: "running" },
      },
    });
    notebook.cellRuntime = {
      [runtimeOnlyCellId]: createCellRuntimeState({ status: "running" }),
      ...notebook.cellRuntime,
    };
    store.set(notebookAtom, notebook);

    notebookScrollToRunning();

    expect(scrollAndHighlightCell).toHaveBeenCalledOnce();
    expect(scrollAndHighlightCell).toHaveBeenCalledWith(runningCellId, "focus");
  });
});
