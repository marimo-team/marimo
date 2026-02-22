/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { SELECT_COLUMN_ID } from "../../types";
import {
  countDataCellsInSelection,
  getCellsBetween,
  getCellValues,
  getNumericValuesFromSelectedCells,
} from "../utils";
import {
  createMockCell,
  createMockColumn,
  createMockRow,
  createMockTable,
  createSelectedCell,
} from "./test-utils";

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

describe("getNumericValuesFromSelectedCells", () => {
  it("should return empty array for empty selection", () => {
    const mockTable = createMockTable([], []);
    const result = getNumericValuesFromSelectedCells(mockTable, new Set());
    expect(result).toEqual([]);
  });

  it("should ignore select checkbox in tables", () => {
    const cell = createMockCell(`row_${SELECT_COLUMN_ID}`, 10);
    const row = createMockRow("0", [cell]);
    const table = createMockTable([row], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set([`row_${SELECT_COLUMN_ID}`]),
    );
    expect(result).toEqual([]);
  });

  it("should extract numeric values from number cells", () => {
    const cell1 = createMockCell("0_0", 10);
    const cell2 = createMockCell("0_1", 20);
    const row = createMockRow("0", [cell1, cell2]);
    const table = createMockTable([row], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set(["0_0", "0_1"]),
    );
    expect(result).toEqual([10, 20]);
  });

  it("should parse string numbers to numeric values", () => {
    const cell1 = createMockCell("0_0", "42");
    const cell2 = createMockCell("0_1", "3.14");
    const row = createMockRow("0", [cell1, cell2]);
    const table = createMockTable([row], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set(["0_0", "0_1"]),
    );
    expect(result).toEqual([42, 3.14]);
  });

  it("should skip non-numeric values", () => {
    const cell1 = createMockCell("0_0", 10);
    const cell2 = createMockCell("0_1", "abc");
    const cell3 = createMockCell("0_2", undefined);
    const row = createMockRow("0", [cell1, cell2, cell3]);
    const table = createMockTable([row], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set(["0_0", "0_1", "0_2"]),
    );
    expect(result).toEqual([10]);
  });

  it("should skip NaN and Infinity", () => {
    const cell1 = createMockCell("0_0", 5);
    const cell2 = createMockCell("0_1", NaN);
    const cell3 = createMockCell("0_2", Infinity);
    const row = createMockRow("0", [cell1, cell2, cell3]);
    const table = createMockTable([row], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set(["0_0", "0_1", "0_2"]),
    );
    expect(result).toEqual([5]);
  });

  it("should skip booleans (not treat as 1 or 0)", () => {
    const cell1 = createMockCell("0_0", 10);
    const cell2 = createMockCell("0_1", true);
    const cell3 = createMockCell("0_2", false);
    const row = createMockRow("0", [cell1, cell2, cell3]);
    const table = createMockTable([row], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set(["0_0", "0_1", "0_2"]),
    );
    expect(result).toEqual([10]);
  });

  it("should skip null and empty string (not treat as 0)", () => {
    const cell1 = createMockCell("0_0", 10);
    const cell2 = createMockCell("0_1", null);
    const cell3 = createMockCell("0_2", "");
    const row = createMockRow("0", [cell1, cell2, cell3]);
    const table = createMockTable([row], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set(["0_0", "0_1", "0_2"]),
    );
    expect(result).toEqual([10]);
  });

  it("should include string '0' as numeric zero", () => {
    const cell1 = createMockCell("0_0", "0");
    const cell2 = createMockCell("0_1", 0);
    const row = createMockRow("0", [cell1, cell2]);
    const table = createMockTable([row], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set(["0_0", "0_1"]),
    );
    expect(result).toEqual([0, 0]);
  });

  it("should skip -Infinity", () => {
    const cell1 = createMockCell("0_0", 5);
    const cell2 = createMockCell("0_1", -Infinity);
    const row = createMockRow("0", [cell1, cell2]);
    const table = createMockTable([row], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set(["0_0", "0_1"]),
    );
    expect(result).toEqual([5]);
  });

  it("should skip objects", () => {
    const cell1 = createMockCell("0_0", 5);
    const cell2 = createMockCell("0_1", { x: 1 });
    const cell3 = createMockCell("0_2", [1, 2]);
    const row = createMockRow("0", [cell1, cell2, cell3]);
    const table = createMockTable([row], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set(["0_0", "0_1", "0_2"]),
    );
    expect(result).toEqual([5]);
  });

  it("should handle missing cells gracefully", () => {
    const cell = createMockCell("0_0", 100);
    const row = createMockRow("0", [cell]);
    const table = createMockTable([row], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set(["0_0", "0_999", "999_0"]),
    );
    expect(result).toEqual([100]);
  });

  it("should return multiple numeric cells across rows", () => {
    const row1 = createMockRow("0", [
      createMockCell("0_0", 1),
      createMockCell("0_1", 2),
    ]);
    const row2 = createMockRow("1", [
      createMockCell("1_0", 3),
      createMockCell("1_1", 4),
    ]);
    const table = createMockTable([row1, row2], []);
    const result = getNumericValuesFromSelectedCells(
      table,
      new Set(["0_0", "0_1", "1_0", "1_1"]),
    );
    expect(result).toEqual([1, 2, 3, 4]);
  });
});

describe("countDataCellsInSelection", () => {
  it("should return 0 for empty selection", () => {
    expect(countDataCellsInSelection(new Set())).toBe(0);
  });

  it("should count only non-checkbox cells", () => {
    expect(countDataCellsInSelection(new Set(["0_0", "0_1", "1_0"]))).toBe(3);
  });

  it("should exclude select checkbox column cells", () => {
    const selectCellId = `0_${SELECT_COLUMN_ID}`;
    expect(
      countDataCellsInSelection(new Set([selectCellId, "0_0", "0_1"])),
    ).toBe(2);
  });

  it("should return 0 when only checkbox cells are selected", () => {
    const selectCellId1 = `0_${SELECT_COLUMN_ID}`;
    const selectCellId2 = `1_${SELECT_COLUMN_ID}`;
    expect(
      countDataCellsInSelection(new Set([selectCellId1, selectCellId2])),
    ).toBe(0);
  });
});
