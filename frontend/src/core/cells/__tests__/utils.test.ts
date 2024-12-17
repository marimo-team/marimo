/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect } from "vitest";
import { getCellConfigs, type NotebookState } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { MultiColumn } from "@/utils/id-tree";
import type { CellData, CellRuntimeState } from "@/core/cells/types";
import {
  disabledCellIds,
  enabledCellIds,
  isUninstantiated,
  staleCellIds,
} from "../utils";

describe("getCellConfigs", () => {
  it("should return correct cell configs with column indices", () => {
    // Create mock cell IDs
    const cellId1 = CellId.create();
    const cellId2 = CellId.create();
    const cellId3 = CellId.create();
    const cellId4 = CellId.create();

    // Create a mock NotebookState
    const mockState: NotebookState = {
      cellIds: MultiColumn.from([
        [cellId1, cellId2],
        [cellId3, cellId4],
      ]),
      cellData: {
        [cellId1]: {
          id: cellId1,
          config: { hide_code: false, disabled: false },
        } as CellData,
        [cellId2]: {
          id: cellId2,
          config: { hide_code: true, disabled: false },
        } as CellData,
        [cellId3]: {
          id: cellId3,
          config: { hide_code: false, disabled: true },
        } as CellData,
        [cellId4]: {
          id: cellId4,
          config: { hide_code: true, disabled: true },
        } as CellData,
      },
      cellRuntime: {} as Record<CellId, CellRuntimeState>,
      cellHandles: {},
      history: [],
      scrollKey: null,
      cellLogs: [],
    };

    // Call the function
    const result = getCellConfigs(mockState);

    // Assert the results
    expect(result).toEqual([
      { hide_code: false, disabled: false, column: 0 },
      { hide_code: true, disabled: false },
      { hide_code: false, disabled: true, column: 1 },
      { hide_code: true, disabled: true },
    ]);

    // Check that the original state was not modified
    expect(mockState.cellData[cellId1].config).toEqual({
      hide_code: false,
      disabled: false,
    });
    expect(mockState.cellData[cellId2].config).toEqual({
      hide_code: true,
      disabled: false,
    });
    expect(mockState.cellData[cellId3].config).toEqual({
      hide_code: false,
      disabled: true,
    });
    expect(mockState.cellData[cellId4].config).toEqual({
      hide_code: true,
      disabled: true,
    });
  });

  it("should handle single column", () => {
    const cellId1 = CellId.create();
    const mockState: NotebookState = {
      cellIds: MultiColumn.from([[cellId1]]),
      cellData: {
        [cellId1]: {
          id: cellId1,
          config: { hide_code: false, disabled: false },
        } as CellData,
      },
      cellRuntime: {},
      cellHandles: {},
      history: [],
      scrollKey: null,
      cellLogs: [],
    };

    const result = getCellConfigs(mockState);
    expect(result).toEqual([
      { hide_code: false, disabled: false, column: null },
    ]);
  });

  it("should handle empty notebook state", () => {
    const mockState: NotebookState = {
      cellIds: MultiColumn.from([]),
      cellData: {},
      cellRuntime: {},
      cellHandles: {},
      history: [],
      scrollKey: null,
      cellLogs: [],
    };

    const result = getCellConfigs(mockState);

    expect(result).toEqual([]);
  });
});

