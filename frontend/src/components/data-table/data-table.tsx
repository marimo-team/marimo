/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo, useEffect, useState } from "react";
import {
  type Column,
  type ColumnDef,
  type ColumnFiltersState,
  ColumnPinning,
  type ColumnPinningState,
  type OnChangeFn,
  type PaginationState,
  type Row,
  type RowSelectionState,
  type SortingState,
  type Table as TanStackTable,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DataTablePagination } from "./pagination";
import { type DownloadActionProps, DownloadAs } from "./download-actions";
import { cn } from "@/utils/cn";
import { SearchIcon } from "lucide-react";
import { Button } from "../ui/button";
import { useDebounce } from "@uidotdev/usehooks";
import useEvent from "react-use-event-hook";
import { Tooltip } from "../ui/tooltip";
import { Spinner } from "../icons/spinner";
import { FilterPills } from "./filter-pills";
import { ColumnWrappingFeature } from "./column-wrapping/feature";
import { ColumnFormattingFeature } from "./column-formatting/feature";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { SELECT_COLUMN_ID } from "./types";

interface DataTableProps<TData> extends Partial<DownloadActionProps> {
  wrapperClassName?: string;
  className?: string;
  columns: Array<ColumnDef<TData>>;
  data: TData[];
  // Sorting
  sorting?: SortingState;
  setSorting?: OnChangeFn<SortingState>;
  // Pagination
  totalRows: number | "too_many";
  pagination?: boolean;
  paginationState?: PaginationState;
  setPaginationState?: OnChangeFn<PaginationState>;
  // Selection
  selection?: "single" | "multi" | null;
  rowSelection?: RowSelectionState;
  onRowSelectionChange?: OnChangeFn<RowSelectionState>;
  // Search
  enableSearch?: boolean;
  searchQuery?: string;
  onSearchQueryChange?: (query: string) => void;
  showFilters?: boolean;
  filters?: ColumnFiltersState;
  onFiltersChange?: OnChangeFn<ColumnFiltersState>;
  reloading?: boolean;
  // Columns
  freezeColumnsLeft?: string[];
  freezeColumnsRight?: string[];
}

