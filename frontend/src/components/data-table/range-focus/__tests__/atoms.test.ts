/* Copyright 2024 Marimo. All rights reserved. */

import type { Cell, Row, Table } from "@tanstack/react-table";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { visibleForTesting } from "../atoms";

// Mock dependencies
vi.mock("@/utils/copy", () => ({
  copyToClipboard: vi.fn(),
}));

vi.mock("../utils", async (importOriginal) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const original = (await importOriginal()) as any;
  return {
    ...original,
    getCellsBetween: vi.fn().mockReturnValue(["row1_col1", "row1_col2"]),
    getCellValues: vi.fn().mockReturnValue("mocked cell values"),
  };
});

import { copyToClipboard } from "@/utils/copy";
import type { CellSelectionState, SelectedCell } from "../atoms";
import {
  createCellCopiedAtom,
  createCellSelectedAtom,
  createCellStateAtom,
} from "../atoms";
import { getCellsBetween, getCellValues } from "../utils";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type T = any;

// Create mock table and cells
function createMockCell(
  rowId: string,
  columnId: string,
  rowIndex = 0,
  columnIndex = 0,
): Cell<T, unknown> {
  const cell = {
    id: `${rowId}_${columnId}`, // Use underscore to match actual format
    row: {
      id: rowId,
      index: rowIndex,
      getAllCells: vi.fn(),
    } as unknown as Row<T>,
    column: {
      id: columnId,
      getIndex: () => columnIndex,
    },
    getValue: () => `value-${rowId}-${columnId}`,
  } as unknown as Cell<T, unknown>;

  return cell;
}

function createMockTable(): Table<T> {
  const rows = [
    {
      id: "row1",
      index: 0,
      getAllCells: () => [
        createMockCell("row1", "col1", 0, 0),
        createMockCell("row1", "col2", 0, 1),
        createMockCell("row1", "col3", 0, 2),
      ],
    },
    {
      id: "row2",
      index: 1,
      getAllCells: () => [
        createMockCell("row2", "col1", 1, 0),
        createMockCell("row2", "col2", 1, 1),
        createMockCell("row2", "col3", 1, 2),
      ],
    },
    {
      id: "row3",
      index: 2,
      getAllCells: () => [
        createMockCell("row3", "col1", 2, 0),
        createMockCell("row3", "col2", 2, 1),
        createMockCell("row3", "col3", 2, 2),
      ],
    },
  ];

  const table = {
    getRowModel: () => ({ rows }),
    getRow: (rowId: string) => rows.find((row) => row.id === rowId),
  } as unknown as Table<T>;

  return table;
}

