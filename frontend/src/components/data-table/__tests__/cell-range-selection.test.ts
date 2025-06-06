/* Copyright 2024 Marimo. All rights reserved. */

import { describe, it, expect } from "vitest";
import type { Table } from "@tanstack/react-table";
import {
  type SelectedCells,
  getCellValues,
  getCellsBetween,
  exportedForTesting,
  type SelectedCell,
} from "../hooks/use-cell-range-selection";

const { getUniqueCellId } = exportedForTesting;

describe("getCellsBetween", () => {
  it("should return empty array when cells are not found", () => {
    const mockTable = {
      getRow: () => ({
        getAllCells: () => [],
      }),
      getRowModel: () => ({
        rows: [],
      }),
    } as unknown as Table<unknown>;

    const cell1: SelectedCell = {
      rowId: "row1",
      columnId: "col1",
      cellId: "cell1",
    };
    const cell2: SelectedCell = {
      rowId: "row2",
      columnId: "col2",
      cellId: "cell2",
    };

    expect(getCellsBetween(mockTable, cell1, cell2)).toEqual(new Map());
  });

  it("should return cells in a single row", () => {
    const mockRow = {
      id: "row1",
      getAllCells: () => [
        {
          id: "cell1",
          column: { id: "col1", getIndex: () => 0 },
          row: { id: "row1" },
        },
        {
          id: "cell2",
          column: { id: "col2", getIndex: () => 1 },
          row: { id: "row1" },
        },
        {
          id: "cell3",
          column: { id: "col3", getIndex: () => 2 },
          row: { id: "row1" },
        },
      ],
    };
    const mockTable = {
      getRow: () => ({
        getAllCells: () => mockRow.getAllCells(),
      }),
      getRowModel: () => ({
        rows: [mockRow],
      }),
      getAllColumns: () => [{ id: "col1" }, { id: "col2" }, { id: "col3" }],
    } as unknown as Table<unknown>;

    const cell1: SelectedCell = {
      rowId: "row1",
      columnId: "col1",
      cellId: "cell1",
    };
    const cell2: SelectedCell = {
      rowId: "row1",
      columnId: "col3",
      cellId: "cell3",
    };

    const result = getCellsBetween(mockTable, cell1, cell2);
    expect(result.size).toBe(3);
    const cell1Id = getUniqueCellId(cell1.rowId, cell1.columnId, cell1.cellId);
    const cell2Id = getUniqueCellId(cell2.rowId, cell2.columnId, cell2.cellId);
    const cell3Id = getUniqueCellId(cell2.rowId, cell2.columnId, cell2.cellId);
    expect(result.get(cell1Id)).toEqual(cell1);
    expect(result.get(cell2Id)).toEqual(cell2);
    expect(result.get(cell3Id)).toEqual(cell2);
  });

  it("should return cells in a rectangular selection", () => {
    const mockRow1 = {
      id: "row1",
      getAllCells: () => [
        {
          id: "cell1",
          column: { id: "col1", getIndex: () => 0 },
          row: { id: "row1" },
        },
        {
          id: "cell2",
          column: { id: "col2", getIndex: () => 1 },
          row: { id: "row1" },
        },
      ],
    };
    const mockRow2 = {
      id: "row2",
      getAllCells: () => [
        {
          id: "cell3",
          column: { id: "col1", getIndex: () => 0 },
          row: { id: "row2" },
        },
        {
          id: "cell4",
          column: { id: "col2", getIndex: () => 1 },
          row: { id: "row2" },
        },
      ],
    };
    const mockTable = {
      getRow: (id: string) => ({
        getAllCells: () =>
          id === "row1" ? mockRow1.getAllCells() : mockRow2.getAllCells(),
      }),
      getRowModel: () => ({
        rows: [mockRow1, mockRow2],
      }),
      getAllColumns: () => [{ id: "col1" }, { id: "col2" }],
    } as unknown as Table<unknown>;

    const cell1: SelectedCell = {
      rowId: "row1",
      columnId: "col1",
      cellId: "cell1",
    };
    const cell2: SelectedCell = {
      rowId: "row2",
      columnId: "col2",
      cellId: "cell4",
    };

    const result = getCellsBetween(mockTable, cell1, cell2);
    const cell1Id = getUniqueCellId(cell1.rowId, cell1.columnId, cell1.cellId);
    const cell2Id = getUniqueCellId(cell2.rowId, cell2.columnId, cell2.cellId);
    expect(result.get(cell1Id)).toEqual(cell1);
    expect(result.get(cell2Id)).toEqual(cell2);
  });

  it("should handle reverse selection (bottom-right to top-left)", () => {
    const mockRow1 = {
      id: "row1",
      getAllCells: () => [
        {
          id: "cell1",
          column: { id: "col1", getIndex: () => 0 },
          row: { id: "row1" },
        },
        {
          id: "cell2",
          column: { id: "col2", getIndex: () => 1 },
          row: { id: "row1" },
        },
      ],
    };
    const mockRow2 = {
      id: "row2",
      getAllCells: () => [
        {
          id: "cell3",
          column: { id: "col1", getIndex: () => 0 },
          row: { id: "row2" },
        },
        {
          id: "cell4",
          column: { id: "col2", getIndex: () => 1 },
          row: { id: "row2" },
        },
      ],
    };
    const mockTable = {
      getRow: (id: string) => ({
        getAllCells: () =>
          id === "row1" ? mockRow1.getAllCells() : mockRow2.getAllCells(),
      }),
      getRowModel: () => ({
        rows: [mockRow1, mockRow2],
      }),
      getAllColumns: () => [{ id: "col1" }, { id: "col2" }],
    } as unknown as Table<unknown>;

    const cell1: SelectedCell = {
      rowId: "row2",
      columnId: "col2",
      cellId: "cell4",
    };
    const cell2: SelectedCell = {
      rowId: "row1",
      columnId: "col1",
      cellId: "cell1",
    };

    const result = getCellsBetween(mockTable, cell1, cell2);
    const cell1Id = getUniqueCellId(cell1.rowId, cell1.columnId, cell1.cellId);
    const cell2Id = getUniqueCellId(cell2.rowId, cell2.columnId, cell2.cellId);
    const cell3Id = getUniqueCellId(cell1.rowId, cell1.columnId, cell1.cellId);
    const cell4Id = getUniqueCellId(cell1.rowId, cell1.columnId, cell1.cellId);
    expect(result.get(cell1Id)).toEqual(cell1);
    expect(result.get(cell2Id)).toEqual(cell2);
    expect(result.get(cell3Id)).toEqual(cell1);
    expect(result.get(cell4Id)).toEqual(cell1);
  });
});