const DataTableInternal = <TData,>({
  wrapperClassName,
  className,
  columns,
  data,
  sorting,
  totalRows,
  setSorting,
  rowSelection,
  paginationState,
  setPaginationState,
  downloadAs,
  pagination = false,
  onRowSelectionChange,
  enableSearch = false,
  searchQuery,
  onSearchQueryChange,
  showFilters = false,
  filters,
  onFiltersChange,
  reloading,
  freezeColumnsLeft,
  freezeColumnsRight,
}: DataTableProps<TData>) => {
  const [isSearchEnabled, setIsSearchEnabled] = React.useState<boolean>(false);
  const [columnPinning, setColumnPinning] = React.useState<ColumnPinningState>({
    left: freezeColumnsLeft
      ? [SELECT_COLUMN_ID, ...freezeColumnsLeft]
      : [SELECT_COLUMN_ID],
    right: freezeColumnsRight,
  });

  const table = useReactTable<TData>({
    _features: [ColumnPinning, ColumnWrappingFeature, ColumnFormattingFeature],
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    // pagination
    rowCount: totalRows === "too_many" ? undefined : totalRows,
    ...(setPaginationState
      ? {
          manualPagination: true,
          onPaginationChange: setPaginationState,
          getRowId: (_row, idx) => {
            if (!paginationState) {
              return String(idx);
            }
            // Add offset if pagination is enabled
            const offset = pagination
              ? paginationState.pageIndex * paginationState.pageSize
              : 0;
            return String(idx + offset);
          },
        }
      : {}),
    getPaginationRowModel: pagination ? getPaginationRowModel() : undefined,
    // sorting
    onSortingChange: setSorting,
    manualSorting: true,
    getSortedRowModel: getSortedRowModel(),
    // filtering
    manualFiltering: true,
    enableColumnFilters: showFilters,
    getFilteredRowModel: getFilteredRowModel(),
    onColumnFiltersChange: onFiltersChange,
    // selection
    onRowSelectionChange: onRowSelectionChange,
    state: {
      sorting,
      columnFilters: filters,
      pagination: pagination
        ? paginationState
        : { pageIndex: 0, pageSize: data.length },
      rowSelection,
      columnPinning: columnPinning,
    },
    onColumnPinningChange: setColumnPinning,
  });

  useEffect(() => {
    setColumnPinning({
      left:
        !freezeColumnsLeft || freezeColumnsLeft?.includes(SELECT_COLUMN_ID)
          ? freezeColumnsLeft
          : [SELECT_COLUMN_ID, ...freezeColumnsLeft],
      right: freezeColumnsRight,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [useDeepCompareMemoize([freezeColumnsLeft, freezeColumnsRight])]);

  const getPinningStyles = (
    column: Column<TData>,
  ): React.HTMLAttributes<HTMLElement> => {
    const isPinned = column.getIsPinned();
    const isLastLeftPinnedColumn =
      isPinned === "left" && column.getIsLastColumn("left");
    const isFirstRightPinnedColumn =
      isPinned === "right" && column.getIsFirstColumn("right");

    return {
      className: cn(isPinned && "bg-background", "shadow-r z-10"),
      style: {
        boxShadow:
          isLastLeftPinnedColumn && column.id !== "__select__"
            ? "-4px 0 4px -4px var(--slate-8) inset"
            : isFirstRightPinnedColumn
              ? "4px 0 4px -4px var(--slate-8) inset"
              : undefined,
        left: isPinned === "left" ? `${column.getStart("left")}px` : undefined,
        right:
          isPinned === "right" ? `${column.getAfter("right")}px` : undefined,
        opacity: 1,
        position: isPinned ? "sticky" : "relative",
        zIndex: isPinned ? 1 : 0,
        width: column.getSize(),
      },
    };
  };

  // Update column sizes in table state for column pinning offsets
  // https://github.com/TanStack/table/discussions/3947#discussioncomment-9564867
  const columnSizingHandler = (
    thead: HTMLTableCellElement | null,
    table: TanStackTable<TData>,
    column: Column<TData>,
  ) => {
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
  };

  const renderHeader = (position: "left" | "center" | "right") => {
    // Hide header if no results
    if (!table.getRowModel().rows?.length) {
      return;
    }

    const headerGroups =
      position === "left"
        ? table.getLeftHeaderGroups()
        : position === "right"
          ? table.getRightHeaderGroups()
          : table.getCenterHeaderGroups();

    // whitespace-pre so that strings with different whitespace look
    // different
    return headerGroups.map((headerGroup) =>
      headerGroup.headers.map((header) => {
        const { className, style } = getPinningStyles(header.column);
        return (
          <TableHead
            key={header.id}
            className={cn(
              "h-auto min-h-10 whitespace-pre align-baseline",
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

  const renderCells = (
    row: Row<TData>,
    position: "left" | "center" | "right",
  ) => {
    const cells =
      position === "left"
        ? row.getLeftVisibleCells()
        : position === "right"
          ? row.getRightVisibleCells()
          : row.getCenterVisibleCells();

    return cells.map((cell) => {
      const { className, style } = getPinningStyles(cell.column);
      return (
        <TableCell
          key={cell.id}
          className={cn(
            "whitespace-pre truncate max-w-[300px]",
            cell.column.getColumnWrapping &&
              cell.column.getColumnWrapping() === "wrap" &&
              "whitespace-pre-wrap min-w-[200px]",
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

  return (
    <div className={cn(wrapperClassName, "flex flex-col space-y-1")}>
      <FilterPills filters={filters} table={table} />
      <div className={cn(className || "rounded-md border overflow-hidden")}>
        {onSearchQueryChange && enableSearch && (
          <SearchBar
            value={searchQuery || ""}
            onHide={() => setIsSearchEnabled(false)}
            handleSearch={onSearchQueryChange}
            hidden={!isSearchEnabled}
            reloading={reloading}
          />
        )}
        <Table>
          <TableHeader>
            {renderHeader("left")}
            {renderHeader("center")}
            {renderHeader("right")}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                  onClick={() => {
                    // If we have any row selected, make the row
                    // toggle selection on click
                    if (table.getIsSomeRowsSelected()) {
                      row.toggleSelected();
                    }
                  }}
                >
                  {renderCells(row, "left")}
                  {renderCells(row, "center")}
                  {renderCells(row, "right")}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between flex-shrink-0 pt-1">
        {onSearchQueryChange && enableSearch && (
          <Tooltip content="Search">
            <Button
              variant="text"
              size="xs"
              className="mb-0"
              onClick={() => setIsSearchEnabled(!isSearchEnabled)}
            >
              <SearchIcon className="w-4 h-4 text-muted-foreground" />
            </Button>
          </Tooltip>
        )}
        {pagination ? (
          <DataTablePagination
            onSelectAllRowsChange={
              onRowSelectionChange
                ? (value) => {
                    if (value) {
                      const allKeys = Array.from(
                        { length: table.getRowCount() },
                        (_, i) => [i, true] as const,
                      );
                      onRowSelectionChange(Object.fromEntries(allKeys));
                    } else {
                      onRowSelectionChange({});
                    }
                  }
                : undefined
            }
            table={table}
          />
        ) : (
          <div />
        )}
        {downloadAs && <DownloadAs downloadAs={downloadAs} />}
      </div>
    </div>
  );
};

const SearchBar = (props: {
  hidden: boolean;
  value: string;
  handleSearch: (query: string) => void;
  onHide: () => void;
  reloading?: boolean;
}) => {
  const { reloading, value, handleSearch, hidden, onHide } = props;
  const [internalValue, setInternalValue] = useState(value);
  const debouncedSearch = useDebounce(internalValue, 500);
  const onSearch = useEvent(handleSearch);
  const ref = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    onSearch(debouncedSearch);
  }, [debouncedSearch, onSearch]);

  useEffect(() => {
    if (hidden) {
      // Closing, reset
      setInternalValue("");
    } else {
      // Opening, focus
      ref.current?.focus();
    }
  }, [hidden]);

  return (
    <div
      className={cn(
        "flex items-center space-x-2 h-8 px-2 border-b transition-all overflow-hidden duration-300 opacity-100",
        hidden && "h-0 border-none opacity-0",
      )}
    >
      <SearchIcon className="w-4 h-4 text-muted-foreground" />
      <input
        type="text"
        ref={ref}
        className="w-full h-full border-none bg-transparent focus:outline-none text-sm"
        value={internalValue}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            onHide();
          }
        }}
        onChange={(e) => setInternalValue(e.target.value)}
        placeholder="Search"
      />
      {reloading && <Spinner size="small" />}
    </div>
  );
};

export const DataTable = memo(DataTableInternal) as typeof DataTableInternal;
