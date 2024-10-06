/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo } from "react";
import {
  type ColumnDef,
  type ColumnFiltersState,
  ColumnPinning,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  type OnChangeFn,
  type PaginationState,
  type RowSelectionState,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";

import { Table } from "@/components/ui/table";
import type { DownloadActionProps } from "./download-actions";
import { cn } from "@/utils/cn";
import { FilterPills } from "./filter-pills";
import { useColumnPinning } from "./hooks/useColumnPinning";
import { renderTableHeader, renderTableBody } from "./renderers";
import { SearchBar } from "./SearchBar";
import { TableActions } from "./TableActions";
import { ColumnFormattingFeature } from "./column-formatting/feature";
import { ColumnWrappingFeature } from "./column-wrapping/feature";
import { CellHeatmapFeature } from "./cell-heatmap/feature";

interface DataTableProps<TData> extends Partial<DownloadActionProps> {
  wrapperClassName?: string;
  className?: string;
  columns: Array<ColumnDef<TData>>;
  data: TData[];
  // Sorting
  manualSorting?: boolean; // server-side sorting
  sorting?: SortingState; // controlled sorting
  setSorting?: OnChangeFn<SortingState>; // controlled sorting
  // Pagination
  totalRows: number | "too_many";
  pagination?: boolean;
  manualPagination?: boolean; // server-side pagination
  paginationState?: PaginationState; // controlled pagination
  setPaginationState?: OnChangeFn<PaginationState>; // controlled pagination
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
  // Heatmap
  initialHeatmap?: boolean | string[];
}

const DataTableInternal = <TData,>({
  wrapperClassName,
  className,
  columns,
  data,
  selection,
  totalRows,
  manualSorting = false,
  sorting,
  setSorting,
  rowSelection,
  paginationState,
  setPaginationState,
  downloadAs,
  manualPagination = false,
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
  initialHeatmap = false,
}: DataTableProps<TData>) => {
  const [isSearchEnabled, setIsSearchEnabled] = React.useState<boolean>(false);
  // const [cellHeatmap, setCellHeatmap] = React.useState<boolean>(false);

  const { columnPinning, setColumnPinning } = useColumnPinning(
    freezeColumnsLeft,
    freezeColumnsRight,
  );

  const table = useReactTable<TData>({
    _features: [
      ColumnPinning,
      ColumnWrappingFeature,
      ColumnFormattingFeature,
      CellHeatmapFeature,
    ],
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    // pagination
    rowCount: totalRows === "too_many" ? undefined : totalRows,
    ...(setPaginationState
      ? {
          onPaginationChange: setPaginationState,
          getRowId: (_row, idx) => {
            if (!paginationState) {
              return String(idx);
            }
            // Add offset if manualPagination is enabled
            const offset = manualPagination
              ? paginationState.pageIndex * paginationState.pageSize
              : 0;
            return String(idx + offset);
          },
        }
      : {}),
    manualPagination: manualPagination,
    getPaginationRowModel: getPaginationRowModel(),
    // sorting
    ...(setSorting ? { onSortingChange: setSorting } : {}),
    manualSorting: manualSorting,
    getSortedRowModel: getSortedRowModel(),
    // filtering
    manualFiltering: true,
    enableColumnFilters: showFilters,
    getFilteredRowModel: getFilteredRowModel(),
    onColumnFiltersChange: onFiltersChange,
    // selection
    onRowSelectionChange: onRowSelectionChange,
    initialState: {
      columnHeatmap:
        initialHeatmap === true
          ? // Initialize heatmap state for all columns
            Object.fromEntries(columns.map((column) => [column.id, true]))
          : Array.isArray(initialHeatmap)
            ? Object.fromEntries(
                initialHeatmap.map((columnId) => [columnId, true]),
              )
            : {},
    },
    state: {
      ...(sorting ? { sorting } : {}),
      columnFilters: filters,
      // Controlled state
      ...(paginationState
        ? { pagination: paginationState }
        : // Uncontrolled state
          pagination && !paginationState
          ? {}
          : // No pagination, show all rows
            { pagination: { pageIndex: 0, pageSize: data.length } }),
      rowSelection,
      columnPinning: columnPinning,
    },
    onColumnPinningChange: setColumnPinning,
  });

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
          {renderTableHeader(table)}
          {renderTableBody(table, columns)}
        </Table>
      </div>
      <TableActions
        enableSearch={enableSearch}
        onSearchQueryChange={onSearchQueryChange}
        isSearchEnabled={isSearchEnabled}
        setIsSearchEnabled={setIsSearchEnabled}
        pagination={pagination}
        selection={selection}
        onRowSelectionChange={onRowSelectionChange}
        table={table}
        downloadAs={downloadAs}
      />
    </div>
  );
};

export const DataTable = memo(DataTableInternal) as typeof DataTableInternal;
