/* Copyright 2024 Marimo. All rights reserved. */

import type { Cell, Row, Table } from "@tanstack/react-table";
import { useCallback, useState } from "react";
import useEvent from "react-use-event-hook";
import { copyToClipboard } from "@/utils/copy";
import { renderUnknownValue } from "../renderers";

export interface SelectedCell {
  rowId: string;
  columnId: string;
  cellId: string; // unique id for the cell
}

export interface UseCellSelectionProps<TData> {
  table: Table<TData>;
}

export type SelectedCells = Set<string>;

/*
 * This hook is used to handle selecting multiple cells at once.
 */
export const useCellSelection = <TData>({
  table,
}: UseCellSelectionProps<TData>) => {
  const [selectedCells, setSelectedCells] = useState<SelectedCells>(new Set());
  const [copiedCells, setCopiedCells] = useState<SelectedCells>(new Set());

  // The cell that is currently selected. This is used for navigation.
  const [selectedStartCell, setSelectedStartCell] =
    useState<SelectedCell | null>(null);

  // The cell that is currently focused. This is used for navigation when shift key is pressed.
  const [focusedCell, setFocusedCell] = useState<SelectedCell | null>(null);

  const [isSelecting, setIsSelecting] = useState(false);

  const rows = table.getRowModel().rows;

  const isCellSelected = useCallback(
    (cellId: string) => selectedCells.has(cellId),
    [selectedCells],
  );

  const isCellCopied = useCallback(
    (cellId: string) => copiedCells.has(cellId),
    [copiedCells],
  );

  const handleCopy = useEvent(() => {
    const text = getCellValues(table, selectedCells);
    copyToClipboard(text);
    setCopiedCells(selectedCells);
    setTimeout(() => {
      setCopiedCells(new Set());
    }, 500);
  });

  const updateSelection = (newCell: SelectedCell, isShiftKey: boolean) => {
    if (isShiftKey && selectedStartCell) {
      const cellsInRange = getCellsBetween(
        table,
        rows,
        selectedStartCell,
        newCell,
      );
      setSelectedCells(new Set(cellsInRange));
      setFocusedCell(newCell);
    } else {
      setSelectedCells(new Set([newCell.cellId]));
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

  const updateRangeSelection = (cell: Cell<TData, unknown>) => {
    if (!selectedStartCell) {
      return;
    }

    const selectedCell = {
      rowId: cell.row.id,
      columnId: cell.column.id,
      cellId: cell.id,
    };

    const cellsInRange = getCellsBetween(
      table,
      rows,
      selectedStartCell,
      selectedCell,
    );
    setSelectedCells(new Set(cellsInRange));
  };

  const handleCellMouseDown = useEvent(
    (e: React.MouseEvent, cell: Cell<TData, unknown>) => {
      const selectedCell = {
        rowId: cell.row.id,
        columnId: cell.column.id,
        cellId: cell.id,
      };

      // Handle shift key selection
      if (e.shiftKey) {
        updateRangeSelection(cell);
        setIsSelecting(true);
        return;
      }

      // Handle normal selection
      if (!e.ctrlKey) {
        const isDeselecting =
          selectedCells.size === 1 && selectedCells.has(selectedCell.cellId);

        if (isDeselecting) {
          setSelectedCells(new Set());
          setSelectedStartCell(null);
          setFocusedCell(null);
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
      if (isSelecting) {
        updateRangeSelection(cell);
      }
    },
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
  selectedCellIds: Set<string>,
): string {
  const rowValues = new Map<string, string[]>();

  for (const cellId of selectedCellIds) {
    const [rowId] = cellId.split("_"); // CellId is rowId_columnId
    const row = table.getRow(rowId);
    const tableCell = row.getAllCells().find((c) => c.id === cellId);
    if (!tableCell) {
      continue;
    }

    const values = rowValues.get(rowId) ?? [];
    values.push(renderUnknownValue({ value: tableCell.getValue() }));
    rowValues.set(rowId, values);
  }

  return [...rowValues.values()].map((values) => values.join("\t")).join("\n");
}

// Returns the cell ids between two cells.
export function getCellsBetween<TData>(
  table: Table<TData>,
  rows: Array<Row<TData>>,
  cellStart: SelectedCell,
  cellEnd: SelectedCell,
): string[] {
  const startRow = table.getRow(cellStart.rowId);
  const endRow = table.getRow(cellEnd.rowId);

  if (!startRow || !endRow) {
    return [];
  }

  const startCell = startRow
    .getAllCells()
    .find((c) => c.id === cellStart.cellId);
  const endCell = endRow.getAllCells().find((c) => c.id === cellEnd.cellId);

  if (!startCell || !endCell) {
    return [];
  }

  const startRowIdx = startRow.index;
  const endRowIdx = endRow.index;
  const startColumnIdx = startCell.column.getIndex();
  const endColumnIdx = endCell.column.getIndex();

  const minRow = Math.min(startRowIdx, endRowIdx);
  const maxRow = Math.max(startRowIdx, endRowIdx);
  const minCol = Math.min(startColumnIdx, endColumnIdx);
  const maxCol = Math.max(startColumnIdx, endColumnIdx);

  // Pre-allocate array with known size
  const result: string[] = [];
  const totalCells = (maxRow - minRow + 1) * (maxCol - minCol + 1);
  result.length = totalCells;
  let resultIndex = 0;

  for (let i = minRow; i <= maxRow; i++) {
    const row = rows[i];
    const cells = row.getAllCells();

    for (let j = minCol; j <= maxCol; j++) {
      const cell = cells[j];
      result[resultIndex++] = cell.id;
    }
  }

  // Trim any unused slots
  result.length = resultIndex;
  return result;
}
