/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import {
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import {
  flexRender,
  type Table,
  type ColumnDef,
  type Row,
  type Column,
  type Table as TanStackTable,
  type HeaderGroup,
  type Cell,
} from "@tanstack/react-table";
import { cn } from "@/utils/cn";
import { useCellSelection } from "@/components/data-table/hooks/use-cell-range-selection";
import React, { useMemo } from "react";

export function renderTableHeader<TData>(
  table: Table<TData>,
): JSX.Element | null {
  if (!table.getRowModel().rows?.length) {
    return null;
  }

  const renderHeaderGroup = (headerGroups: Array<HeaderGroup<TData>>) => {
    return headerGroups.map((headerGroup) =>
      headerGroup.headers.map((header) => {
        const { className, style } = getPinningStyles(header.column);
        return (
          <TableHead
            key={header.id}
            className={cn(
              "h-auto min-h-10 whitespace-pre align-top",
              className,
            )}
            style={style}
            ref={(thead) => columnSizingHandler(thead, table, header.column)}
          >
            {header.isPlaceholder
              ? null
              : flexRender(header.column.columnDef.header, header.getContext())}
          </TableHead>
        );
      }),
    );
  };

  return (
    <TableHeader>
      {renderHeaderGroup(table.getLeftHeaderGroups())}
      {renderHeaderGroup(table.getCenterHeaderGroups())}
      {renderHeaderGroup(table.getRightHeaderGroups())}
    </TableHeader>
  );
}

export const DataTableBody = <TData,>({
  table,
  columns,
  rowViewerPanelOpen,
  getRowIndex,
  viewedRowIdx,
  tableBodyRef,
}: {
  table: Table<TData>;
  columns: Array<ColumnDef<TData>>;
  rowViewerPanelOpen: boolean;
  getRowIndex?: (row: TData, idx: number) => number;
  viewedRowIdx?: number;
  tableBodyRef?: React.RefObject<HTMLTableSectionElement>;
}): JSX.Element => {
  const {
    handleCellMouseDown,
    handleCellMouseUp,
    handleCellMouseOver,
    handleCellsKeyDown,
    isCellSelected,
    isCellCopied,
  } = useCellSelection({
    table,
  });

  const renderCells = (cells: Array<Cell<TData, unknown>>) => {
    return cells.map((cell) => {
      return (
        <MemoizedTableCell
          key={cell.id}
          cell={cell}
          isSelected={isCellSelected(cell)}
          isCopied={isCellCopied(cell)}
          onMouseDown={handleCellMouseDown}
          onMouseUp={handleCellMouseUp}
          onMouseOver={handleCellMouseOver}
        />
      );
    });
  };

  const handleRowClick = (row: Row<TData>) => {
    const rowIndex = getRowIndex?.(row.original, row.index) ?? row.index;
    row.focusRow?.(rowIndex);
  };

  return (
    <TableBody ref={tableBodyRef} onKeyDown={handleCellsKeyDown} tabIndex={-1}>
      {table.getRowModel().rows?.length ? (
        table.getRowModel().rows.map((row) => {
          const rowIndex = rowViewerPanelOpen
            ? (getRowIndex?.(row.original, row.index) ?? row.index)
            : undefined;
          const isRowViewedInPanel =
            rowViewerPanelOpen && viewedRowIdx === rowIndex;

          return (
            <TableRow
              key={row.id}
              data-state={row.getIsSelected() && "selected"}
              // These classes ensure that empty rows (nulls) still render
              className={cn(
                "border-t h-6",
                rowViewerPanelOpen && "cursor-pointer",
                isRowViewedInPanel &&
                  "bg-[var(--blue-3)] hover:bg-[var(--blue-3)] data-[state=selected]:bg-[var(--blue-4)]",
              )}
              onClick={() => handleRowClick(row)}
              tabIndex={-1}
            >
              {renderCells(row.getLeftVisibleCells())}
              {renderCells(row.getCenterVisibleCells())}
              {renderCells(row.getRightVisibleCells())}
            </TableRow>
          );
        })
      ) : (
        <TableRow>
          <TableCell colSpan={columns.length} className="h-24 text-center">
            No results.
          </TableCell>
        </TableRow>
      )}
    </TableBody>
  );
};

function getPinningStyles<TData>(
  column: Column<TData>,
): React.HTMLAttributes<HTMLElement> {
  const isPinned = column.getIsPinned();
  const isLastLeftPinnedColumn =
    isPinned === "left" && column.getIsLastColumn("left");
  const isFirstRightPinnedColumn =
    isPinned === "right" && column.getIsFirstColumn("right");

  return {
    className: cn(isPinned && "bg-inherit", "shadow-r z-10"),
    style: {
      boxShadow:
        isLastLeftPinnedColumn && column.id !== "__select__"
          ? "-4px 0 4px -4px var(--slate-8) inset"
          : isFirstRightPinnedColumn
            ? "4px 0 4px -4px var(--slate-8) inset"
            : undefined,
      left: isPinned === "left" ? `${column.getStart("left")}px` : undefined,
      right: isPinned === "right" ? `${column.getAfter("right")}px` : undefined,
      opacity: 1,
      position: isPinned ? "sticky" : "relative",
      zIndex: isPinned ? 1 : 0,
      width: column.getSize(),
    },
  };
}

interface DataTableCellProps<TData> {
  cell: Cell<TData, unknown>;
  isSelected: boolean;
  isCopied: boolean;
  onMouseDown: (e: React.MouseEvent, cell: Cell<TData, unknown>) => void;
  onMouseUp: () => void;
  onMouseOver: (e: React.MouseEvent, cell: Cell<TData, unknown>) => void;
}

const DataTableCell = <TData,>({
  cell,
  isSelected,
  isCopied,
  onMouseDown,
  onMouseUp,
  onMouseOver,
}: DataTableCellProps<TData>) => {
  const { className: pinClassName, style: pinningStyle } = useMemo(
    () => getPinningStyles(cell.column),
    [cell.column],
  );
  const userStyle = useMemo(() => cell.getUserStyling?.() || {}, [cell]);
  const style = Object.assign({}, userStyle, pinningStyle);

  const className = useMemo(
    () =>
      cn(
        "whitespace-pre truncate max-w-[300px] select-none outline-none",
        cell.column.getColumnWrapping &&
          cell.column.getColumnWrapping() === "wrap" &&
          "whitespace-pre-wrap min-w-[200px]",
        "px-1.5 py-[0.18rem]",
        isSelected && "bg-[var(--green-3)]",
        isCopied && "bg-[var(--green-4)] transition-colors duration-150",
        pinClassName,
      ),
    [cell.column, isCopied, isSelected, pinClassName],
  );

  return (
    <TableCell
      tabIndex={0}
      className={className}
      style={style}
      title={String(cell.getValue())}
      onMouseDown={(e) => onMouseDown(e, cell)}
      onMouseUp={onMouseUp}
      onMouseOver={(e) => onMouseOver(e, cell)}
    >
      {flexRender(cell.column.columnDef.cell, cell.getContext())}
    </TableCell>
  );
};

const MemoizedTableCell = React.memo(DataTableCell, (prev, next) => {
  return (
    prev.isSelected === next.isSelected &&
    prev.isCopied === next.isCopied &&
    prev.cell === next.cell
  );
}) as typeof DataTableCell;

// Update column sizes in table state for column pinning offsets
// https://github.com/TanStack/table/discussions/3947#discussioncomment-9564867
function columnSizingHandler<TData>(
  thead: HTMLTableCellElement | null,
  table: TanStackTable<TData>,
  column: Column<TData>,
) {
  if (!thead) {
    return;
  }
  if (
    table.getState().columnSizing[column.id] ===
    thead.getBoundingClientRect().width
  ) {
    return;
  }

  table.setColumnSizing((prevSizes) => ({
    ...prevSizes,
    [column.id]: thead.getBoundingClientRect().width,
  }));
}

/**
 * Render an unknown value as a string. Converts objects to JSON strings.
 * @param opts.value - The value to render.
 * @param opts.nullAsEmptyString - If true, null values will be "". Else, stringify.
 */
export function renderUnknownValue(opts: {
  value: unknown;
  nullAsEmptyString?: boolean;
}): string {
  const { value, nullAsEmptyString = false } = opts;

  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  if (value === null && nullAsEmptyString) {
    return "";
  }
  return String(value);
}
