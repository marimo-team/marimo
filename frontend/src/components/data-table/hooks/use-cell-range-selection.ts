/* Copyright 2024 Marimo. All rights reserved. */

import { useState, useCallback } from "react";
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
  scrollToRow?: (index: number) => void;
}

/*
 * This hook is used to handle selecting multiple cells at once.
 */
export const useCellSelection = <TData>({
  table,
  scrollToRow,
}: UseCellSelectionProps<TData>) => {
  const [selectedCells, setSelectedCells] = useState<SelectedCell[]>([]);
  const [copiedCells, setCopiedCells] = useState<SelectedCell[]>([]);
  const [selectedStartCell, setSelectedStartCell] =
    useState<SelectedCell | null>(null);
  const [isMouseDown, setIsMouseDown] = useState(false);

  const getCellSelectionData = useEvent(
    (cell: Cell<TData, unknown>): SelectedCell => ({
      rowId: cell.row.id,
      columnId: cell.column.id,
      cellId: cell.id,
    }),
  );

  const handleCopy = useCallback(() => {
    const text = getCellValues(table, selectedCells);
    copyToClipboard(text);
    setCopiedCells(selectedCells);
    setTimeout(() => {
      setCopiedCells([]);
    }, 500);
  }, [selectedCells, table]);

  const navigateUp = useCallback(() => {
    const selectedCell = selectedCells[selectedCells.length - 1];
    if (!selectedCell) {
      return;
    }

    const selectedRowIndex = table
      .getRowModel()
      .rows.findIndex((row) => row.id === selectedCell.rowId);
    const nextRowIndex = selectedRowIndex - 1;
    const previousRow = table.getRowModel().rows[nextRowIndex];
    if (previousRow) {
      const previousCell = previousRow
        .getAllCells()
        .find((c) => c.column.id === selectedCell.columnId);
      if (previousCell) {
        setSelectedCells([getCellSelectionData(previousCell)]);
        scrollToRow?.(nextRowIndex);
      }
    }
  }, [selectedCells, table, scrollToRow, getCellSelectionData]);

  const navigateDown = useCallback(() => {
    const selectedCell = selectedCells[selectedCells.length - 1];
    if (!selectedCell) {
      return;
    }

    const selectedRowIndex = table
      .getRowModel()
      .rows.findIndex((row) => row.id === selectedCell.rowId);
    const nextRowIndex = selectedRowIndex + 1;
    const nextRow = table.getRowModel().rows[nextRowIndex];
    if (nextRow) {
      const nextCell = nextRow
        .getAllCells()
        .find((c) => c.column.id === selectedCell.columnId);
      if (nextCell) {
        setSelectedCells([getCellSelectionData(nextCell)]);
        scrollToRow?.(nextRowIndex);
      }
    }
  }, [selectedCells, table, scrollToRow, getCellSelectionData]);

  const navigateLeft = useCallback(() => {
    const selectedCell = selectedCells[selectedCells.length - 1];
    if (!selectedCell) {
      return;
    }

    const selectedRow = table.getRow(selectedCell.rowId);
    const selectedColumnIndex = selectedRow
      .getAllCells()
      .findIndex((c) => c.id === selectedCell.cellId);
    const previousCell = selectedRow.getAllCells()[selectedColumnIndex - 1];
    if (previousCell) {
      setSelectedCells([getCellSelectionData(previousCell)]);
    }
  }, [selectedCells, table, getCellSelectionData]);

  const navigateRight = useCallback(() => {
    const selectedCell = selectedCells[selectedCells.length - 1];
    if (!selectedCell) {
      return;
    }

    const selectedRow = table.getRow(selectedCell.rowId);
    const selectedColumnIndex = selectedRow
      .getAllCells()
      .findIndex((c) => c.id === selectedCell.cellId);
    const nextCell = selectedRow.getAllCells()[selectedColumnIndex + 1];
    if (nextCell) {
      setSelectedCells([getCellSelectionData(nextCell)]);
    }
  }, [selectedCells, table, getCellSelectionData]);

  const handleCellsKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLElement>) => {
      switch (e.key) {
        case "c":
          if (e.metaKey || e.ctrlKey) {
            handleCopy();
          }
          break;
        case "ArrowDown":
          e.preventDefault();
          navigateDown();
          break;
        case "ArrowUp":
          e.preventDefault();
          navigateUp();
          break;
        case "ArrowLeft":
          e.preventDefault();
          navigateLeft();
          break;
        case "ArrowRight":
          e.preventDefault();
          navigateRight();
          break;
      }
    },
    [handleCopy, navigateDown, navigateUp, navigateLeft, navigateRight],
  );

  const updateRangeSelection = useCallback(
    (cell: Cell<TData, unknown>) => {
      if (!selectedStartCell) {
        return;
      }

      const selectedCellsInRange = getCellsBetween(
        table,
        selectedStartCell,
        getCellSelectionData(cell),
      );

      setSelectedCells((prev) => {
        const startIndex = prev.findIndex(
          (c) => c.cellId === selectedStartCell.cellId,
        );
        const prevSelectedCells = prev.slice(0, startIndex);
        const newCellSelection = selectedCellsInRange.filter(
          (c) => c.cellId !== selectedStartCell.cellId,
        );

        return [...prevSelectedCells, selectedStartCell, ...newCellSelection];
      });
    },
    [selectedStartCell, table, getCellSelectionData],
  );

  const handleCellMouseDown = useCallback(
    (e: React.MouseEvent, cell: Cell<TData, unknown>) => {
      if (!e.ctrlKey && !e.shiftKey) {
        setSelectedCells([getCellSelectionData(cell)]);
        if (!isMouseDown) {
          setSelectedStartCell(getCellSelectionData(cell));
        }
      }

      if (e.ctrlKey) {
        setSelectedCells((prev) =>
          prev.some((c) => c.cellId === cell.id)
            ? prev.filter(({ cellId }) => cellId !== cell.id)
            : [...prev, getCellSelectionData(cell)],
        );
        if (!isMouseDown) {
          setSelectedStartCell(getCellSelectionData(cell));
        }
      }

      if (e.shiftKey) {
        updateRangeSelection(cell);
      }

      setIsMouseDown(true);
    },
    [isMouseDown, updateRangeSelection, getCellSelectionData],
  );

  const handleCellMouseUp = useEvent(
    (_e: React.MouseEvent, _cell: Cell<TData, unknown>) => {
      setIsMouseDown(false);
    },
  );

  const handleCellMouseOver = useCallback(
    (e: React.MouseEvent, cell: Cell<TData, unknown>) => {
      if (e.buttons !== 1) {
        return;
      }
      if (isMouseDown) {
        updateRangeSelection(cell);
      }
    },
    [isMouseDown, updateRangeSelection],
  );

  const isCellSelected = useCallback(
    (cell: Cell<TData, unknown>) =>
      selectedCells.some((c) => c.cellId === cell.id),
    [selectedCells],
  );

  const isCellCopied = useCallback(
    (cell: Cell<TData, unknown>) =>
      copiedCells.some((c) => c.cellId === cell.id),
    [copiedCells],
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
  cells: SelectedCell[],
): string {
  const rows = cells.reduce(
    (acc: Record<string, SelectedCell[]>, cell: SelectedCell) => {
      const cellsForRow = acc[cell.rowId] ?? [];
      return {
        ...acc,
        [cell.rowId]: [...cellsForRow, cell],
      };
    },
    {},
  );

  return Object.keys(rows)
    .map((rowId) => {
      const selectedCells = rows[rowId];
      const row = table.getRow(rowId);
      const cellValues = row
        .getAllCells()
        .filter((cell) => selectedCells.find((c) => c.cellId === cell.id))
        .map((cell) => renderUnknownValue({ value: cell.getValue() }));
      return cellValues.join("\t");
    })
    .join("\n");
}