describe("cell selection atoms", () => {
  let state: CellSelectionState;
  let mockTable: Table<T>;
  let actions: ReturnType<typeof visibleForTesting.createActions>;

  beforeEach(() => {
    vi.clearAllMocks();
    mockTable = createMockTable();

    actions = visibleForTesting.createActions((action) => {
      state = visibleForTesting.reducer(state, action);
    });

    state = visibleForTesting.initialState();
  });

  describe("initial state", () => {
    it("should have empty initial state", () => {
      expect(state.selectedCells).toEqual(new Set());
      expect(state.copiedCells).toEqual(new Set());
      expect(state.selectedStartCell).toBeNull();
      expect(state.focusedCell).toBeNull();
      expect(state.isSelecting).toBe(false);
    });
  });

  describe("basic actions", () => {
    it("can set selected cells", () => {
      const selectedCells = new Set(["row1_col1", "row1_col2"]);

      actions.setSelectedCells(selectedCells);

      expect(state.selectedCells).toEqual(selectedCells);
    });

    it("can set selected start cell", () => {
      const startCell: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      actions.setSelectedStartCell(startCell);

      expect(state.selectedStartCell).toEqual(startCell);
    });

    it("can set focused cell", () => {
      const focusedCell: SelectedCell = {
        rowId: "row2",
        columnId: "col2",
        cellId: "row2_col2",
      };

      actions.setFocusedCell(focusedCell);

      expect(state.focusedCell).toEqual(focusedCell);
    });

    it("can set is selecting", () => {
      actions.setIsSelecting(true);
      expect(state.isSelecting).toBe(true);

      actions.setIsSelecting(false);
      expect(state.isSelecting).toBe(false);
    });

    it("can set copied cells", () => {
      const copiedCells = new Set(["row1_col1", "row2_col2"]);

      actions.setCopiedCells(copiedCells);

      expect(state.copiedCells).toEqual(copiedCells);
    });

    it("can clear selection", () => {
      // Set some initial state
      actions.setSelectedCells(new Set(["row1_col1"]));
      actions.setSelectedStartCell({
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      });
      actions.setFocusedCell({
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      });

      // Clear selection
      actions.clearSelection();

      expect(state.selectedCells).toEqual(new Set());
      expect(state.selectedStartCell).toBeNull();
      expect(state.focusedCell).toBeNull();
    });

    it("can select all cells", () => {
      actions.selectAllCells(mockTable);
      const allCells = mockTable
        .getRowModel()
        .rows.flatMap((row) => row.getAllCells().map((cell) => cell.id));
      expect(state.selectedCells).toEqual(new Set(allCells));
    });
  });

  describe("updateSelection", () => {
    beforeEach(() => {
      // Reset mocks before each test
      vi.mocked(getCellsBetween).mockClear();
      vi.mocked(getCellsBetween).mockReturnValue(["row1_col1", "row1_col2"]);
    });

    it("should update selection without shift key", () => {
      const newCell: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      actions.updateSelection({
        newCell,
        isShiftKey: false,
        table: mockTable,
      });

      expect(state.selectedCells).toEqual(new Set(["row1_col1"]));
      expect(state.selectedStartCell).toEqual(newCell);
      expect(state.focusedCell).toEqual(newCell);
    });

    it("should update range selection with shift key", () => {
      const startCell: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      const newCell: SelectedCell = {
        rowId: "row2",
        columnId: "col2",
        cellId: "row2_col2",
      };

      // First set a start cell
      actions.setSelectedStartCell(startCell);

      actions.updateSelection({
        newCell,
        isShiftKey: true,
        table: mockTable,
      });

      expect(getCellsBetween).toHaveBeenCalledWith(
        mockTable,
        startCell,
        newCell,
      );
      expect(state.selectedCells).toEqual(new Set(["row1_col1", "row1_col2"]));
      expect(state.focusedCell).toEqual(newCell);
    });

    it("should handle shift selection without start cell", () => {
      const newCell: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      actions.updateSelection({
        newCell,
        isShiftKey: true,
        table: mockTable,
      });

      // Should behave like regular selection when no start cell
      expect(state.selectedCells).toEqual(new Set(["row1_col1"]));
    });
  });

  describe("updateRangeSelection", () => {
    beforeEach(() => {
      // Reset mocks before each test
      vi.mocked(getCellsBetween).mockClear();
      vi.mocked(getCellsBetween).mockReturnValue(["row1_col1", "row1_col2"]);
    });

    it("should update range selection from existing start cell", () => {
      const startCell: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      const cell = createMockCell("row2", "col2", 1, 1);

      // Set start cell first
      actions.setSelectedStartCell(startCell);

      actions.updateRangeSelection({
        cell,
        table: mockTable,
      });

      expect(getCellsBetween).toHaveBeenCalled();
      expect(state.selectedCells).toEqual(new Set(["row1_col1", "row1_col2"]));
    });

    it("should do nothing without start cell", () => {
      const cell = createMockCell("row2", "col2", 1, 1);

      actions.updateRangeSelection({
        cell,
        table: mockTable,
      });

      // Should not call getCellsBetween if no start cell
      expect(getCellsBetween).not.toHaveBeenCalled();
      // Selection should remain empty
      expect(state.selectedCells).toEqual(new Set());
    });
  });

  describe("handleCopy", () => {
    beforeEach(() => {
      // Reset mocks before each test
      vi.mocked(getCellValues).mockClear();
      vi.mocked(getCellValues).mockReturnValue("mocked cell values");
    });

    it("should copy selected cells and call onCopyComplete", () => {
      const selectedCells = new Set(["row1_col1", "row1_col2"]);
      const onCopyComplete = vi.fn();

      // Set some selected cells first
      actions.setSelectedCells(selectedCells);

      actions.handleCopy({
        table: mockTable,
        onCopyComplete,
      });

      expect(getCellValues).toHaveBeenCalledWith(mockTable, selectedCells);
      expect(copyToClipboard).toHaveBeenCalledWith("mocked cell values");
      expect(onCopyComplete).toHaveBeenCalledWith();
      expect(state.copiedCells).toEqual(selectedCells);
    });
  });

  describe("navigate", () => {
    beforeEach(() => {
      // Reset mocks before each test
      vi.mocked(getCellsBetween).mockClear();
      vi.mocked(getCellsBetween).mockReturnValue(["row1_col1", "row1_col2"]);
    });

    it("should navigate up", () => {
      const startCell: SelectedCell = {
        rowId: "row2",
        columnId: "col2",
        cellId: "row2_col2",
      };

      actions.setFocusedCell(startCell);
      actions.setSelectedStartCell(startCell);

      actions.navigate({
        direction: "up",
        isShiftKey: false,
        table: mockTable,
      });

      // Should move to row1, col2
      expect(state.focusedCell).toEqual({
        rowId: "row1",
        columnId: "col2",
        cellId: "row1_col2",
      });
      expect(state.selectedCells).toEqual(new Set(["row1_col2"]));
    });

    it("should navigate down", () => {
      const startCell: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      actions.setFocusedCell(startCell);
      actions.setSelectedStartCell(startCell);

      actions.navigate({
        direction: "down",
        isShiftKey: false,
        table: mockTable,
      });

      // Should move to row2, col1
      expect(state.focusedCell).toEqual({
        rowId: "row2",
        columnId: "col1",
        cellId: "row2_col1",
      });
    });

    it("should navigate left", () => {
      const startCell: SelectedCell = {
        rowId: "row1",
        columnId: "col2",
        cellId: "row1_col2",
      };

      actions.setFocusedCell(startCell);
      actions.setSelectedStartCell(startCell);

      actions.navigate({
        direction: "left",
        isShiftKey: false,
        table: mockTable,
      });

      // Should move to row1, col1
      expect(state.focusedCell).toEqual({
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      });
    });

    it("should navigate right", () => {
      const startCell: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      actions.setFocusedCell(startCell);
      actions.setSelectedStartCell(startCell);

      actions.navigate({
        direction: "right",
        isShiftKey: false,
        table: mockTable,
      });

      // Should move to row1, col2
      expect(state.focusedCell).toEqual({
        rowId: "row1",
        columnId: "col2",
        cellId: "row1_col2",
      });
    });

    it("should extend selection when shift key is pressed", () => {
      const startCell: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      actions.setSelectedStartCell(startCell);
      actions.setFocusedCell(startCell);

      actions.navigate({
        direction: "down",
        isShiftKey: true,
        table: mockTable,
      });

      expect(getCellsBetween).toHaveBeenCalled();
      expect(state.selectedCells).toEqual(new Set(["row1_col1", "row1_col2"]));
      expect(state.focusedCell).toEqual({
        rowId: "row2",
        columnId: "col1",
        cellId: "row2_col1",
      });
    });

    it("should do nothing without current cell", () => {
      actions.setFocusedCell(null);
      actions.setSelectedStartCell(null);

      actions.navigate({
        direction: "up",
        isShiftKey: false,
        table: mockTable,
      });

      // Should remain null
      expect(state.focusedCell).toBeNull();
    });

    it("should handle navigation at boundaries", () => {
      // Try to navigate up from first row
      const firstRowCell: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      actions.setFocusedCell(firstRowCell);
      actions.setSelectedStartCell(firstRowCell);

      actions.navigate({
        direction: "up",
        isShiftKey: false,
        table: mockTable,
      });

      // Should stay in the same position
      expect(state.focusedCell).toEqual(firstRowCell);

      // Try to navigate left from first column
      actions.navigate({
        direction: "left",
        isShiftKey: false,
        table: mockTable,
      });

      // Should stay in the same position
      expect(state.focusedCell).toEqual(firstRowCell);
    });
  });

  describe("handleCellMouseDown", () => {
    const mockCell = createMockCell("row1", "col1");

    beforeEach(() => {
      // Reset mocks before each test
      vi.mocked(getCellsBetween).mockClear();
      vi.mocked(getCellsBetween).mockReturnValue(["row1_col1", "row1_col2"]);
    });

    it("should handle single cell selection", () => {
      actions.handleCellMouseDown({
        cell: mockCell,
        isShiftKey: false,
        isCtrlKey: false,
        table: mockTable,
      });

      expect(state.selectedCells).toEqual(new Set(["row1_col1"]));
      expect(state.selectedStartCell).toEqual({
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      });
      expect(state.focusedCell).toEqual({
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      });
      expect(state.isSelecting).toBe(true);
    });

    it("should handle shift+click range selection", () => {
      const startCell: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      actions.setSelectedStartCell(startCell);

      // Use a different cell for the shift+click
      const endCell = createMockCell("row2", "col2", 1, 1);

      actions.handleCellMouseDown({
        cell: endCell,
        isShiftKey: true,
        isCtrlKey: false,
        table: mockTable,
      });

      expect(getCellsBetween).toHaveBeenCalled();
      expect(state.selectedCells).toEqual(new Set(["row1_col1", "row1_col2"]));
      expect(state.isSelecting).toBe(true);
    });

    it("should deselect when clicking same cell", () => {
      const selectedCells = new Set(["row1_col1"]);
      actions.setSelectedCells(selectedCells);

      actions.handleCellMouseDown({
        cell: mockCell,
        isShiftKey: false,
        isCtrlKey: false,
        table: mockTable,
      });

      expect(state.selectedCells).toEqual(new Set());
      expect(state.selectedStartCell).toBeNull();
      expect(state.focusedCell).toBeNull();
    });
  });

  describe("derived atoms", () => {
    it("should create cell selected atom", () => {
      createCellSelectedAtom("row1_col1");

      // Initially not selected
      expect(state.selectedCells.has("row1_col1")).toBe(false);

      // Select the cell
      actions.setSelectedCells(new Set(["row1_col1"]));
      expect(state.selectedCells.has("row1_col1")).toBe(true);
    });

    it("should create cell copied atom", () => {
      createCellCopiedAtom("row1_col1");

      // Initially not copied
      expect(state.copiedCells.has("row1_col1")).toBe(false);

      // Copy the cell
      actions.setCopiedCells(new Set(["row1_col1"]));
      expect(state.copiedCells.has("row1_col1")).toBe(true);
    });

    it("should create cell state atom", () => {
      createCellStateAtom("row1_col1");

      // Initially not selected or copied
      expect(state.selectedCells.has("row1_col1")).toBe(false);
      expect(state.copiedCells.has("row1_col1")).toBe(false);

      // Select and copy the cell
      actions.setSelectedCells(new Set(["row1_col1"]));
      actions.setCopiedCells(new Set(["row1_col1"]));

      expect(state.selectedCells.has("row1_col1")).toBe(true);
      expect(state.copiedCells.has("row1_col1")).toBe(true);
    });
  });

  describe("edge cases", () => {
    it("should handle navigation at table boundaries", () => {
      // Test navigation from first row up
      const firstRowCell: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      actions.setFocusedCell(firstRowCell);
      actions.setSelectedStartCell(firstRowCell);

      actions.navigate({
        direction: "up",
        isShiftKey: false,
        table: mockTable,
      });

      // Should stay in the same position
      expect(state.focusedCell).toEqual(firstRowCell);

      // Test navigation from last row down
      const lastRowCell: SelectedCell = {
        rowId: "row3",
        columnId: "col3",
        cellId: "row3_col3",
      };

      actions.setFocusedCell(lastRowCell);
      actions.navigate({
        direction: "down",
        isShiftKey: false,
        table: mockTable,
      });

      // Should stay in the same position
      expect(state.focusedCell).toEqual(lastRowCell);
    });

    it("should handle empty table gracefully", () => {
      const emptyTable = {
        getRowModel: () => ({ rows: [] }),
        getRow: () => undefined,
      } as unknown as Table<T>;

      const currentCell: SelectedCell = {
        rowId: "nonexistent",
        columnId: "col1",
        cellId: "nonexistent_col1",
      };

      actions.setFocusedCell(currentCell);
      actions.navigate({
        direction: "up",
        isShiftKey: false,
        table: emptyTable,
      });

      // Should remain unchanged
      expect(state.focusedCell).toEqual(currentCell);
    });

    it("should handle missing cells gracefully", () => {
      const incompleteTable = {
        getRowModel: () => ({ rows: [] }),
        getRow: () => ({
          getAllCells: () => [],
        }),
      } as unknown as Table<T>;

      const cell: SelectedCell = {
        rowId: "nonexistent",
        columnId: "col1",
        cellId: "nonexistent_col1",
      };

      actions.setFocusedCell(cell);
      actions.navigate({
        direction: "right",
        isShiftKey: false,
        table: incompleteTable,
      });

      // Should remain unchanged
      expect(state.focusedCell).toEqual(cell);
    });
  });

  describe("complex interactions", () => {
    it("should handle multiple selections and copies", () => {
      const cells = ["row1_col1", "row1_col2", "row2_col1"];
      const selectedCells = new Set(cells);
      const onCopyComplete = vi.fn();

      actions.setSelectedCells(selectedCells);
      actions.handleCopy({
        table: mockTable,
        onCopyComplete,
      });

      expect(copyToClipboard).toHaveBeenCalled();
      expect(onCopyComplete).toHaveBeenCalledWith();
      expect(state.copiedCells).toEqual(selectedCells);
    });

    it("should clear selection and then create new selection", () => {
      // Start with some selection
      actions.setSelectedCells(new Set(["row1_col1"]));
      actions.setSelectedStartCell({
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      });

      // Clear it
      actions.clearSelection();

      expect(state.selectedCells).toEqual(new Set());
      expect(state.selectedStartCell).toBeNull();

      // Create new selection
      const newCell: SelectedCell = {
        rowId: "row2",
        columnId: "col2",
        cellId: "row2_col2",
      };

      actions.updateSelection({
        newCell,
        isShiftKey: false,
        table: mockTable,
      });

      expect(state.selectedCells).toEqual(new Set(["row2_col2"]));
      expect(state.selectedStartCell).toEqual(newCell);
    });

    it("should handle rapid state changes", () => {
      const cell1: SelectedCell = {
        rowId: "row1",
        columnId: "col1",
        cellId: "row1_col1",
      };

      const cell2: SelectedCell = {
        rowId: "row2",
        columnId: "col2",
        cellId: "row2_col2",
      };

      // Rapid state changes
      actions.setSelectedStartCell(cell1);
      actions.setFocusedCell(cell1);
      actions.setIsSelecting(true);
      actions.setSelectedStartCell(cell2);
      actions.setFocusedCell(cell2);
      actions.setIsSelecting(false);
      actions.clearSelection();

      expect(state.selectedCells).toEqual(new Set());
      expect(state.selectedStartCell).toBeNull();
      expect(state.focusedCell).toBeNull();
      expect(state.isSelecting).toBe(false);
    });
  });
});
