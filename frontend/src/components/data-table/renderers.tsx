/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import {
  type Cell,
  type Column,
  type ColumnDef,
  flexRender,
  type HeaderGroup,
  type Row,
  type Table,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { type JSX, useLayoutEffect, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/utils/cn";
import { getCellDomProps } from "./cell-utils";
import { COLUMN_WRAPPING_STYLES } from "./column-wrapping/feature";
import { DataTableContextMenu } from "./context-menu";
import { CellRangeSelectionIndicator } from "./range-focus/cell-selection-indicator";
import { useCellRangeSelection } from "./range-focus/use-cell-range-selection";
import { useScrollIntoViewOnFocus } from "./range-focus/use-scroll-into-view";
import { AUTO_WIDTH_MAX_COLUMNS, TABLE_ROW_HEIGHT_PX } from "./types";
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
              "h-auto min-h-10 whitespace-pre align-top border-r border-r-border/75",
              className,
            )}
            style={style}
            ref={(thead) => {
              columnSizingHandler({ table, column: header.column, thead });
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
        {table.getAllColumns().length <= AUTO_WIDTH_MAX_COLUMNS && (
          <th
            className="w-full border-0"
            aria-hidden="true"
            role="presentation"
          />
        )}
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
  virtualize?: boolean;
}

export const DataTableBody = <TData,>({
  table,
  columns,
  rowViewerPanelOpen,
  getRowIndex,
  viewedRowIdx,
  virtualize = false,
}: DataTableBodyProps<TData>) => {
  const rows = table.getRowModel().rows;

  // Find the scroll container (tbody -> table -> overflow-auto wrapper div).
  // Using useState so that when the element becomes available after mount,
  // useVirtualizer re-observes the correct element.
  const [scrollElement, setScrollElement] = useState<HTMLElement | null>(null);
  const tableRef = useRef<HTMLTableSectionElement>(null);
  useLayoutEffect(() => {
    // tbody.parentElement = table, table.parentElement = overflow wrapper
    setScrollElement(tableRef.current?.parentElement?.parentElement ?? null);
  }, []);

  // Always call useVirtualizer (rules of hooks); count=0 when not virtualizing
  const virtualizer = useVirtualizer({
    count: virtualize ? rows.length : 0,
    getScrollElement: () => scrollElement,
    estimateSize: () => TABLE_ROW_HEIGHT_PX,
    overscan: 10,
  });

  // Automatically scroll focused cells into view.
  // In virtual mode, off-screen cells won't be in the DOM so this silently no-ops for them.
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
      const isCellSelected = cell.getIsSelected?.() || false;
      return (
        <TableCell
          tabIndex={0}
          {...getCellDomProps(cell.id)}
          key={cell.id}
          className={cn(
            "whitespace-pre truncate max-w-[300px] border-r border-r-border/75",
            isCellSelected
              ? "outline outline-2 outline-(--blue-7) -outline-offset-2"
              : "outline-hidden",
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

  const renderRow = (row: Row<TData>) => {
    // Only find the row index if the row viewer panel is open
    const rowIndex = rowViewerPanelOpen
      ? (getRowIndex?.(row.original, row.index) ?? row.index)
      : undefined;
    const isRowViewedInPanel = rowViewerPanelOpen && viewedRowIdx === rowIndex;

    // Compute hover title once per row using all visible cells
    let rowTitle: string | undefined;
    if (hoverTemplate) {
      const visibleCells = row.getVisibleCells?.() ?? [
        ...row.getLeftVisibleCells(),
        ...row.getCenterVisibleCells(),
        ...row.getRightVisibleCells(),
      ];
      rowTitle = applyHoverTemplate(hoverTemplate, visibleCells);
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
        {columns.length <= AUTO_WIDTH_MAX_COLUMNS && (
          <td className="border-0" aria-hidden="true" role="presentation" />
        )}
      </TableRow>
    );
  };

  const hasFillerColumn = columns.length <= AUTO_WIDTH_MAX_COLUMNS;
  const totalColSpan = columns.length + (hasFillerColumn ? 1 : 0);

  const renderRows = () => {
    if (rows.length === 0) {
      return (
        <TableRow>
          <TableCell colSpan={totalColSpan} className="h-24 text-center">
            No results.
          </TableCell>
        </TableRow>
      );
    }

    if (virtualize) {
      const virtualItems = virtualizer.getVirtualItems();
      const totalSize = virtualizer.getTotalSize();
      return (
        <>
          {virtualItems[0]?.start > 0 && (
            <tr
              data-virtual-spacer=""
              style={{ height: virtualItems[0].start }}
            >
              <td colSpan={totalColSpan} />
            </tr>
          )}
          {virtualItems.map((vItem) => renderRow(rows[vItem.index]))}
          {virtualItems.length > 0 && (
            <tr
              data-virtual-spacer=""
              style={{
                height: totalSize - (virtualItems.at(-1)?.end ?? totalSize),
              }}
            >
              <td colSpan={totalColSpan} />
            </tr>
          )}
        </>
      );
    }

    return rows.map((row) => renderRow(row));
  };

  const tableBody = (
    <TableBody onKeyDown={handleCellsKeyDown} ref={tableRef}>
      {renderRows()}
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
function columnSizingHandler<TData>({
  table,
  column,
  thead,
}: {
  table: Table<TData>;
  column: Column<TData>;
  thead: HTMLTableCellElement | null;
}): void {
  if (!thead) {
    return;
  }
  // Round to avoid infinite re-render loops: the browser's table layout
  // algorithm may render a <th> at a slightly different width than the
  // CSS `width` we set via column.getSize(), so a strict float === float
  // comparison never stabilizes. Rounding to integers ensures convergence
  // after at most one cycle.
  const measuredWidth = Math.round(thead.getBoundingClientRect().width);
  if (table.getState().columnSizing[column.id] === measuredWidth) {
    return;
  }

  table.setColumnSizing((prevSizes) => ({
    ...prevSizes,
    [column.id]: measuredWidth,
  }));
}