export function getCellsBetween<TData>(
  table: Table<TData>,
  cellStart: SelectedCell,
  cellEnd: SelectedCell,
): SelectedCell[] {
  const cellStartData = table
    .getRow(cellStart.rowId)
    .getAllCells()
    .find((c) => c.id === cellStart.cellId);
  const cellEndData = table
    .getRow(cellEnd.rowId)
    .getAllCells()
    .find((c) => c.id === cellEnd.cellId);
  if (!cellStartData || !cellEndData) {
    return [];
  }

  const rows = table.getRowModel().rows;
  const cellStartRowIdx = rows.findIndex(
    ({ id }) => id === cellStartData.row.id,
  );
  const cellEndRowIdx = rows.findIndex(({ id }) => id === cellEndData.row.id);
  const cellStartColumnIdx = cellStartData.column.getIndex();
  const cellEndColumnIdx = cellEndData.column.getIndex();

  const selectedRows = rows.slice(
    Math.min(cellStartRowIdx, cellEndRowIdx),
    Math.max(cellStartRowIdx, cellEndRowIdx) + 1,
  );

  const columns = table
    .getAllColumns()
    .slice(
      Math.min(cellStartColumnIdx, cellEndColumnIdx),
      Math.max(cellStartColumnIdx, cellEndColumnIdx) + 1,
    );

  return selectedRows.flatMap((row) =>
    columns
      .map((column) => {
        const tableCell = row
          .getAllCells()
          .find((cell) => cell.column.id === column.id);
        if (!tableCell) {
          return null;
        }
        return {
          rowId: tableCell.row.id,
          columnId: tableCell.column.id,
          cellId: tableCell.id,
        };
      })
      .filter((cell): cell is SelectedCell => cell !== null),
  );
}
