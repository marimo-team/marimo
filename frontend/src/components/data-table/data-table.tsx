/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

// tanstack/table is not compatible with React compiler
// https://github.com/TanStack/table/issues/5567

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
import React, { memo } from "react";

import { Table } from "@/components/ui/table";
import type { GetRowIds } from "@/plugins/impl/DataTablePlugin";
import { cn } from "@/utils/cn";
import type { PanelType } from "../editor/chrome/panels/context-aware-panel/context-aware-panel";
import { CellSelectionFeature } from "./cell-selection/feature";
import type { CellSelectionState } from "./cell-selection/types";
import { CellStylingFeature } from "./cell-styling/feature";
import type { CellStyleState } from "./cell-styling/types";
import { ColumnFormattingFeature } from "./column-formatting/feature";
import { ColumnWrappingFeature } from "./column-wrapping/feature";
import { CopyColumnFeature } from "./copy-column/feature";
import type { DownloadActionProps } from "./download-actions";
import { FilterPills } from "./filter-pills";
import { FocusRowFeature } from "./focus-row/feature";
import { useColumnPinning } from "./hooks/use-column-pinning";
import { CellSelectionProvider } from "./range-focus/provider";
import { DataTableBody, renderTableHeader } from "./renderers";
import { SearchBar } from "./SearchBar";
import { TableActions } from "./TableActions";
import type { DataTableSelection, TooManyRows } from "./types";
import { getStableRowId } from "./utils";

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
  totalRows: number | TooManyRows;
  totalColumns: number;
  pagination?: boolean;
  manualPagination?: boolean; // server-side pagination
  paginationState?: PaginationState; // controlled pagination
  setPaginationState?: OnChangeFn<PaginationState>; // controlled pagination
  // Selection
  selection?: DataTableSelection;
  rowSelection?: RowSelectionState;
  cellSelection?: CellSelectionState;
  cellStyling?: CellStyleState | null;
  onRowSelectionChange?: OnChangeFn<RowSelectionState>;
  onCellSelectionChange?: OnChangeFn<CellSelectionState>;
  getRowIds?: GetRowIds;
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
  toggleDisplayHeader?: () => void;
  // Row viewer panel
  showRowViewer?: boolean;
  viewedRowIdx?: number;
  onViewedRowChange?: OnChangeFn<number>;
  // Others
  showChartBuilder?: boolean;
  showPageSizeSelector?: number[] | false;
  showColumnExplorer?: boolean;
  togglePanel?: (panelType: PanelType) => void;
  isPanelOpen?: (panelType: PanelType) => boolean;
}

const DataTableInternal = <TData,>({
  wrapperClassName,
  className,
  columns,
  data,
  selection,
  totalColumns,
  totalRows,
  manualSorting = false,
  sorting,
  setSorting,
  rowSelection,
  cellSelection,
  cellStyling,
  paginationState,
  setPaginationState,
  downloadAs,
  manualPagination = false,
  pagination = false,
  onRowSelectionChange,
  onCellSelectionChange,
  getRowIds,
  enableSearch = false,
  searchQuery,
  onSearchQueryChange,
  showFilters = false,
  filters,
  onFiltersChange,
  reloading,
  freezeColumnsLeft,
  freezeColumnsRight,
  toggleDisplayHeader,
  showChartBuilder,
  showPageSizeSelector,
  showRowViewer,
  showColumnExplorer,
  togglePanel,
  isPanelOpen,
  viewedRowIdx,
  onViewedRowChange,
}: DataTableProps<TData>) => {
  const [isSearchEnabled, setIsSearchEnabled] = React.useState<boolean>(false);
  const [showLoadingBar, setShowLoadingBar] = React.useState<boolean>(false);

  const { columnPinning, setColumnPinning } = useColumnPinning(
    freezeColumnsLeft,
    freezeColumnsRight,
  );

  // Show loading bar only after a short delay to prevent flickering
  React.useEffect(() => {
    let timeoutId: NodeJS.Timeout;

    if (reloading) {
      timeoutId = setTimeout(() => {
        setShowLoadingBar(true);
      }, 300);
    } else {
      setShowLoadingBar(false);
    }

    return () => {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, [reloading]);

  // Returns the row index, accounting for pagination
  function getPaginatedRowIndex(_row: TData, idx: number): number {
    if (!paginationState) {
      return idx;
    }

    // Add offset if manualPagination is enabled
    const offset = manualPagination
      ? paginationState.pageIndex * paginationState.pageSize
      : 0;
    return idx + offset;
  }

  const table = useReactTable<TData>({
    _features: [
      ColumnPinning,
      ColumnWrappingFeature,
      ColumnFormattingFeature,
      CellSelectionFeature,
      CellStylingFeature,
      CopyColumnFeature,
      FocusRowFeature,
    ],
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    // pagination
    rowCount: totalRows === "too_many" ? undefined : totalRows,
    ...(setPaginationState
      ? {
          onPaginationChange: setPaginationState,
          getRowId: (row, idx) => {
            // Prefer stable row ID if it exists
            const stableRowId = getStableRowId(row);
            if (stableRowId) {
              return stableRowId;
            }

            const paginatedRowIndex = getPaginatedRowIndex(row, idx);
            return String(paginatedRowIndex);
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
    onCellSelectionChange: onCellSelectionChange,
    enableCellSelection:
      selection === "single-cell" || selection === "multi-cell",
    enableMultiCellSelection: selection === "multi-cell",
    // pinning
    onColumnPinningChange: setColumnPinning,
    // focus row
    enableFocusRow: true,
    onFocusRowChange: onViewedRowChange,
    // state
    state: {
      ...(sorting ? { sorting } : {}),
      columnFilters: filters,
      ...// Controlled state
      (paginationState
        ? { pagination: paginationState }
        : // Uncontrolled state
          pagination && !paginationState
          ? {}
          : // No pagination, show all rows
            { pagination: { pageIndex: 0, pageSize: data.length } }),
      rowSelection,
      cellSelection,
      cellStyling,
      columnPinning: columnPinning,
    },
  });

  const rowViewerPanelOpen = isPanelOpen?.("row-viewer") ?? false;

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
        <Table className="relative">
          {showLoadingBar && (
            <div className="absolute top-0 left-0 h-[3px] w-1/2 bg-primary animate-slide" />
          )}
          {renderTableHeader(table)}
          <CellSelectionProvider>
            <DataTableBody
              table={table}
              columns={columns}
              rowViewerPanelOpen={rowViewerPanelOpen}
              getRowIndex={getPaginatedRowIndex}
              viewedRowIdx={viewedRowIdx}
            />
          </CellSelectionProvider>
        </Table>
      </div>
      <TableActions
        enableSearch={enableSearch}
        totalColumns={totalColumns}
        onSearchQueryChange={onSearchQueryChange}
        isSearchEnabled={isSearchEnabled}
        setIsSearchEnabled={setIsSearchEnabled}
        pagination={pagination}
        selection={selection}
        onRowSelectionChange={onRowSelectionChange}
        table={table}
        downloadAs={downloadAs}
        getRowIds={getRowIds}
        toggleDisplayHeader={toggleDisplayHeader}
        showChartBuilder={showChartBuilder}
        showPageSizeSelector={showPageSizeSelector}
        showRowViewer={showRowViewer}
        showColumnExplorer={showColumnExplorer}
        togglePanel={togglePanel}
        isPanelOpen={isPanelOpen}
        tableLoading={reloading}
      />
    </div>
  );
};

export const DataTable = memo(DataTableInternal) as typeof DataTableInternal;
