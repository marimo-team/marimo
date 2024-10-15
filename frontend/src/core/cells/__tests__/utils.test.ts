/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect } from "vitest";
import { getCellConfigs, type NotebookState } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import { MultiColumn } from "@/utils/id-tree";
import type { CellData, CellRuntimeState } from "@/core/cells/types";

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
      column: 0,
    });
    expect(mockState.cellData[cellId2].config).toEqual({
      hide_code: true,
      disabled: false,
    });
    expect(mockState.cellData[cellId3].config).toEqual({
      hide_code: false,
      disabled: true,
      column: 1,
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
