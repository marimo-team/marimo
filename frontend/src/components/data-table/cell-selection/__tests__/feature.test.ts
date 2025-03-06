/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { describe, it, expect, vi } from "vitest";
import { CellSelectionFeature } from "../feature";
import type { Table, Row, Cell, Column } from "@tanstack/react-table";
import { INDEX_COLUMN_NAME } from "../../types";
import type { CellSelectionTableState } from "../types";

describe("CellSelectionFeature", () => {
  // Mock table setup
  const createMockTable = () => {
    const state: CellSelectionTableState = {
      cellSelection: [],
    };

    const table = {
      getState: () => state,
      setState: vi.fn((updater) => {
        const newState = updater(state);
        state.cellSelection = newState.cellSelection;
        return newState;
      }),
      options: {
        enableMultiCellSelection: true,
        onCellSelectionChange: vi.fn(),
      },
      setCellSelection: undefined as any,
    };

    // Initialize the table with the feature
    CellSelectionFeature.createTable?.(table as unknown as Table<any>);

    return { table, state };
  };

  const createMockCell = (rowId: string, columnId: string, table: any) => {
    // Create mock row
    const row: Partial<Row<any>> = {
      id: rowId,
      [INDEX_COLUMN_NAME]: rowId,
    } as any;

    // Create mock column
    const column: Partial<Column<any>> = {
      id: columnId,
    };

    // Create mock cell
    const cell: Partial<Cell<any, unknown>> = {};

    // Initialize the cell with the feature
    CellSelectionFeature.createCell?.(
      cell as Cell<any, unknown>,
      column as Column<any>,
      row as Row<any>,
      table as Table<any>,
    );

    return { cell, row, column };
  };

  describe("toggleSelected", () => {
    it("should add cell to selection when not selected", () => {
      const { table } = createMockTable();
      const { cell } = createMockCell("row1", "col1", table);

      cell.toggleSelected!(true);

      expect(table.setState).toHaveBeenCalled();
      expect(table.getState().cellSelection).toEqual([
        { rowId: "row1", columnName: "col1" },
      ]);
    });

    it("should remove only the specific cell from selection", () => {
      const { table, state } = createMockTable();

      // Pre-populate with multiple cells in the selection
      state.cellSelection = [
        { rowId: "row1", columnName: "col1" },
        { rowId: "row1", columnName: "col2" },
        { rowId: "row2", columnName: "col1" },
      ];

      const { cell } = createMockCell("row1", "col1", table);

      // Deselect the cell
      cell.toggleSelected!(false);

      // It should only remove row1/col1, leaving the other cells
      expect(table.getState().cellSelection).toEqual([
        { rowId: "row1", columnName: "col2" },
        { rowId: "row2", columnName: "col1" },
      ]);
    });

    it("should preserve other cells in the same row when deselecting a cell", () => {
      const { table, state } = createMockTable();

      // Pre-populate with multiple cells in the same row
      state.cellSelection = [
        { rowId: "row1", columnName: "col1" },
        { rowId: "row1", columnName: "col2" },
        { rowId: "row1", columnName: "col3" },
      ];

      const { cell } = createMockCell("row1", "col1", table);

      // Deselect the cell
      cell.toggleSelected!(false);

      // It should only remove row1/col1, preserving other cells in row1
      expect(table.getState().cellSelection).toEqual([
        { rowId: "row1", columnName: "col2" },
        { rowId: "row1", columnName: "col3" },
      ]);
    });

    it("should preserve other cells in the same column when deselecting a cell", () => {
      const { table, state } = createMockTable();

      // Pre-populate with multiple cells in the same column
      state.cellSelection = [
        { rowId: "row1", columnName: "col1" },
        { rowId: "row2", columnName: "col1" },
        { rowId: "row3", columnName: "col1" },
      ];

      const { cell } = createMockCell("row1", "col1", table);

      // Deselect the cell
      cell.toggleSelected!(false);

      // It should only remove row1/col1, preserving other cells in col1
      expect(table.getState().cellSelection).toEqual([
        { rowId: "row2", columnName: "col1" },
        { rowId: "row3", columnName: "col1" },
      ]);
    });

    it("should toggle cell selection correctly", () => {
      const { table } = createMockTable();
      const { cell } = createMockCell("row1", "col1", table);

      // First select
      cell.toggleSelected!();

      expect(table.getState().cellSelection).toEqual([
        { rowId: "row1", columnName: "col1" },
      ]);

      // Then deselect
      cell.toggleSelected!();

      expect(table.getState().cellSelection).toEqual([]);
    });
  });
});
