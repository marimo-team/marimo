/* Copyright 2024 Marimo. All rights reserved. */

import type { Column, Row } from "@tanstack/react-table";
import {
  createRef,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

export interface CellCoordinates {
  rowId: string;
  columnId: string;
}

export interface Selection {
  start: CellCoordinates;
  end: CellCoordinates;
}

interface Accumulator {
  [key: string]: number;
}

export function useRangeSelection<TData>(
  rows: Array<Row<TData>>,
  columns: Array<Column<TData>>,
) {
  const [selectedCell, setSelectedCell] = useState<CellCoordinates | null>(
    null,
  );
  const [selection, setSelection] = useState<Selection | null>(null);
  const [isSelecting, setIsSelecting] = useState(false);

  const cellRefs = useRef<{
    [key: string]: React.RefObject<HTMLTableCellElement>;
  }>({});

  // DO we need this? Because this goes through every column and row
  const columnIndexMap = useMemo(() => {
    return columns.reduce((acc: Accumulator, column, index) => {
      acc[column.id] = index;
      return acc;
    }, {});
  }, [columns]);

  const rowIndexMap = useMemo(() => {
    return rows.reduce((acc: Accumulator, row, index) => {
      acc[row.id] = index;
      return acc;
    }, {});
  }, [rows]);

  const getCellRef = (rowId: string, columnId: string) => {
    const key = `${rowId}-${columnId}`;
    if (!cellRefs.current[key]) {
      cellRefs.current[key] = createRef();
    }
    return cellRefs.current[key];
  };

  const isCellSelected = useCallback(
    (cellRowId: string, cellColumnId: string) => {
      return (
        selectedCell?.rowId === cellRowId &&
        selectedCell?.columnId === cellColumnId
      );
    },
    [selectedCell],
  );

  const isCellInRange = useCallback(
    (cellRowId: string, cellColumnId: string) => {
      if (!selection) {
        return false;
      }

      const rowIndex = rowIndexMap[cellRowId];
      const columnIndex = columnIndexMap[cellColumnId];

      const startRowIndex = rowIndexMap[selection.start.rowId];
      const startColumnIndex = columnIndexMap[selection.start.columnId];

      const endRowIndex = rowIndexMap[selection.end.rowId];
      const endColumnIndex = columnIndexMap[selection.end.columnId];

      const isRowInRange =
        rowIndex >= Math.min(startRowIndex, endRowIndex) &&
        rowIndex <= Math.max(startRowIndex, endRowIndex);
      const isColumnInRange =
        columnIndex >= Math.min(startColumnIndex, endColumnIndex) &&
        columnIndex <= Math.max(startColumnIndex, endColumnIndex);

      return isRowInRange && isColumnInRange;
    },
    [columnIndexMap, rowIndexMap, selection],
  );

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLTableCellElement>,
    rowId: string,
    columnId: string,
  ) => {
    const { key, shiftKey } = e;

    if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(key)) {
      e.preventDefault();

      const edgeRowId = selection ? selection.end.rowId : rowId;
      const edgeColumnId = selection ? selection.end.columnId : columnId;

      const rowIndex = rows.findIndex((row) => row.id === edgeRowId);
      const columnIndex = columns.findIndex(
        (column) => column.id === edgeColumnId,
      );

      let nextRowId = edgeRowId;
      let nextColumnId = edgeColumnId;

      switch (key) {
        case "ArrowUp":
          if (rowIndex > 0) {
            nextRowId = rows[rowIndex - 1].id;
          }
          break;
        case "ArrowDown":
          if (rowIndex < rows.length - 1) {
            nextRowId = rows[rowIndex + 1].id;
          }
          break;
        case "ArrowLeft":
          if (columnIndex > 0) {
            nextColumnId = columns[columnIndex - 1].id;
          }
          break;
        case "ArrowRight":
          if (columnIndex < columns.length - 1) {
            nextColumnId = columns[columnIndex + 1].id;
          }
          break;
        default:
          return;
      }

      const nextSelectedCell: CellCoordinates = {
        rowId: nextRowId,
        columnId: nextColumnId,
      };

      if (shiftKey && selectedCell) {
        setSelection((prev) => {
          const start = prev?.start || selectedCell;
          return { start, end: nextSelectedCell };
        });
      } else if (!shiftKey) {
        setSelectedCell(nextSelectedCell);
        setSelection({
          start: nextSelectedCell,
          end: nextSelectedCell,
        });
      }
    }
  };

  const handleMouseDown = useCallback((rowId: string, columnId: string) => {
    setSelectedCell({ rowId, columnId });
    setSelection({
      start: { rowId, columnId },
      end: { rowId, columnId },
    });
    setIsSelecting(true);
  }, []);

  const handleMouseUp = useCallback(() => {
    setIsSelecting(false);
  }, []);

  const handleMouseEnter = useCallback(
    (rowId: string, columnId: string) => {
      if (isSelecting) {
        setSelection((prev) => {
          if (!prev) {
            return null;
          }
          return {
            start: prev.start,
            end: { rowId, columnId },
          };
        });
      }
    },
    [isSelecting],
  );

  const handleClick = useCallback((rowId: string, columnId: string) => {
    setSelectedCell({ rowId, columnId });
  }, []);

  useEffect(() => {
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [handleMouseUp]);

  useLayoutEffect(() => {
    if (selectedCell) {
      const { rowId, columnId } = selectedCell;
      const key = `${rowId}-${columnId}`;
      const cellRef = cellRefs.current[key];
      if (cellRef?.current) {
        cellRef.current.focus();
      }
    }
  }, [selectedCell]);

  return {
    selectedCell,
    selection,
    getCellRef,
    isCellSelected,
    isCellInRange,
    handleClick,
    handleKeyDown,
    handleMouseDown,
    handleMouseEnter,
  };
}
