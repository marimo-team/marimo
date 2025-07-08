/* Copyright 2024 Marimo. All rights reserved. */

import type { Cell, Column, Row, Table } from "@tanstack/react-table";
import { describe, expect, it, vi } from "vitest";
import { SELECT_COLUMN_ID } from "../../types";
import type { SelectedCell } from "../atoms";
import { getCellsBetween, getCellValues } from "../utils";

function createMockCell(id: string, value: unknown): Cell<unknown, unknown> {
  return {
    id,
    getValue: () => value,
    column: {} as Column<unknown>,
    row: {} as Row<unknown>,
    getContext: vi.fn(),
    renderValue: vi.fn(),
  } as unknown as Cell<unknown, unknown>;
}

function createMockColumn(id: string): Column<unknown> {
  return {
    id: id,
    getIndex: () => Number.parseInt(id),
  } as unknown as Column<unknown>;
}

function createMockRow(
  id: string,
  cells: Array<Cell<unknown, unknown>>,
): Row<unknown> {
  return {
    id,
    index: Number.parseInt(id),
    getAllCells: () => cells,
    original: {},
    depth: 0,
    subRows: [],
    getVisibleCells: vi.fn(),
    getValue: vi.fn(),
    getUniqueValues: vi.fn(),
    renderValue: vi.fn(),
  } as unknown as Row<unknown>;
}

function createMockTable(
  rows: Array<Row<unknown>>,
  columns: Array<Column<unknown>>,
): Table<unknown> {
  return {
    getRow: (id: string) => rows.find((row) => row.id === id),
    getRowModel: () => ({ rows }),
    getColumn: (columnId: string) => columns.find((col) => col.id === columnId),
    getAllColumns: () => columns,
  } as unknown as Table<unknown>;
}

function createSelectedCell(rowId: string, columnId: string): SelectedCell {
  return {
    rowId,
    columnId,
    cellId: `${rowId}_${columnId}`,
  };
}

describe("getCellValues", () => {
  it("should return empty string for empty selection", () => {
    const mockTable = createMockTable([], []);
    const result = getCellValues(mockTable, new Set());
    expect(result).toBe("");
  });

  it("should ignore select checkbox in tables", () => {
    const cell = createMockCell(`row_${SELECT_COLUMN_ID}`, "test");
    const row = createMockRow("0", [cell]);
    const table = createMockTable([row], []);

    const result = getCellValues(table, new Set());
    expect(result).toBe("");
  });

  it("should return single cell value", () => {
    const cell = createMockCell("0_0", "test");
    const row = createMockRow("0", [cell]);
    const table = createMockTable([row], []);

    const result = getCellValues(table, new Set(["0_0"]));
    expect(result).toBe("test");
  });

  it("should return multiple cells from same row separated by tabs", () => {
    const cell1 = createMockCell("0_0", "value1");
    const cell2 = createMockCell("0_1", "value2");
    const row = createMockRow("0", [cell1, cell2]);
    const table = createMockTable([row], []);

    const result = getCellValues(table, new Set(["0_0", "0_1"]));
    expect(result).toBe("value1\tvalue2");
  });

  it("should return multiple rows separated by newlines", () => {
    const cell1 = createMockCell("0_0", "row1");
    const cell2 = createMockCell("1_0", "row2");
    const row1 = createMockRow("0", [cell1]);
    const row2 = createMockRow("1", [cell2]);
    const table = createMockTable([row1, row2], []);

    const result = getCellValues(table, new Set(["0_0", "1_0"]));
    expect(result).toBe("row1\nrow2");
  });

  it("should handle missing cells gracefully", () => {
    const cell = createMockCell("0_0", "test");
    const row = createMockRow("0", [cell]);
    const table = createMockTable([row], []);

    const result = getCellValues(table, new Set(["0_0", "0_999", "999_0"]));
    expect(result).toBe("test");
  });

  it("should handle missing cells in existing rows", () => {
    const cell1 = createMockCell("0_0", "test1");
    const cell2 = createMockCell("0_1", "test2");
    const row = createMockRow("0", [cell1, cell2]);
    const table = createMockTable([row], []);

    // Should only return values for cells that exist
    const result = getCellValues(table, new Set(["0_0", "0_1", "0_999"]));
    expect(result).toBe("test1\ttest2");
  });

  it("should handle complex data types", () => {
    const cell1 = createMockCell("0_0", { name: "test" });
    const cell2 = createMockCell("0_1", null);
    const cell3 = createMockCell("0_2", undefined);
    const row = createMockRow("0", [cell1, cell2, cell3]);
    const table = createMockTable([row], []);

    const result = getCellValues(table, new Set(["0_0", "0_1", "0_2"]));
    expect(result).toBe('{"name":"test"}\tnull\tundefined');
  });
});

