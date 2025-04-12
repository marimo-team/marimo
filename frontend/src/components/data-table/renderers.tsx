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
              "h-auto min-h-10 whitespace-pre align-top group",
              className,
            )}
            style={{
              ...style,
              // use css calculation instead of table state to improve performance
              width: `calc(var(--header-${header?.id}-size) * 1px)`,
            }}
            // ref={(thead) => columnSizingHandler(thead, table, header.column)}
          >
            {header.isPlaceholder
              ? null
              : flexRender(header.column.columnDef.header, header.getContext())}
            <div
              onDoubleClick={() => header.column.resetSize()}
              onMouseDown={header.getResizeHandler()}
              onTouchStart={header.getResizeHandler()}
              className="absolute top-0 right-0 h-full w-1 cursor-col-resize select-none touch-none"
            >
              {/* Create a blue line that is thinner than the parent div */}
              <div
                className={`absolute h-full w-0.5 left-1/2 -translate-x-1/2 bg-[var(--slate-3)] 
                  dark:bg-slate-600/40 opacity-0 group-hover:opacity-70 rounded ${
                    header.column.getIsResizing() && "opacity-90"
                  }`}
              />
            </div>
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
          style={{
            ...style,
            // use css calculation instead of table state to improve performance
            width: `calc(var(--col-${cell.column.id}-size) * 1px)`,
          }}
          title={String(cell.getValue())}
        >
          {flexRender(cell.column.columnDef.cell, cell.getContext())}
        </TableCell>
      );
    });
  };

  return (
    <TableBody>
      {table.getRowModel().rows?.length ? (
        table.getRowModel().rows.map((row) => (
          <TableRow
            key={row.id}
            data-state={row.getIsSelected() && "selected"}
            // These classes ensure that empty rows (nulls) still render
            className="border-t h-6"
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
