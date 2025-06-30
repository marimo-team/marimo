/* Copyright 2024 Marimo. All rights reserved. */

import type { Cell, Table } from "@tanstack/react-table";
import { atom } from "jotai";
import { copyToClipboard } from "@/utils/copy";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { getCellsBetween, getCellValues } from "./utils";

export interface SelectedCell {
  rowId: string;
  columnId: string;
  cellId: string; // unique id for the cell
}

export type SelectedCells = Set<string>;

export interface CellSelectionState {
  selectedCells: SelectedCells;
  copiedCells: SelectedCells;
  selectedStartCell: SelectedCell | null;
  focusedCell: SelectedCell | null;
  isSelecting: boolean;
}

function initialState(): CellSelectionState {
  return {
    selectedCells: new Set<string>(),
    copiedCells: new Set<string>(),
    selectedStartCell: null,
    focusedCell: null,
    isSelecting: false,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyTable = Table<any>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyCell = Cell<any, unknown>;

const {
  valueAtom: cellSelectionStateAtom,
  useActions: useCellSelectionReducerActions,
  createActions,
  reducer,
} = createReducerAndAtoms(initialState, {
  setSelectedCells: (state, selectedCells: SelectedCells) => {
    return { ...state, selectedCells };
  },
  setSelectedStartCell: (state, selectedStartCell: SelectedCell | null) => {
    return { ...state, selectedStartCell };
  },
  setFocusedCell: (state, focusedCell: SelectedCell | null) => {
    return { ...state, focusedCell };
  },
  setIsSelecting: (state, isSelecting: boolean) => {
    return { ...state, isSelecting };
  },
  setCopiedCells: (state, copiedCells: SelectedCells) => {
    return { ...state, copiedCells };
  },
  clearSelection: (state) => {
    return {
      ...state,
      selectedCells: new Set(),
      selectedStartCell: null,
      focusedCell: null,
    };
  },
  selectAllCells: (state, table: AnyTable) => {
    const allCells = table
      .getRowModel()
      .rows.flatMap((row) => row.getAllCells().map((cell) => cell.id));
    return {
      ...state,
      selectedCells: new Set(allCells),
    };
  },
  toggleCurrentRowSelection: (state, table: AnyTable) => {
    const currentCell = state.focusedCell;
    if (currentCell?.rowId) {
      const row = table.getRow(currentCell?.rowId);
      row?.toggleSelected?.();
    }
    return state;
  },
  updateSelection: (
    state,
    {
      newCell,
      isShiftKey,
      table,
    }: {
      newCell: SelectedCell;
      isShiftKey: boolean;
      table: AnyTable;
    },
  ) => {
    if (isShiftKey && state.selectedStartCell) {
      const cellsInRange = getCellsBetween(
        table,
        state.selectedStartCell,
        newCell,
      );
      return {
        ...state,
        selectedCells: new Set(cellsInRange),
        focusedCell: newCell,
      };
    } else {
      return {
        ...state,
        selectedCells: new Set([newCell.cellId]),
        selectedStartCell: newCell,
        focusedCell: newCell,
      };
    }
  },
  updateRangeSelection: (
    state,
    {
      cell,
      table,
    }: {
      cell: AnyCell;
      table: AnyTable;
    },
  ) => {
    if (!state.selectedStartCell) {
      return state;
    }

    const selectedCell = {
      rowId: cell.row.id,
      columnId: cell.column.id,
      cellId: cell.id,
    };

    const cellsInRange = getCellsBetween(
      table,
      state.selectedStartCell,
      selectedCell,
    );

    return {
      ...state,
      selectedCells: new Set(cellsInRange),
    };
  },
  handleCopy: (
    state,
    {
      table,
      onCopyComplete,
    }: {
      table: AnyTable;
      onCopyComplete: () => void;
    },
  ) => {
    const text = getCellValues(table, state.selectedCells);
    copyToClipboard(text);
    onCopyComplete();

    return {
      ...state,
      copiedCells: state.selectedCells,
    };
  },
  navigate: (
    state,
    {
      direction,
      isShiftKey,
      table,
    }: {
      direction: "up" | "down" | "left" | "right";
      isShiftKey: boolean;
      table: AnyTable;
    },
  ) => {
    const currentCell = state.focusedCell ?? state.selectedStartCell;
    if (!currentCell) {
      return state;
    }

    let nextCell: AnyCell | undefined;

    if (direction === "up" || direction === "down") {
      const rows = table.getRowModel().rows;
      const selectedRowIndex = rows.findIndex(
        (row) => row.id === currentCell.rowId,
      );
      if (selectedRowIndex === -1) {
        return state;
      }

      const nextRow =
        direction === "up"
          ? rows[selectedRowIndex - 1]
          : rows[selectedRowIndex + 1];

      if (!nextRow) {
        return state;
      }

      nextCell = nextRow
        .getAllCells()
        .find((c) => c.column.id === currentCell.columnId);
    }

    if (direction === "left" || direction === "right") {
      const selectedRow = table.getRow(currentCell.rowId);
      const cells = selectedRow.getAllCells();
      const selectedColumnIndex = cells.findIndex(
        (c) => c.id === currentCell.cellId,
      );
      if (selectedColumnIndex === -1) {
        return state;
      }

      nextCell =
        direction === "left"
          ? cells[selectedColumnIndex - 1]
          : cells[selectedColumnIndex + 1];
    }

    if (!nextCell) {
      return state;
    }

    const newCell = {
      rowId: nextCell.row.id,
      columnId: nextCell.column.id,
      cellId: nextCell.id,
    };

    if (isShiftKey && state.selectedStartCell) {
      const cellsInRange = getCellsBetween(
        table,
        state.selectedStartCell,
        newCell,
      );
      return {
        ...state,
        selectedCells: new Set(cellsInRange),
        focusedCell: newCell,
      };
    } else {
      return {
        ...state,
        selectedCells: new Set([newCell.cellId]),
        selectedStartCell: newCell,
        focusedCell: newCell,
      };
    }
  },
  handleCellMouseDown: (
    state,
    {
      cell,
      isShiftKey,
      isCtrlKey,
      table,
    }: {
      cell: AnyCell;
      isShiftKey: boolean;
      isCtrlKey: boolean;
      table: AnyTable;
    },
  ) => {
    const selectedCell = {
      rowId: cell.row.id,
      columnId: cell.column.id,
      cellId: cell.id,
    };

    if (isShiftKey && state.selectedStartCell) {
      const cellsInRange = getCellsBetween(
        table,
        state.selectedStartCell,
        selectedCell,
      );
      return {
        ...state,
        selectedCells: new Set(cellsInRange),
        isSelecting: true,
      };
    }

    if (!isCtrlKey) {
      const isDeselecting =
        state.selectedCells.size === 1 &&
        state.selectedCells.has(selectedCell.cellId);

      if (isDeselecting) {
        return {
          ...state,
          selectedCells: new Set(),
          selectedStartCell: null,
          focusedCell: null,
        };
      }

      return {
        ...state,
        selectedCells: new Set([selectedCell.cellId]),
        selectedStartCell: selectedCell,
        focusedCell: selectedCell,
        isSelecting: true,
      };
    }

    return state;
  },
});

export { useCellSelectionReducerActions, cellSelectionStateAtom };

export const visibleForTesting = {
  createActions,
  reducer,
  initialState,
};

// Derived atoms for individual cell state
export const selectedCellsAtom = atom(
  (get) => get(cellSelectionStateAtom).selectedCells,
);
export const copiedCellsAtom = atom(
  (get) => get(cellSelectionStateAtom).copiedCells,
);
export const selectedStartCellAtom = atom(
  (get) => get(cellSelectionStateAtom).selectedStartCell,
);
export const focusedCellAtom = atom(
  (get) => get(cellSelectionStateAtom).focusedCell,
);
export const isSelectingAtom = atom(
  (get) => get(cellSelectionStateAtom).isSelecting,
);

// Optimized derived atoms for individual cell state
export const createCellSelectedAtom = (cellId: string) =>
  atom((get) => {
    const selectedCells = get(selectedCellsAtom);
    return selectedCells.has(cellId);
  });

export const createCellCopiedAtom = (cellId: string) =>
  atom((get) => {
    const copiedCells = get(copiedCellsAtom);
    return copiedCells.has(cellId);
  });

export const createCellStateAtom = (cellId: string) =>
  atom((get) => {
    const selectedCells = get(selectedCellsAtom);
    const copiedCells = get(copiedCellsAtom);
    return {
      isSelected: selectedCells.has(cellId),
      isCopied: copiedCells.has(cellId),
    };
  });