describe("getCellsBetween", () => {
  it("should return empty array when start row is not found", () => {
    const cell = createMockCell("0_0", "test");
    const rows = [createMockRow("0", [cell])];
    const table = createMockTable(rows, []);

    const cellStart = createSelectedCell("999", "0"); // non existent row
    const cellEnd = createSelectedCell("0", "0");

    const result = getCellsBetween(table, cellStart, cellEnd);
    expect(result).toEqual([]);
  });

  it("should return empty array when end row is not found", () => {
    const cell = createMockCell("0_0", "test");
    const rows = [createMockRow("0", [cell])];
    const table = createMockTable(rows, []);

    const cellStart = createSelectedCell("0", "0");
    const cellEnd = createSelectedCell("999", "0"); // non existent row

    const result = getCellsBetween(table, cellStart, cellEnd);
    expect(result).toEqual([]);
  });

  it("should return single cell when start and end are the same", () => {
    const cell = createMockCell("0_0", "test");
    const rows = [createMockRow("0", [cell])];
    const columns = [createMockColumn("0")];
    const table = createMockTable(rows, columns);

    const cellStart = createSelectedCell("0", "0");
    const cellEnd = createSelectedCell("0", "0");

    const result = getCellsBetween(table, cellStart, cellEnd);
    expect(result).toEqual(["0_0"]);
  });

  it("should return cells in a single row range", () => {
    const cell1 = createMockCell("0_0", "test1");
    const cell2 = createMockCell("0_1", "test2");
    const cell3 = createMockCell("0_2", "test3");
    const cell4 = createMockCell("0_3", "test4");
    const cell5 = createMockCell("0_4", "test5");
    const rows = [createMockRow("0", [cell1, cell2, cell3, cell4, cell5])];
    const columns = [
      createMockColumn("0"),
      createMockColumn("1"),
      createMockColumn("2"),
      createMockColumn("3"),
      createMockColumn("4"),
    ];
    const table = createMockTable(rows, columns);

    const startCell = createSelectedCell("0", "1");
    const endCell = createSelectedCell("0", "3");

    const result = getCellsBetween(table, startCell, endCell);
    expect(result).toEqual(["0_1", "0_2", "0_3"]);
  });

  it("should return cells in a single column range", () => {
    const rows = [
      createMockRow("0", [
        createMockCell("0_0", "test1"),
        createMockCell("0_1", "test2"),
        createMockCell("0_2", "test3"),
      ]),
      createMockRow("1", [
        createMockCell("1_0", "test4"),
        createMockCell("1_1", "test5"),
        createMockCell("1_2", "test6"),
      ]),
      createMockRow("2", [
        createMockCell("2_0", "test7"),
        createMockCell("2_1", "test8"),
        createMockCell("2_2", "test9"),
      ]),
    ];
    const columns = [
      createMockColumn("0"),
      createMockColumn("1"),
      createMockColumn("2"),
    ];
    const table = createMockTable(rows, columns);

    const cellStart = createSelectedCell("0", "1");
    const cellEnd = createSelectedCell("2", "1");

    const result = getCellsBetween(table, cellStart, cellEnd);
    expect(result).toEqual(["0_1", "1_1", "2_1"]);
  });

  it("should return cells in a rectangular range", () => {
    const rows = [
      createMockRow("0", [
        createMockCell("0_0", "test1"),
        createMockCell("0_1", "test2"),
        createMockCell("0_2", "test3"),
      ]),
      createMockRow("1", [
        createMockCell("1_0", "test4"),
        createMockCell("1_1", "test5"),
        createMockCell("1_2", "test6"),
      ]),
      createMockRow("2", [
        createMockCell("2_0", "test7"),
        createMockCell("2_1", "test8"),
        createMockCell("2_2", "test9"),
      ]),
    ];
    const columns = [
      createMockColumn("0"),
      createMockColumn("1"),
      createMockColumn("2"),
    ];
    const table = createMockTable(rows, columns);

    const cellStart = createSelectedCell("0", "1");
    const cellEnd = createSelectedCell("2", "2");

    const result = getCellsBetween(table, cellStart, cellEnd);
    expect(result).toEqual(["0_1", "0_2", "1_1", "1_2", "2_1", "2_2"]);
  });

  it("should work when end is before start (reverse selection)", () => {
    const rows = [
      createMockRow("0", [
        createMockCell("0_0", "test1"),
        createMockCell("0_1", "test2"),
        createMockCell("0_2", "test3"),
      ]),
      createMockRow("1", [
        createMockCell("1_0", "test4"),
        createMockCell("1_1", "test5"),
        createMockCell("1_2", "test6"),
      ]),
    ];
    const columns = [
      createMockColumn("0"),
      createMockColumn("1"),
      createMockColumn("2"),
    ];
    const table = createMockTable(rows, columns);

    const cellStart = createSelectedCell("1", "2");
    const cellEnd = createSelectedCell("0", "0");

    const result = getCellsBetween(table, cellStart, cellEnd);
    expect(result).toEqual(["0_0", "0_1", "0_2", "1_0", "1_1", "1_2"]);
  });

  it("should handle missing cells gracefully", () => {
    const rows = [
      createMockRow("0", [
        createMockCell("0_0", "test1"),
        createMockCell("0_1", "test2"),
        createMockCell("0_2", "test3"),
      ]),
    ];
    const columns = [
      createMockColumn("0"),
      createMockColumn("1"),
      createMockColumn("2"),
    ];
    const table = createMockTable(rows, columns);

    const cellStart = createSelectedCell("0", "999");
    const cellEnd = createSelectedCell("0", "0");

    const result = getCellsBetween(table, cellStart, cellEnd);
    expect(result).toEqual([]);
  });
});
