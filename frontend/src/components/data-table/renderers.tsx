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

export function renderTableBody<TData>(
  table: Table<TData>,
  columns: Array<ColumnDef<TData>>,
  isSelectionPanelOpen?: boolean,
  getRowIndex?: (row: TData, idx: number) => number,
): JSX.Element {
  const renderCells = (row: Row<TData>, cells: Array<Cell<TData, unknown>>) => {
    return cells.map((cell) => {
      const { className, style: pinningstyle } = getPinningStyles(cell.column);
      const style = Object.assign(
        {},
        cell.getUserStyling?.() || {},
        pinningstyle,
      );
      return (
        <TableCell
          key={cell.id}
          className={cn(
            "whitespace-pre truncate max-w-[300px]",
            cell.column.getColumnWrapping &&
              cell.column.getColumnWrapping() === "wrap" &&
              "whitespace-pre-wrap min-w-[200px]",
            "px-1.5 py-[0.18rem]",
            className,
          )}
          style={style}
          title={String(cell.getValue())}
        >
          {flexRender(cell.column.columnDef.cell, cell.getContext())}
        </TableCell>
      );
    });
  };

  const handleRowClick = (row: Row<TData>) => {
    const rowIndex = getRowIndex?.(row.original, row.index) ?? row.index;
    row.focusRow?.(rowIndex);
  };

  return (
    <TableBody>
      {table.getRowModel().rows?.length ? (
        table.getRowModel().rows.map((row) => (
          <TableRow
            key={row.id}
            data-state={row.getIsSelected() && "selected"}
            // These classes ensure that empty rows (nulls) still render
            className={cn(
              "border-t h-6",
              isSelectionPanelOpen && "cursor-pointer",
            )}
            onClick={() => handleRowClick(row)}
          >
            {renderCells(row, row.getLeftVisibleCells())}
            {renderCells(row, row.getCenterVisibleCells())}
            {renderCells(row, row.getRightVisibleCells())}
          </TableRow>
        ))
      ) : (
        <TableRow>
          <TableCell colSpan={columns.length} className="h-24 text-center">
            No results.
          </TableCell>
        </TableRow>
      )}
    </TableBody>
  );
}

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
