/* Copyright 2024 Marimo. All rights reserved. */
import { describe, it, expect, vi } from "vitest";
import { CellHeatmapFeature } from "../cell-heatmap/feature";
import {
  type Column,
  createTable,
  getCoreRowModel,
} from "@tanstack/react-table";

describe("CellHeatmapFeature", () => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let state: any = {
    columnHeatmap: {
      value: true,
    },
    cachedMaxValue: null,
    cachedMinValue: null,
  };

  const mockTable = createTable({
    _features: [CellHeatmapFeature],
    data: [
      { id: 1, value: 10 },
      { id: 2, value: 20 },
      { id: 3, value: 30 },
    ],
    state: state,
    onStateChange: (updater) => {
      state = typeof updater === "function" ? updater(state) : updater;
    },
    columns: [
      { id: "id", accessorKey: "id" },
      { id: "value", accessorKey: "value" },
    ],
    getCoreRowModel: getCoreRowModel(),
    renderFallbackValue: null,
  });

  it("should initialize with correct default state", () => {
    const initialState = CellHeatmapFeature.getInitialState?.();
    expect(initialState).toEqual({
      columnHeatmap: {},
      cachedMaxValue: null,
      cachedMinValue: null,
    });
  });

  it("should provide default options", () => {
    const options = CellHeatmapFeature.getDefaultOptions?.(mockTable) || {};
    expect(options.enableCellHeatmap).toBe(true);
    expect(typeof options.onColumnHeatmapChange).toBe("function");
  });

  it("should add getGlobalHeatmap and toggleGlobalHeatmap methods to table", () => {
    CellHeatmapFeature.createTable?.(mockTable);
    expect(typeof mockTable.getGlobalHeatmap).toBe("function");
    expect(typeof mockTable.toggleGlobalHeatmap).toBe("function");
  });

  it("should add methods to column", () => {
    const mockColumn = { id: "test" } as Column<number>;
    CellHeatmapFeature.createColumn?.(mockColumn, mockTable);
    expect(typeof mockColumn.getCellHeatmapColor).toBe("function");
    expect(typeof mockColumn.toggleColumnHeatmap).toBe("function");
    expect(typeof mockColumn.getIsColumnHeatmapEnabled).toBe("function");
  });

  it("should calculate correct heatmap color", () => {
    const mockColumn = { id: "value" } as Column<number>;
    CellHeatmapFeature.createColumn?.(mockColumn, mockTable);
    mockTable.setState((prev) => {
      prev.columnHeatmap = { value: true };
      return prev;
    });

    const color = mockColumn.getCellHeatmapColor?.(20);
    expect(color).toMatch(/^hsla\(\d+(?:,\s*\d+%){2},\s*0\.6\)$/);
  });

  it("should toggle column heatmap", () => {
    const mockColumn = { id: "value" } as Column<number>;
    const onColumnHeatmapChange = vi.fn();
    mockTable.options.onColumnHeatmapChange = onColumnHeatmapChange;

    CellHeatmapFeature.createColumn?.(mockColumn, mockTable);
    mockColumn.toggleColumnHeatmap?.();

    expect(onColumnHeatmapChange).toHaveBeenCalled();
  });

  it("should handle global heatmap toggle", () => {
    CellHeatmapFeature.createTable?.(mockTable);
    const onColumnHeatmapChange = vi.fn();
    mockTable.options.onColumnHeatmapChange = onColumnHeatmapChange;

    mockTable.toggleGlobalHeatmap?.();
    expect(onColumnHeatmapChange).toHaveBeenCalled();
  });
});
