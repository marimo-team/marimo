/* Copyright 2024 Marimo. All rights reserved. */

import { useCallback, useState } from "react";
import type { Cell, Table } from "@tanstack/react-table";
import { renderUnknownValue } from "../renderers";
import { copyToClipboard } from "@/utils/copy";
import useEvent from "react-use-event-hook";

export interface SelectedCell {
  rowId: string;
  columnId: string;
  cellId: string;
}

export interface UseCellSelectionProps<TData> {
  table: Table<TData>;
}

export type SelectedCells = Map<string, SelectedCell>;

/*
 * This hook is used to handle selecting multiple cells at once.
 */
export const useCellSelection = <TData>({
  table,
}: UseCellSelectionProps<TData>) => {
  // Map of unique id to selected cell. So that we can use the unique id to check if a cell is selected.
  const [selectedCells, setSelectedCells] = useState<SelectedCells>(new Map());
  const [copiedCells, setCopiedCells] = useState<SelectedCells>(new Map());

  // The cell that is currently selected. This is used for navigation.
  const [selectedStartCell, setSelectedStartCell] =
    useState<SelectedCell | null>(null);

  // The cell that is currently focused. This is used for navigation when shift key is pressed.
  const [focusedCell, setFocusedCell] = useState<SelectedCell | null>(null);

  const [isMouseDown, setIsMouseDown] = useState(false);

  const getSelectedCell = useCallback(
    (cell: Cell<TData, unknown>): SelectedCell => {
      return {
        rowId: cell.row.id,
        columnId: cell.column.id,
        cellId: cell.id,
      };
    },
    [],
  );

  const handleCopy = () => {
    const text = getCellValues(table, selectedCells);
    copyToClipboard(text);
    setCopiedCells(selectedCells);
    setTimeout(() => {
      setCopiedCells(new Map());
    }, 500);
  };

  const updateSelection = (newCell: SelectedCell, isShiftKey: boolean) => {
    if (isShiftKey && selectedStartCell) {
      setSelectedCells(getCellsBetween(table, selectedStartCell, newCell));
      // Do not update selectedStartCell
      setFocusedCell(newCell);
    } else {
      const uniqueId = getUniqueCellId(
        newCell.rowId,
        newCell.columnId,
        newCell.cellId,
      );
      setSelectedCells(new Map([[uniqueId, newCell]]));
      setSelectedStartCell(newCell);
      setFocusedCell(newCell);
    }
  };

  const navigate = (
    e: React.KeyboardEvent<HTMLElement>,
    direction: "up" | "down" | "left" | "right",
  ) => {
    const currentCell = focusedCell ?? selectedStartCell;
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
    updateSelection(getSelectedCell(nextCell), e.shiftKey);
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

  const updateRangeSelection = (cell: Cell<TData, unknown>) => {
    if (!selectedStartCell) {
      return;
    }

    const selectedCellsInRange = getCellsBetween(
      table,
      selectedStartCell,
      getSelectedCell(cell),
    );

    setSelectedCells(selectedCellsInRange);
  };

  const handleCellMouseDown = useEvent(
    (e: React.MouseEvent, cell: Cell<TData, unknown>) => {
      const selectedCell = getSelectedCell(cell);
      const uniqueId = getUniqueCellId(
        selectedCell.rowId,
        selectedCell.columnId,
        selectedCell.cellId,
      );

      if (!e.ctrlKey && !e.shiftKey) {
        const deselectCell =
          selectedCells.size === 1 && selectedCells.has(uniqueId);
        // Deselect the cell if it's already selected
        if (deselectCell) {
          setSelectedCells(new Map());
          setSelectedStartCell(null);
          setFocusedCell(null);
          setIsMouseDown(true);
          return;
        }

        setSelectedCells(new Map([[uniqueId, selectedCell]]));
        if (!isMouseDown) {
          setSelectedStartCell(selectedCell);
          setFocusedCell(selectedCell);
        }
        setIsMouseDown(true);
        return;
      }

      if (e.shiftKey) {
        updateRangeSelection(cell);
        setIsMouseDown(true);
      }
    },
  );

  const handleCellMouseUp = useEvent(() => {
    setIsMouseDown(false);
  });

  const handleCellMouseOver = useEvent(
    (e: React.MouseEvent, cell: Cell<TData, unknown>) => {
      if (e.buttons !== 1) {
        return;
      }
      if (isMouseDown) {
        updateRangeSelection(cell);
      }
    },
  );

  const isCellSelected = useCallback(
    (cell: Cell<TData, unknown>) => {
      const cellToCheck = getSelectedCell(cell);
      const uniqueId = getUniqueCellId(
        cellToCheck.rowId,
        cellToCheck.columnId,
        cellToCheck.cellId,
      );
      return selectedCells.has(uniqueId);
    },
    [getSelectedCell, selectedCells],
  );

  const isCellCopied = useCallback(
    (cell: Cell<TData, unknown>) => {
      const cellToCheck = getSelectedCell(cell);
      const uniqueId = getUniqueCellId(
        cellToCheck.rowId,
        cellToCheck.columnId,
        cellToCheck.cellId,
      );
      return copiedCells.has(uniqueId);
    },
    [getSelectedCell, copiedCells],
  );

  return {
    handleCellMouseDown,
    handleCellMouseUp,
    handleCellMouseOver,
    handleCellsKeyDown,
    isCellSelected,
    isCellCopied,
  };
};

// Helper functions
export function getCellValues<TData>(
  table: Table<TData>,
  cells: SelectedCells,
): string {
  const rowValues = new Map<string, string[]>();

  for (const cell of cells.values()) {
    const row = table.getRow(cell.rowId);
    const tableCell = row.getAllCells().find((c) => c.id === cell.cellId);
    if (!tableCell) {
      continue;
    }

    const values = rowValues.get(cell.rowId) ?? [];
    values.push(renderUnknownValue({ value: tableCell.getValue() }));
    rowValues.set(cell.rowId, values);
  }

  return [...rowValues.values()].map((values) => values.join("\t")).join("\n");
}

export function getCellsBetween<TData>(
  table: Table<TData>,
  cellStart: SelectedCell,
  cellEnd: SelectedCell,
): SelectedCells {
  const rows = table.getRowModel().rows;
  const startRow = table.getRow(cellStart.rowId);
  const endRow = table.getRow(cellEnd.rowId);

  if (!startRow || !endRow) {
    return new Map();
  }

  const startCell = startRow
    .getAllCells()
    .find((c) => c.id === cellStart.cellId);
  const endCell = endRow.getAllCells().find((c) => c.id === cellEnd.cellId);

  if (!startCell || !endCell) {
    return new Map();
  }

  const startRowIdx = rows.findIndex(({ id }) => id === startCell.row.id);
  const endRowIdx = rows.findIndex(({ id }) => id === endCell.row.id);
  const startColumnIdx = startCell.column.getIndex();
  const endColumnIdx = endCell.column.getIndex();

  const minRow = Math.min(startRowIdx, endRowIdx);
  const maxRow = Math.max(startRowIdx, endRowIdx);
  const minCol = Math.min(startColumnIdx, endColumnIdx);
  const maxCol = Math.max(startColumnIdx, endColumnIdx);

  const result = new Map<string, SelectedCell>();

  for (let i = minRow; i <= maxRow; i++) {
    const row = rows[i];
    const cells = row.getAllCells();

    for (let j = minCol; j <= maxCol; j++) {
      const cell = cells[j];
      if (cell) {
        const uniqueId = getUniqueCellId(cell.row.id, cell.column.id, cell.id);
        const selectedCell = {
          rowId: cell.row.id,
          columnId: cell.column.id,
          cellId: cell.id,
        };
        result.set(uniqueId, selectedCell);
      }
    }
  }

  return result;
}

function getUniqueCellId(
  rowId: string,
  columnId: string,
  cellId: string,
): string {
  return `${rowId}-${columnId}-${cellId}`;
}

export const exportedForTesting = { getUniqueCellId };
