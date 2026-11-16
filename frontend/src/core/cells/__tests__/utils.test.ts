/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */
import { describe, expect, it } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { initialNotebookState, type NotebookState } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import type { CellData } from "@/core/cells/types";
import type { CellFreshnessLookup } from "@/core/executions";
import type { OutputMessage } from "@/core/kernel/messages";
import {
  cellNeedsRun,
  disabledCellIds,
  enabledCellIds,
  isUninstantiated,
  shouldHidePublishedCell,
  staleCellIds,
} from "../utils";

type Cells = Record<
  string,
  { edited?: boolean; disabled?: boolean; staleInputs?: boolean }
>;

function notebook(cells: Cells): NotebookState {
  return {
    cellIds: Object.keys(cells),
    cellData: Object.fromEntries(
      Object.entries(cells).map(([id, cell]) => [
        id,
        { config: { disabled: cell.disabled } },
      ]),
    ),
    cellRuntime: Object.fromEntries(Object.keys(cells).map((id) => [id, {}])),
  } as any;
}

/** Freshness as the host would report it for `cells`. */
function freshness(cells: Cells): CellFreshnessLookup {
  return (id) => {
    const cell = cells[id];
    return {
      sourceChanged: cell?.edited ?? false,
      inputsChanged: cell?.staleInputs ?? false,
    };
  };
}

describe("staleCellIds", () => {
  it("should return cell IDs that have never run", () => {
    const cells: Cells = { cell1: {}, cell2: {} };
    const state = notebook(cells);
    const executions = MockExecutions.inputs([
      MockExecutions.completed("cell2"),
    ]);

    expect(staleCellIds(state, executions, freshness(cells))).toEqual([
      "cell1",
    ]);
  });

  it("should return cell IDs that are edited", () => {
    const cells: Cells = { cell1: { edited: true }, cell2: {} };
    const state = notebook(cells);
    const executions = MockExecutions.inputs([
      MockExecutions.completed("cell1"),
      MockExecutions.completed("cell2"),
    ]);

    expect(staleCellIds(state, executions, freshness(cells))).toEqual([
      "cell1",
    ]);
  });

  it("should return cell IDs that are interrupted", () => {
    const cells: Cells = { cell1: {}, cell2: {} };
    const state = notebook(cells);
    const executions = MockExecutions.inputs([
      MockExecutions.interrupted("cell1"),
      MockExecutions.completed("cell2"),
    ]);

    expect(staleCellIds(state, executions, freshness(cells))).toEqual([
      "cell1",
    ]);
  });

  it("should return cell IDs with stale inputs", () => {
    const cells: Cells = { cell1: { staleInputs: true }, cell2: {} };
    const state = notebook(cells);
    const executions = MockExecutions.inputs([
      MockExecutions.completed("cell1"),
      MockExecutions.completed("cell2"),
    ]);

    expect(staleCellIds(state, executions, freshness(cells))).toEqual([
      "cell1",
    ]);
  });

  it("should not return cell IDs that are disabled", () => {
    const cells: Cells = {
      cell1: { disabled: true, staleInputs: true },
      cell2: { staleInputs: true },
    };
    const state = notebook(cells);
    const executions = MockExecutions.inputs(
      [MockExecutions.completed("cell1"), MockExecutions.completed("cell2")],
      { blocked: new Set(["cell2"]) },
    );

    expect(staleCellIds(state, executions, freshness(cells))).toEqual([]);
  });
});

describe("staleCellIds with a run in progress", () => {
  it("leaves a running cell alone unless its source changed since", () => {
    const cells: Cells = { cell1: {}, cell2: { edited: true } };
    const state = notebook(cells);
    const executions = MockExecutions.inputs([
      MockExecutions.running("cell1"),
      MockExecutions.running("cell2"),
    ]);

    expect(staleCellIds(state, executions, freshness(cells))).toEqual([
      "cell2",
    ]);
  });

  it("leaves a submitted cell alone until the host has planned its run", () => {
    const cells: Cells = { cell1: { edited: true } };
    const state = notebook(cells);
    const ran = MockExecutions.completed("cell1");
    const executions = MockExecutions.inputs([ran], {
      requested: new Set(["cell1"]),
    });

    expect(staleCellIds(state, executions, freshness(cells))).toEqual([]);
  });
});

