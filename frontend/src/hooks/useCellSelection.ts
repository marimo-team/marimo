/* Copyright 2024 Marimo. All rights reserved. */

import { useState, useCallback } from "react";
import type { Cell, Table } from "@tanstack/react-table";

export interface SelectedCell {
  rowId: string;
  columnId: string;
  cellId: string;
}

export interface UseCellSelectionProps {
  table: Table<unknown>;
  scrollToRow?: (index: number) => void;
}

export const useCellSelection = ({
  table,
  scrollToRow,
}: UseCellSelectionProps) => {
  const [selectedCells, setSelectedCells] = useState<SelectedCell[]>([]);
  const [copiedCells, setCopiedCells] = useState<SelectedCell[]>([]);
  const [selectedStartCell, setSelectedStartCell] =
    useState<SelectedCell | null>(null);
  const [isMouseDown, setIsMouseDown] = useState(false);

  const getCellSelectionData = useCallback(
    (cell: Cell<unknown, unknown>): SelectedCell => ({
      rowId: cell.row.id,
      columnId: cell.column.id,
      cellId: cell.id,
    }),
    [],
  );

  const handleCopy = useCallback(() => {
    const text = getCellValues(table, selectedCells);
    navigator.clipboard.writeText(text);
    setCopiedCells(selectedCells);
    setTimeout(() => {
      setCopiedCells([]);
    }, 500);
  }, [selectedCells, table]);

  const navigateHome = useCallback(() => {
    const firstCell = table.getRowModel().rows[0]?.getAllCells()[0];
    if (!firstCell) {
      return;
    }
    setSelectedCells([getCellSelectionData(firstCell)]);
    scrollToRow?.(0);
  }, [table, scrollToRow, getCellSelectionData]);

  const navigateEnd = useCallback(() => {
    const lastRow =
      table.getRowModel().rows[table.getRowModel().rows.length - 1];
    const lastCell = lastRow?.getAllCells()[lastRow.getAllCells().length - 1];
    if (!lastCell) {
      return;
    }
    setSelectedCells([getCellSelectionData(lastCell)]);
    scrollToRow?.(table.getRowModel().rows.length);
  }, [table, scrollToRow, getCellSelectionData]);

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
        case "Home":
          e.preventDefault();
          navigateHome();
          break;
        case "End":
          e.preventDefault();
          navigateEnd();
          break;
      }
    },
    [
      handleCopy,
      navigateDown,
      navigateUp,
      navigateLeft,
      navigateRight,
      navigateHome,
      navigateEnd,
    ],
  );

  const updateRangeSelection = useCallback(
    (cell: Cell<unknown, unknown>) => {
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
    (e: React.MouseEvent<HTMLElement>, cell: Cell<unknown, unknown>) => {
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

  const handleCellMouseUp = useCallback(
    (_e: React.MouseEvent<HTMLElement>, _cell: Cell<unknown, unknown>) => {
      setIsMouseDown(false);
    },
    [],
  );

  const handleCellMouseOver = useCallback(
    (e: React.MouseEvent<HTMLElement>, cell: Cell<unknown, unknown>) => {
      if (e.buttons !== 1) {
        return;
      }
      if (isMouseDown) {
        updateRangeSelection(cell);
      }
    },
    [isMouseDown, updateRangeSelection],
  );

  const isRowSelected = useCallback(
    (rowId: string) => selectedCells.some((c) => c.rowId === rowId),
    [selectedCells],
  );

  const isCellSelected = useCallback(
    (cell: Cell<unknown, unknown>) =>
      selectedCells.some((c) => c.cellId === cell.id),
    [selectedCells],
  );

  const isCellCopied = useCallback(
    (cell: Cell<unknown, unknown>) =>
      copiedCells.some((c) => c.cellId === cell.id),
    [copiedCells],
  );

  return {
    handleCellMouseDown,
    handleCellMouseUp,
    handleCellMouseOver,
    handleCellsKeyDown,
    isCellSelected,
    isRowSelected,
    isCellCopied,
  };
};

// Helper functions
const getCellValues = (
  table: Table<unknown>,
  cells: SelectedCell[],
): string => {
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
        .map((cell) => cell.getValue());
      return cellValues.join("\t");
    })
    .join("\n");
};

const getCellsBetween = (
  table: Table<unknown>,
  cell1: SelectedCell,
  cell2: SelectedCell,
): SelectedCell[] => {
  const cell1Data = table
    .getRow(cell1.rowId)
    .getAllCells()
    .find((c) => c.id === cell1.cellId);
  const cell2Data = table
    .getRow(cell2.rowId)
    .getAllCells()
    .find((c) => c.id === cell2.cellId);
  if (!cell1Data || !cell2Data) {
    return [];
  }

  const rows = table.getRowModel().rows;
  const cell1RowIndex = rows.findIndex(({ id }) => id === cell1Data.row.id);
  const cell2RowIndex = rows.findIndex(({ id }) => id === cell2Data.row.id);
  const cell1ColumnIndex = cell1Data.column.getIndex();
  const cell2ColumnIndex = cell2Data.column.getIndex();

  const selectedRows = rows.slice(
    Math.min(cell1RowIndex, cell2RowIndex),
    Math.max(cell1RowIndex, cell2RowIndex) + 1,
  );

  const columns = table
    .getAllColumns()
    .slice(
      Math.min(cell1ColumnIndex, cell2ColumnIndex),
      Math.max(cell1ColumnIndex, cell2ColumnIndex) + 1,
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
};
