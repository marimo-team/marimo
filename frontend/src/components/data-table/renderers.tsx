/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import {
  type Cell,
  type Column,
  type ColumnDef,
  flexRender,
  type HeaderGroup,
  type Row,
  type Table,
  type Table as TanStackTable,
} from "@tanstack/react-table";
import { type JSX, useRef } from "react";
import useEvent from "react-use-event-hook";
import {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/utils/cn";
import { COLUMN_WRAPPING_STYLES } from "./column-wrapping/feature";
import { DataTableContextMenu } from "./context-menu";
import { CellRangeSelectionIndicator } from "./range-focus/cell-selection-indicator";
import { useCellRangeSelection } from "./range-focus/use-cell-range-selection";
import { useScrollIntoViewOnFocus } from "./range-focus/use-scroll-into-view";
import { stringifyUnknownValue } from "./utils";

export function renderTableHeader<TData>(
  table: Table<TData>,
  isSticky?: boolean,
): JSX.Element | null {
  if (!table.getRowModel().rows?.length) {
    return null;
  }

  const renderHeaderGroup = (headerGroups: HeaderGroup<TData>[]) => {
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
            ref={(thead) => {
              columnSizingHandler(thead, table, header.column);
            }}
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
    <TableHeader className={cn(isSticky && "sticky top-0 z-10")}>
      <TableRow>
        {renderHeaderGroup(table.getLeftHeaderGroups())}
        {renderHeaderGroup(table.getCenterHeaderGroups())}
        {renderHeaderGroup(table.getRightHeaderGroups())}
      </TableRow>
    </TableHeader>
  );
}

interface DataTableBodyProps<TData> {
  table: Table<TData>;
  columns: ColumnDef<TData>[];
  rowViewerPanelOpen: boolean;
  getRowIndex?: (row: TData, idx: number) => number;
  viewedRowIdx?: number;
}

export const DataTableBody = <TData,>({
  table,
  columns,
  rowViewerPanelOpen,
  getRowIndex,
  viewedRowIdx,
}: DataTableBodyProps<TData>) => {
  // Automatically scroll focused cells into view
  const tableRef = useRef<HTMLTableSectionElement>(null);
  useScrollIntoViewOnFocus(tableRef);

  const {
    handleCellMouseDown,
    handleCellMouseUp,
    handleCellMouseOver,
    handleCellsKeyDown,
    handleCopy: handleCopyAllCells,
  } = useCellRangeSelection({ table });

  const contextMenuCell = useRef<Cell<TData, unknown> | null>(null);
  const handleContextMenu = useEvent((cell: Cell<TData, unknown>) => {
    contextMenuCell.current = cell;
  });

  function applyHoverTemplate(
    template: string,
    cells: Cell<TData, unknown>[],
  ): string {
    const variableRegex = /{{(\w+)}}/g;
    // Map column id -> stringified value
    const idToValue = new Map<string, string>();
    for (const c of cells) {
      const v = c.getValue();
      // Prefer empty string for nulls to keep tooltip clean
      const s = stringifyUnknownValue({ value: v, nullAsEmptyString: true });
      idToValue.set(c.column.id, s);
    }
    return template.replaceAll(variableRegex, (_substr, varName: string) => {
      const val = idToValue.get(varName);
      return val === undefined ? `{{${varName}}}` : val;
    });
  }

  const renderCells = (cells: Cell<TData, unknown>[]) => {
    return cells.map((cell) => {
      const { className, style: pinningstyle } = getPinningStyles(cell.column);
      const style = Object.assign(
        {},
        cell.getUserStyling?.() || {},
        pinningstyle,
      );

      const title = cell.getHoverTitle?.() ?? undefined;
      return (
        <TableCell
          tabIndex={0}
          data-cell-id={cell.id}
          key={cell.id}
          className={cn(
            "whitespace-pre truncate max-w-[300px] outline-hidden",
            cell.column.getColumnWrapping &&
              cell.column.getColumnWrapping?.() === "wrap" &&
              COLUMN_WRAPPING_STYLES,
            "px-1.5 py-[0.18rem]",
            className,
          )}
          style={style}
          title={title}
          onMouseDown={(e) => handleCellMouseDown(e, cell)}
          onMouseUp={handleCellMouseUp}
          onMouseOver={(e) => handleCellMouseOver(e, cell)}
          onContextMenu={() => handleContextMenu(cell)}
        >
          <CellRangeSelectionIndicator cellId={cell.id} />
          <div className="relative">
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </div>
        </TableCell>
      );
    });
  };

  const handleRowClick = (row: Row<TData>) => {
    if (rowViewerPanelOpen) {
      const rowIndex = getRowIndex?.(row.original, row.index) ?? row.index;
      row.focusRow?.(rowIndex);
    }
  };

  const hoverTemplate = table.getState().cellHoverTemplate || null;

  const tableBody = (
    <TableBody onKeyDown={handleCellsKeyDown} ref={tableRef}>
      {table.getRowModel().rows?.length ? (
        table.getRowModel().rows.map((row) => {
          // Only find the row index if the row viewer panel is open
          const rowIndex = rowViewerPanelOpen
            ? (getRowIndex?.(row.original, row.index) ?? row.index)
            : undefined;
          const isRowViewedInPanel =
            rowViewerPanelOpen && viewedRowIdx === rowIndex;

          // Compute hover title once per row using all visible cells
          let rowTitle: string | undefined;
          if (hoverTemplate) {
            const visibleCells = row.getVisibleCells?.() ?? [
              ...row.getLeftVisibleCells(),
              ...row.getCenterVisibleCells(),
              ...row.getRightVisibleCells(),
            ];
            rowTitle = hoverTemplate
              ? applyHoverTemplate(hoverTemplate, visibleCells)
              : undefined;
          }

          return (
            <TableRow
              key={row.id}
              data-state={row.getIsSelected() && "selected"}
              title={rowTitle}
              // These classes ensure that empty rows (nulls) still render
              className={cn(
                "border-t h-6",
                rowViewerPanelOpen && "cursor-pointer",
                isRowViewedInPanel &&
                  "bg-(--blue-3) hover:bg-(--blue-3) data-[state=selected]:bg-(--blue-4)",
              )}
              onClick={() => handleRowClick(row)}
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

  return (
    <DataTableContextMenu
      tableBody={tableBody}
      contextMenuRef={contextMenuCell}
      tableRef={tableRef}
      copyAllCells={handleCopyAllCells}
    />
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