describe("getCellValues", () => {
  it("should return empty string for empty cells array", () => {
    const mockTable = {
      getRow: () => ({
        getAllCells: () => [],
      }),
    } as unknown as Table<unknown>;

    expect(getCellValues(mockTable, new Map())).toBe("");
  });

  it("should format cell values with tabs and newlines", () => {
    const mockTable = {
      getRow: (id: string) => ({
        getAllCells: () => [
          { id: "cell1", getValue: () => "value1", column: { id: "col1" } },
          { id: "cell2", getValue: () => "value2", column: { id: "col2" } },
        ],
      }),
    } as unknown as Table<unknown>;

    const cells: SelectedCells = new Map([
      ["cell1", { rowId: "row1", columnId: "col1", cellId: "cell1" }],
      ["cell2", { rowId: "row1", columnId: "col2", cellId: "cell2" }],
    ]);

    expect(getCellValues(mockTable, cells)).toBe("value1\tvalue2");
  });

  it("should handle multiple rows", () => {
    const mockTable = {
      getRow: (id: string) => ({
        getAllCells: () => [
          {
            id: id === "row1" ? "cell1" : "cell3",
            getValue: () => (id === "row1" ? "value1" : "value3"),
            column: { id: "col1" },
          },
          {
            id: id === "row1" ? "cell2" : "cell4",
            getValue: () => (id === "row1" ? "value2" : "value4"),
            column: { id: "col2" },
          },
        ],
      }),
    } as unknown as Table<unknown>;

    const cells: SelectedCells = new Map([
      ["cell1", { rowId: "row1", columnId: "col1", cellId: "cell1" }],
      ["cell2", { rowId: "row1", columnId: "col2", cellId: "cell2" }],
      ["cell3", { rowId: "row2", columnId: "col1", cellId: "cell3" }],
      ["cell4", { rowId: "row2", columnId: "col2", cellId: "cell4" }],
    ]);

    expect(getCellValues(mockTable, cells)).toBe(
      "value1\tvalue2\nvalue3\tvalue4",
    );
  });
});