describe("cellNeedsRun", () => {
  const blocked = { interrupted: false, disabled: false, blocked: true };

  it("flags a blocked cell whose source changed, whatever its inputs did", () => {
    expect(
      cellNeedsRun({
        ...blocked,
        freshness: freshness({ c: { edited: true, staleInputs: true } })("c"),
      }),
    ).toBe(true);
  });

  it("does not flag a blocked cell for changed inputs alone", () => {
    expect(
      cellNeedsRun({
        ...blocked,
        freshness: freshness({ c: { staleInputs: true } })("c"),
      }),
    ).toBe(false);
  });
});

describe("isUninstantiated", () => {
  it("should return true if the cell has not run", () => {
    expect(isUninstantiated({ status: "idle", outcome: null })).toBe(true);
  });

  it("should return false if the cell has run", () => {
    expect(isUninstantiated({ status: "idle", outcome: "value" })).toBe(false);
  });

  it("should return false if the cell is currently queued or running", () => {
    expect(isUninstantiated({ status: "queued", outcome: null })).toBe(false);
    expect(isUninstantiated({ status: "running", outcome: null })).toBe(false);
  });

  it("should return false if the cell ended without a value", () => {
    expect(isUninstantiated({ status: "idle", outcome: "error" })).toBe(false);
    expect(isUninstantiated({ status: "idle", outcome: "interrupted" })).toBe(
      false,
    );
    expect(isUninstantiated({ status: "idle", outcome: "skipped" })).toBe(
      false,
    );
  });
});

describe("disabledCellIds", () => {
  it("should return only disabled cell IDs", () => {
    const cellId1 = CellId.create();
    const cellId2 = CellId.create();
    const cellId3 = CellId.create();

    const state: NotebookState = {
      ...initialNotebookState(),
      cellIds: [cellId1, cellId2, cellId3],
      cellData: {
        [cellId1]: { id: cellId1, config: { disabled: true } } as CellData,
        [cellId2]: { id: cellId2, config: { disabled: false } } as CellData,
        [cellId3]: { id: cellId3, config: { disabled: true } } as CellData,
      },
    };

    const result = disabledCellIds(state);
    expect(result).toEqual([cellId1, cellId3]);
  });
});

describe("enabledCellIds", () => {
  it("should return only enabled cell IDs", () => {
    const cellId1 = CellId.create();
    const cellId2 = CellId.create();
    const cellId3 = CellId.create();

    const state: NotebookState = {
      ...initialNotebookState(),
      cellIds: [cellId1, cellId2, cellId3],
      cellData: {
        [cellId1]: { id: cellId1, config: { disabled: true } } as CellData,
        [cellId2]: { id: cellId2, config: { disabled: false } } as CellData,
        [cellId3]: { id: cellId3, config: { disabled: false } } as CellData,
      },
    };

    const result = enabledCellIds(state);
    expect(result).toEqual([cellId2, cellId3]);
  });
});

describe("shouldHidePublishedCell", () => {
  const base = {
    errored: false,
    interrupted: false,
    stopped: false,
    output: null,
    showErrorTracebacks: false,
  };
  const errorOutput = (traceback?: string): OutputMessage => ({
    channel: "marimo-error",
    mimetype: "application/vnd.marimo+error",
    data: [
      { type: "exception", exception_type: "ValueError", msg: "!", traceback },
    ],
    timestamp: 0,
  });

  it("does not hide a healthy cell", () => {
    expect(shouldHidePublishedCell(base)).toBe(false);
  });

  it.each(["errored", "interrupted", "stopped"] as const)(
    "hides a %s cell",
    (key) => {
      expect(shouldHidePublishedCell({ ...base, [key]: true })).toBe(true);
    },
  );

  it("hides error outputs", () => {
    expect(shouldHidePublishedCell({ ...base, output: errorOutput() })).toBe(
      true,
    );
  });

  it("shows error outputs with a traceback when show_tracebacks is enabled", () => {
    expect(
      shouldHidePublishedCell({
        ...base,
        errored: true,
        output: errorOutput("Traceback (most recent call last) ..."),
        showErrorTracebacks: true,
      }),
    ).toBe(false);
  });

  it("hides error outputs without a traceback even when show_tracebacks is enabled", () => {
    expect(
      shouldHidePublishedCell({
        ...base,
        errored: true,
        output: errorOutput(),
        showErrorTracebacks: true,
      }),
    ).toBe(true);
  });
});
