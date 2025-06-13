/* Copyright 2024 Marimo. All rights reserved. */

import type { Cell, Table } from "@tanstack/react-table";
import { useSetAtom, useStore } from "jotai";
import useEvent from "react-use-event-hook";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";
import {
  clearSelectionAtom,
  focusedCellAtom,
  isSelectingAtom,
  type SelectedCell,
  selectedCellsAtom,
  selectedStartCellAtom,
  setCopiedCellsAtom,
} from "./cell-selection-atoms";
import { getCellsBetween, getCellValues } from "./utils";

export interface UseCellSelectionActionsProps<TData> {
  table: Table<TData>;
}

/*
 * Pure hook that provides only actions without causing re-renders.
 * Use this in components that only need to trigger actions.
 */
export const useCellSelectionActions = <TData>({
  table,
}: UseCellSelectionActionsProps<TData>) => {
  const setSelectedCells = useSetAtom(selectedCellsAtom);
  const setSelectedStartCell = useSetAtom(selectedStartCellAtom);
  const setFocusedCell = useSetAtom(focusedCellAtom);
  const setIsSelecting = useSetAtom(isSelectingAtom);
  const clearSelection = useSetAtom(clearSelectionAtom);
  const setCopiedCells = useSetAtom(setCopiedCellsAtom);
  const store = useStore();

  // Get current values without subscribing
  const getCurrentSelectedCells = () => store.get(selectedCellsAtom);
  const getCurrentStartCell = () => store.get(selectedStartCellAtom);
  const getCurrentFocusedCell = () => store.get(focusedCellAtom);

  const handleCopy = useEvent(() => {
    const selectedCells = getCurrentSelectedCells();
    const text = getCellValues(table, selectedCells);
    copyToClipboard(text);
    setCopiedCells(selectedCells);
  });

  const updateSelection = useEvent(
    (newCell: SelectedCell, isShiftKey: boolean) => {
      if (isShiftKey) {
        const startCell = getCurrentStartCell();
        if (startCell) {
          const rows = table.getRowModel().rows;
          const cellsInRange = getCellsBetween(table, rows, startCell, newCell);
          setSelectedCells(new Set(cellsInRange));
          setFocusedCell(newCell);
        }
      } else {
        setSelectedCells(new Set([newCell.cellId]));
        setSelectedStartCell(newCell);
        setFocusedCell(newCell);
      }
    },
  );

  const navigate = (
    e: React.KeyboardEvent<HTMLElement>,
    direction: "up" | "down" | "left" | "right",
  ) => {
    const currentCell = getCurrentFocusedCell() ?? getCurrentStartCell();
    if (!currentCell) {
      return;
    }

    let nextCell: Cell<TData, unknown> | undefined;

    if (direction === "up" || direction === "down") {
      const rows = table.getRowModel().rows;
      const selectedRowIndex = rows.findIndex(
        (row) => row.id === currentCell.rowId,
      );
      if (selectedRowIndex < 0) {
        return;
      }

      const nextRow =
        direction === "up"
          ? rows[selectedRowIndex - 1]
          : rows[selectedRowIndex + 1];

      if (!nextRow) {
        return;
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
      if (selectedColumnIndex < 0) {
        return;
      }

      nextCell =
        direction === "left"
          ? cells[selectedColumnIndex - 1]
          : cells[selectedColumnIndex + 1];
    }

    if (!nextCell) {
      return;
    }
    updateSelection(
      {
        rowId: nextCell.row.id,
        columnId: nextCell.column.id,
        cellId: nextCell.id,
      },
      e.shiftKey,
    );
  };

  const handleCellsKeyDown = (e: React.KeyboardEvent<HTMLElement>) => {
    switch (e.key) {
      case "c":
        if (e.metaKey || e.ctrlKey) {
          handleCopy();
        }
        break;
      case "ArrowDown":
        e.preventDefault();
        navigate(e, "down");
        break;
      case "ArrowUp":
        e.preventDefault();
        navigate(e, "up");
        break;
      case "ArrowLeft":
        e.preventDefault();
        navigate(e, "left");
        break;
      case "ArrowRight":
        e.preventDefault();
        navigate(e, "right");
        break;
    }
  };

  const updateRangeSelection = useEvent((cell: Cell<TData, unknown>) => {
    const startCell = getCurrentStartCell();
    if (!startCell) {
      return;
    }

    const selectedCell = {
      rowId: cell.row.id,
      columnId: cell.column.id,
      cellId: cell.id,
    };

    const rows = table.getRowModel().rows;
    const cellsInRange = getCellsBetween(table, rows, startCell, selectedCell);
    setSelectedCells(new Set(cellsInRange));
  });

  const handleCellMouseDown = useEvent(
    (e: React.MouseEvent, cell: Cell<TData, unknown>) => {
      const selectedCell = {
        rowId: cell.row.id,
        columnId: cell.column.id,
        cellId: cell.id,
      };

      if (e.shiftKey) {
        updateRangeSelection(cell);
        setIsSelecting(true);
        return;
      }

      if (!e.ctrlKey) {
        const currentCells = getCurrentSelectedCells();
        const isDeselecting =
          currentCells.size === 1 && currentCells.has(selectedCell.cellId);

        if (isDeselecting) {
          clearSelection();
          return;
        }

        setSelectedCells(new Set([selectedCell.cellId]));
        setSelectedStartCell(selectedCell);
        setFocusedCell(selectedCell);
        setIsSelecting(true);
      }
    },
  );

  const handleCellMouseUp = useEvent(() => {
    setIsSelecting(false);
  });

  const handleCellMouseOver = useEvent(
    (e: React.MouseEvent, cell: Cell<TData, unknown>) => {
      if (e.buttons !== 1) {
        return;
      }

      // Check if selecting without subscribing to state
      const isCurrentlySelecting = isSelectingAtom.init;
      if (isCurrentlySelecting) {
        updateRangeSelection(cell);
      }
    },
  );

  Logger.debug("[table] Rendering cell selection actions");

  return {
    handleCellMouseDown,
    handleCellMouseUp,
    handleCellMouseOver,
    handleCopy,
    handleCellsKeyDown,
    updateSelection,
    clearSelection,
  };
};
