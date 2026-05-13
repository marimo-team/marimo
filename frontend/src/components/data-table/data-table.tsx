/* Copyright 2026 Marimo. All rights reserved. */
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
import { useLocale } from "react-aria";

import { Table } from "@/components/ui/table";
import type {
  CalculateTopKRows,
  GetRowIds,
} from "@/plugins/impl/DataTablePlugin";
import { cn } from "@/utils/cn";
import {
  PANEL_TYPES,
  type PanelType,
} from "../editor/chrome/panels/context-aware-panel/context-aware-panel";
import { CellHoverTemplateFeature } from "./cell-hover-template/feature";
import { CellHoverTextFeature } from "./cell-hover-text/feature";
import { CellSelectionFeature } from "./cell-selection/feature";
import type { CellSelectionState } from "./cell-selection/types";
import { CellStylingFeature } from "./cell-styling/feature";
import type { CellStyleState } from "./cell-styling/types";
import { ColumnFormattingFeature } from "./column-formatting/feature";
import { ColumnWrappingFeature } from "./column-wrapping/feature";
import { CopyColumnFeature } from "./copy-column/feature";
import type { ExportActionProps } from "./export-actions";
import { FilterPills } from "./filter-pills";
import { FocusRowFeature } from "./focus-row/feature";
import { useColumnPinning } from "./hooks/use-column-pinning";
import { useScrollContainerHeight } from "./hooks/use-scroll-container-height";
import { CellSelectionProvider } from "./range-focus/provider";
import { DataTableBody, renderTableHeader } from "./renderers";
import { TableBottomBar } from "./TableBottomBar";
import { TableTopBar } from "./TableTopBar";
import {
  AUTO_WIDTH_MAX_COLUMNS,
  type DataTableSelection,
  MIN_ROWS_TO_VIRTUALIZE,
  type TooManyRows,
} from "./types";
import { getStableRowId } from "./utils";

interface DataTableProps<TData> extends Partial<ExportActionProps> {
  wrapperClassName?: string;
  className?: string;
  maxHeight?: number;
  columns: ColumnDef<TData>[];
  data: TData[];
  rawData?: TData[]; // raw data for filtering/copying (present only if format_mapping is provided)
  // Sorting
  manualSorting?: boolean; // server-side sorting
  sorting?: SortingState; // controlled sorting
  setSorting?: OnChangeFn<SortingState>; // controlled sorting
  // Pagination
  totalRows: number | TooManyRows;
  // JSON-serialized size of the currently-rendered data. Forwarded to
  // ExportMenu so hosts can size-gate the Export button via downloadSizeLimitAtom.
  sizeBytes?: number | null;
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
  hoverTemplate?: string | null;
  cellHoverTexts?: Record<string, Record<string, string | null>> | null;
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
  calculateTopKRows?: CalculateTopKRows;
  reloading?: boolean;
  // Columns
  freezeColumnsLeft?: string[];
  freezeColumnsRight?: string[];
  toggleDisplayHeader?: () => void;
  // Row viewer panel
  viewedRowIdx?: number;
  onViewedRowChange?: OnChangeFn<number>;
  // Others
  showChartBuilder?: boolean;
  isChartBuilderOpen?: boolean;
  showPageSizeSelector?: boolean;
  showTableExplorer?: boolean;
  togglePanel?: (panelType: PanelType) => void;
  isPanelOpen?: (panelType: PanelType) => boolean;
  isAnyPanelOpen?: boolean;
}

const DataTableInternal = <TData,>({
  wrapperClassName,
  className,
  maxHeight,
  columns,
  data,
  rawData,
  selection,
  totalColumns,
  totalRows,
  sizeBytes,
  manualSorting = false,
  sorting,
  setSorting,
  rowSelection,
  cellSelection,
  cellStyling,
  hoverTemplate,
  cellHoverTexts,
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
  calculateTopKRows,
  reloading,
  freezeColumnsLeft,
  freezeColumnsRight,
  toggleDisplayHeader,
  showChartBuilder,
  isChartBuilderOpen,
  showPageSizeSelector,
  showTableExplorer,
  togglePanel,
  isPanelOpen,
  isAnyPanelOpen,
  viewedRowIdx,
  onViewedRowChange,
}: DataTableProps<TData>) => {
  const [showLoadingBar, setShowLoadingBar] = React.useState<boolean>(false);
  const { locale } = useLocale();

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
      CellHoverTextFeature,
      CellHoverTemplateFeature,
      CopyColumnFeature,
      FocusRowFeature,
    ],
    data,
    columns,
    meta: { rawData },
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
    locale: locale,
    manualPagination: manualPagination,
    getPaginationRowModel: getPaginationRowModel(),
    // sorting
    ...(setSorting
      ? {
          onSortingChange: setSorting,
        }
      : {}),
    manualSorting: manualSorting,
    enableMultiSort: true,
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
      rowSelection: rowSelection ?? {},
      cellSelection: cellSelection ?? [],
      cellStyling,
      columnPinning: columnPinning,
      cellHoverTemplate: hoverTemplate,
      cellHoverTexts: cellHoverTexts ?? {},
    },
  });

  const rowViewerPanelOpen = isPanelOpen?.(PANEL_TYPES.ROW_VIEWER) ?? false;
  const virtualize = !pagination && data.length > MIN_ROWS_TO_VIRTUALIZE;

  const tableRef = useScrollContainerHeight({ maxHeight, virtualize });

  return (
    <div className={cn(wrapperClassName, "flex flex-col space-y-1")}>
      <FilterPills
        filters={filters}
        table={table}
        calculateTopKRows={calculateTopKRows}
      />
      <CellSelectionProvider>
        <div
          part="table-wrapper"
          className={cn(className || "rounded-md border overflow-hidden")}
        >
          <TableTopBar
            enableSearch={enableSearch}
            searchQuery={searchQuery}
            onSearchQueryChange={onSearchQueryChange}
            reloading={reloading}
            showChartBuilder={showChartBuilder}
            isChartBuilderOpen={isChartBuilderOpen}
            toggleDisplayHeader={toggleDisplayHeader}
            showTableExplorer={showTableExplorer}
            togglePanel={togglePanel}
            isAnyPanelOpen={isAnyPanelOpen}
            downloadAs={downloadAs}
            sizeBytes={sizeBytes}
          />
          <Table
            className={cn(
              "relative",
              columns.length <= AUTO_WIDTH_MAX_COLUMNS ? "w-auto" : "w-full",
            )}
            ref={tableRef}
          >
            {showLoadingBar && (
              <thead className="absolute top-0 left-0 h-[3px] w-1/2 bg-primary animate-slide" />
            )}
            {renderTableHeader(table, virtualize || Boolean(maxHeight))}
            <DataTableBody
              table={table}
              columns={columns}
              rowViewerPanelOpen={rowViewerPanelOpen}
              getRowIndex={getPaginatedRowIndex}
              viewedRowIdx={viewedRowIdx}
              virtualize={virtualize}
            />
          </Table>
          <TableBottomBar
            part="table-footer"
            className="pt-1.5 pb-0.5 border-t border-border"
            totalColumns={totalColumns}
            pagination={pagination}
            selection={selection}
            onRowSelectionChange={onRowSelectionChange}
            table={table}
            getRowIds={getRowIds}
            showPageSizeSelector={showPageSizeSelector}
            tableLoading={reloading}
          />
        </div>
      </CellSelectionProvider>
    </div>
  );
};

export const DataTable = memo(DataTableInternal) as typeof DataTableInternal;
