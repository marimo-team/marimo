/* Copyright 2024 Marimo. All rights reserved. */

import { useState } from "react";
import type { Cell, Table } from "@tanstack/react-table";
import useEvent from "react-use-event-hook";
import { renderUnknownValue } from "../renderers";
import { copyToClipboard } from "@/utils/copy";

export interface SelectedCell {
  rowId: string;
  columnId: string;
  cellId: string;
}

export interface UseCellSelectionProps<TData> {
  table: Table<TData>;
}

/*
 * This hook is used to handle selecting multiple cells at once.
 */
export const useCellSelection = <TData>({
  table,
}: UseCellSelectionProps<TData>) => {
  const [selectedCells, setSelectedCells] = useState<SelectedCell[]>([]);
  const [copiedCells, setCopiedCells] = useState<SelectedCell[]>([]);
  const [selectedStartCell, setSelectedStartCell] =
    useState<SelectedCell | null>(null);
  const [isMouseDown, setIsMouseDown] = useState(false);

  const getSelectedCell = useEvent(
    (cell: Cell<TData, unknown>): SelectedCell => ({
      rowId: cell.row.id,
      columnId: cell.column.id,
      cellId: cell.id,
    }),
  );

  const handleCopy = () => {
    const text = getCellValues(table, selectedCells);
    copyToClipboard(text);
    setCopiedCells(selectedCells);
    setTimeout(() => {
      setCopiedCells([]);
    }, 500);
  };

  const updateSelection = (newCell: SelectedCell, isShiftKey: boolean) => {
    if (isShiftKey && selectedStartCell) {
      setSelectedCells(getCellsBetween(table, selectedStartCell, newCell));
    } else {
      setSelectedCells([newCell]);
      setSelectedStartCell(newCell);
    }
  };

  const navigateUp = (e: React.KeyboardEvent<HTMLElement>) => {
    const selectedCell = selectedCells[selectedCells.length - 1];
    if (!selectedCell) {
      return;
    }

    const rows = table.getRowModel().rows;
    const selectedRowIndex = rows.findIndex(
      (row) => row.id === selectedCell.rowId,
    );
    if (selectedRowIndex < 0) {
      return;
    }

    const previousRow = rows[selectedRowIndex - 1];
    if (!previousRow) {
      return;
    }

    const previousCell = previousRow
      .getAllCells()
      .find((c) => c.column.id === selectedCell.columnId);
    if (!previousCell) {
      return;
    }

    updateSelection(getSelectedCell(previousCell), e.shiftKey);
  };

  const navigateDown = (e: React.KeyboardEvent<HTMLElement>) => {
    const selectedCell = selectedCells[selectedCells.length - 1];
    if (!selectedCell) {
      return;
    }

    const rows = table.getRowModel().rows;
    const selectedRowIndex = rows.findIndex(
      (row) => row.id === selectedCell.rowId,
    );
    if (selectedRowIndex < 0) {
      return;
    }

    const nextRow = rows[selectedRowIndex + 1];
    if (!nextRow) {
      return;
    }

    const nextCell = nextRow
      .getAllCells()
      .find((c) => c.column.id === selectedCell.columnId);
    if (!nextCell) {
      return;
    }

    updateSelection(getSelectedCell(nextCell), e.shiftKey);
  };

  const navigateLeft = (e: React.KeyboardEvent<HTMLElement>) => {
    const selectedCell = selectedCells[selectedCells.length - 1];
    if (!selectedCell) {
      return;
    }

    const selectedRow = table.getRow(selectedCell.rowId);
    const cells = selectedRow.getAllCells();
    const selectedColumnIndex = cells.findIndex(
      (c) => c.id === selectedCell.cellId,
    );
    if (selectedColumnIndex < 0) {
      return;
    }

    const previousCell = cells[selectedColumnIndex - 1];
    if (!previousCell) {
      return;
    }

    updateSelection(getSelectedCell(previousCell), e.shiftKey);
  };

  const navigateRight = (e: React.KeyboardEvent<HTMLElement>) => {
    const selectedCell = selectedCells[selectedCells.length - 1];
    if (!selectedCell) {
      return;
    }

    const selectedRow = table.getRow(selectedCell.rowId);
    const cells = selectedRow.getAllCells();
    const selectedColumnIndex = cells.findIndex(
      (c) => c.id === selectedCell.cellId,
    );
    if (selectedColumnIndex < 0) {
      return;
    }

    const nextCell = cells[selectedColumnIndex + 1];
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
        navigateDown(e);
        break;
      case "ArrowUp":
        e.preventDefault();
        navigateUp(e);
        break;
      case "ArrowLeft":
        e.preventDefault();
        navigateLeft(e);
        break;
      case "ArrowRight":
        e.preventDefault();
        navigateRight(e);
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

  const handleCellMouseDown = (
    e: React.MouseEvent,
    cell: Cell<TData, unknown>,
  ) => {
    const selectedCell = getSelectedCell(cell);

    if (!e.ctrlKey && !e.shiftKey) {
      const deselectCell =
        selectedCells.length === 1 && selectedCells[0].cellId === cell.id;
      // Deselect the cell if it's already selected
      if (deselectCell) {
        setSelectedCells([]);
        setSelectedStartCell(null);
        setIsMouseDown(true);
        return;
      }

      setSelectedCells([selectedCell]);
      if (!isMouseDown) {
        setSelectedStartCell(selectedCell);
      }
      setIsMouseDown(true);
      return;
    }

    if (e.ctrlKey) {
      setSelectedCells((prev) => {
        const cellExists = prev.some((c) => c.cellId === cell.id);
        if (cellExists) {
          return prev.filter(({ cellId }) => cellId !== cell.id);
        }
        return [...prev, selectedCell];
      });
      if (!isMouseDown) {
        setSelectedStartCell(selectedCell);
      }
      setIsMouseDown(true);
      return;
    }

    if (e.shiftKey) {
      updateRangeSelection(cell);
      setIsMouseDown(true);
    }
  };

  const handleCellMouseUp = () => {
    setIsMouseDown(false);
  };

  const handleCellMouseOver = (
    e: React.MouseEvent,
    cell: Cell<TData, unknown>,
  ) => {
    if (e.buttons !== 1) {
      return;
    }
    if (isMouseDown) {
      updateRangeSelection(cell);
    }
  };

  const isCellSelected = (cell: Cell<TData, unknown>) => {
    return selectedCells.some((c) => c.cellId === cell.id);
  };

  const isCellCopied = (cell: Cell<TData, unknown>) => {
    return copiedCells.some((c) => c.cellId === cell.id);
  };

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
  cells: SelectedCell[],
): string {
  const rowValues = new Map<string, string[]>();

  for (const cell of cells) {
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
): SelectedCell[] {
  const rows = table.getRowModel().rows;
  const cellStartRow = table.getRow(cellStart.rowId);
  const cellEndRow = table.getRow(cellEnd.rowId);

  if (!cellStartRow || !cellEndRow) {
    return [];
  }

  const cellStartData = cellStartRow
    .getAllCells()
    .find((c) => c.id === cellStart.cellId);
  const cellEndData = cellEndRow
    .getAllCells()
    .find((c) => c.id === cellEnd.cellId);

  if (!cellStartData || !cellEndData) {
    return [];
  }

  const cellStartRowIdx = rows.findIndex(
    ({ id }) => id === cellStartData.row.id,
  );
  const cellEndRowIdx = rows.findIndex(({ id }) => id === cellEndData.row.id);
  const cellStartColumnIdx = cellStartData.column.getIndex();
  const cellEndColumnIdx = cellEndData.column.getIndex();

  const minRow = Math.min(cellStartRowIdx, cellEndRowIdx);
  const maxRow = Math.max(cellStartRowIdx, cellEndRowIdx);
  const minCol = Math.min(cellStartColumnIdx, cellEndColumnIdx);
  const maxCol = Math.max(cellStartColumnIdx, cellEndColumnIdx);

  const result: SelectedCell[] = [];

  for (let i = minRow; i <= maxRow; i++) {
    const row = rows[i];
    const cells = row.getAllCells();

    for (let j = minCol; j <= maxCol; j++) {
      const cell = cells[j];
      if (cell) {
        result.push({
          rowId: cell.row.id,
          columnId: cell.column.id,
          cellId: cell.id,
        });
      }
    }
  }

  return result;
}
