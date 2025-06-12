/* Copyright 2024 Marimo. All rights reserved. */

import { useCallback, useState } from "react";
import type { Cell, Table } from "@tanstack/react-table";
import { renderUnknownValue } from "../renderers";
import { copyToClipboard } from "@/utils/copy";
import useEvent from "react-use-event-hook";

export interface SelectedCell {
  rowId: string;
  columnId: string;
  cellId: string; // unique id for the cell
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

  const [isSelecting, setIsSelecting] = useState(false);

  const isCellSelected = useCallback(
    (cellId: string) => {
      return selectedCells.has(cellId);
    },
    [selectedCells],
  );

  const isCellCopied = useCallback(
    (cellId: string) => {
      return copiedCells.has(cellId);
    },
    [copiedCells],
  );

  const handleCopy = useEvent(() => {
    const text = getCellValues(table, selectedCells);
    copyToClipboard(text);
    setCopiedCells(selectedCells);
    setTimeout(() => {
      setCopiedCells(new Map());
    }, 500);
  });

  const updateSelection = (newCell: SelectedCell, isShiftKey: boolean) => {
    if (isShiftKey && selectedStartCell) {
      setSelectedCells(getCellsBetween(table, selectedStartCell, newCell));
      // Do not update selectedStartCell
      setFocusedCell(newCell);
    } else {
      setSelectedCells(new Map([[newCell.cellId, newCell]]));
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

    const selectedCellsInRange = getCellsBetween(
      table,
      selectedStartCell,
      selectedCell,
    );

    setSelectedCells(selectedCellsInRange);
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
          setSelectedCells(new Map());
          setSelectedStartCell(null);
          setFocusedCell(null);
          return;
        }

        setSelectedCells(new Map([[selectedCell.cellId, selectedCell]]));
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
        const uniqueId = cell.id;
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