describe("staleCellIds", () => {
  it("should return cell IDs that have not been instantiated when auto-instantiate is false", () => {
    const state: NotebookState = {
      cellIds: MultiColumn.from([["cell1", "cell2"]]),
      cellData: {
        cell1: {
          lastExecutionTime: null,
          edited: false,
          config: { disabled: false },
        },
        cell2: {
          lastExecutionTime: 123,
          edited: false,
          config: { disabled: false },
        },
      },
      cellRuntime: {
        cell1: {
          runElapsedTimeMs: null,
          status: "idle",
          errored: false,
          interrupted: false,
          stopped: false,
          staleInputs: false,
        },
        cell2: {
          runElapsedTimeMs: 456,
          status: "idle",
          errored: false,
          interrupted: false,
          stopped: false,
          staleInputs: false,
        },
      },
    } as any;

    const result = staleCellIds(state);

    expect(result).toEqual(["cell1"]);
  });

  it("should use lastExecutionTime when runElapsedTimeMs is null", () => {
    const state: NotebookState = {
      cellIds: MultiColumn.from([["cell1", "cell2"]]),
      cellData: {
        cell1: {
          lastExecutionTime: null,
          edited: false,
          config: { disabled: false },
        },
        cell2: {
          lastExecutionTime: 123,
          edited: false,
          config: { disabled: false },
        },
      },
      cellRuntime: {
        cell1: {
          runElapsedTimeMs: null,
          status: "idle",
          errored: false,
          interrupted: false,
          stopped: false,
          staleInputs: false,
        },
        cell2: {
          runElapsedTimeMs: null,
          status: "idle",
          errored: false,
          interrupted: false,
          stopped: false,
          staleInputs: false,
        },
      },
    } as any;

    const result = staleCellIds(state);

    expect(result).toEqual(["cell1"]);
  });

  it("should return cell IDs that are edited", () => {
    const state: NotebookState = {
      cellIds: MultiColumn.from([["cell1", "cell2"]]),
      cellData: {
        cell1: {
          lastExecutionTime: 123,
          edited: true,
          config: { disabled: false },
        },
        cell2: {
          lastExecutionTime: 123,
          edited: false,
          config: { disabled: false },
        },
      },
      cellRuntime: {
        cell1: {
          runElapsedTimeMs: 456,
          status: "idle",
          errored: false,
          interrupted: false,
          stopped: false,
          staleInputs: false,
        },
        cell2: {
          runElapsedTimeMs: 456,
          status: "idle",
          errored: false,
          interrupted: false,
          stopped: false,
          staleInputs: false,
        },
      },
    } as any;

    const result = staleCellIds(state);

    expect(result).toEqual(["cell1"]);
  });

  it("should return cell IDs that are interrupted", () => {
    const state: NotebookState = {
      cellIds: MultiColumn.from([["cell1", "cell2"]]),
      cellData: {
        cell1: {
          lastExecutionTime: 123,
          edited: false,
          config: { disabled: false },
        },
        cell2: {
          lastExecutionTime: 123,
          edited: false,
          config: { disabled: false },
        },
      },
      cellRuntime: {
        cell1: {
          runElapsedTimeMs: 456,
          status: "idle",
          errored: false,
          interrupted: true,
          stopped: false,
          staleInputs: false,
        },
        cell2: {
          runElapsedTimeMs: 456,
          status: "idle",
          errored: false,
          interrupted: false,
          stopped: false,
          staleInputs: false,
        },
      },
    } as any;

    const result = staleCellIds(state);

    expect(result).toEqual(["cell1"]);
  });

  it("should not return cell IDs that are disabled", () => {
    const state: NotebookState = {
      cellIds: MultiColumn.from([["cell1", "cell2"]]),
      cellData: {
        cell1: {
          lastExecutionTime: 123,
          edited: false,
          config: { disabled: true },
        },
        cell2: {
          lastExecutionTime: 123,
          edited: false,
          config: { disabled: false },
        },
      },
      cellRuntime: {
        cell1: {
          runElapsedTimeMs: 456,
          status: "disabled-transitively",
          errored: false,
          interrupted: false,
          stopped: false,
          staleInputs: true,
        },
        cell2: {
          runElapsedTimeMs: 456,
          status: "idle",
          errored: false,
          interrupted: false,
          stopped: false,
          staleInputs: false,
        },
      },
    } as any;

    const result = staleCellIds(state);

    expect(result).toEqual([]);
  });
});

describe("isUninstantiated", () => {
  it("should return true if autoInstantiate is false and cell has not run", () => {
    const result = isUninstantiated({
      executionTime: null,
      status: "idle",
      errored: false,
      interrupted: false,
      stopped: false,
    });
    expect(result).toBe(true);
  });

  it("should return false if cell has run", () => {
    const result = isUninstantiated({
      executionTime: 123,
      status: "idle",
      errored: false,
      interrupted: false,
      stopped: false,
    });
    expect(result).toBe(false);
  });

  it("should return false if cell is currently queued or running", () => {
    let result = isUninstantiated({
      executionTime: null,
      status: "queued",
      errored: false,
      interrupted: false,
      stopped: false,
    });
    expect(result).toBe(false);

    result = isUninstantiated({
      executionTime: null,
      status: "running",
      errored: false,
      interrupted: false,
      stopped: false,
    });
    expect(result).toBe(false);
  });

  it("should return false if cell is in an error state", () => {
    let result = isUninstantiated({
      executionTime: null,
      status: "idle",
      errored: true,
      interrupted: false,
      stopped: false,
    });
    expect(result).toBe(false);

    result = isUninstantiated({
      executionTime: null,
      status: "idle",
      errored: false,
      interrupted: true,
      stopped: false,
    });
    expect(result).toBe(false);

    result = isUninstantiated({
      executionTime: null,
      status: "idle",
      errored: false,
      interrupted: false,
      stopped: true,
    });
    expect(result).toBe(false);
  });
});

describe("disabledCellIds", () => {
  it("should return only disabled cell IDs", () => {
    const cellId1 = CellId.create();
    const cellId2 = CellId.create();
    const cellId3 = CellId.create();

    const state: NotebookState = {
      cellIds: MultiColumn.from([[cellId1, cellId2, cellId3]]),
      cellData: {
        [cellId1]: { id: cellId1, config: { disabled: true } } as CellData,
        [cellId2]: { id: cellId2, config: { disabled: false } } as CellData,
        [cellId3]: { id: cellId3, config: { disabled: true } } as CellData,
      },
      cellRuntime: {} as Record<CellId, CellRuntimeState>,
      cellHandles: {},
      history: [],
      scrollKey: null,
      cellLogs: [],
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
      cellIds: MultiColumn.from([[cellId1, cellId2, cellId3]]),
      cellData: {
        [cellId1]: { id: cellId1, config: { disabled: true } } as CellData,
        [cellId2]: { id: cellId2, config: { disabled: false } } as CellData,
        [cellId3]: { id: cellId3, config: { disabled: false } } as CellData,
      },
      cellRuntime: {} as Record<CellId, CellRuntimeState>,
      cellHandles: {},
      history: [],
      scrollKey: null,
      cellLogs: [],
    };

    const result = enabledCellIds(state);
    expect(result).toEqual([cellId2, cellId3]);
  });
});
