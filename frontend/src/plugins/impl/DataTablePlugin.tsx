/* Copyright 2024 Marimo. All rights reserved. */

import { Provider as SlotzProvider } from "@marimo-team/react-slotz";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import type {
  ColumnFiltersState,
  OnChangeFn,
  PaginationState,
  RowSelectionState,
  SortingState,
} from "@tanstack/react-table";
import { Provider } from "jotai";
import { Table2Icon } from "lucide-react";
import type { JSX } from "react";
import React, {
  memo,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useState,
} from "react";
import useEvent from "react-use-event-hook";
import { z } from "zod";
import type { CellSelectionState } from "@/components/data-table/cell-selection/types";
import type { CellStyleState } from "@/components/data-table/cell-styling/types";
import { ColumnChartSpecModel } from "@/components/data-table/chart-spec-model";
import { TablePanel } from "@/components/data-table/charts/charts";
import { hasChart } from "@/components/data-table/charts/storage";
import { ColumnExplorerPanel } from "@/components/data-table/column-explorer-panel/column-explorer";
import { ColumnChartContext } from "@/components/data-table/column-summary";
import {
  type ColumnFilterValue,
  filterToFilterCondition,
} from "@/components/data-table/filters";
import { usePanelOwnership } from "@/components/data-table/hooks/use-panel-ownership";
import { LoadingTable } from "@/components/data-table/loading-table";
import { RowViewerPanel } from "@/components/data-table/row-viewer-panel/row-viewer";
import {
  type BinValues,
  type ColumnHeaderStats,
  type ColumnName,
  type DataTableSelection,
  type FieldTypesWithExternalType,
  TOO_MANY_ROWS,
  type TooManyRows,
  toFieldTypes,
} from "@/components/data-table/types";
import { loadTableData } from "@/components/data-table/utils";
import { ContextAwarePanelItem } from "@/components/editor/chrome/panels/context-aware-panel/context-aware-panel";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DelayMount } from "@/components/utils/delay-mount";
import { type CellId, findCellId } from "@/core/cells/ids";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { slotsController } from "@/core/slots/slots";
import { store } from "@/core/state/jotai";
import { isStaticNotebook } from "@/core/static/static-state";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { useEffectSkipFirstRender } from "@/hooks/useEffectSkipFirstRender";
import { Arrays } from "@/utils/arrays";
import { Functions } from "@/utils/functions";
import { Logger } from "@/utils/Logger";
import {
  generateColumns,
  inferFieldTypes,
} from "../../components/data-table/columns";
import { DataTable } from "../../components/data-table/data-table";
import { createPlugin } from "../core/builder";
import { rpc } from "../core/rpc";
import { Banner } from "./common/error-banner";
import { Labeled } from "./common/labeled";
import {
  ConditionSchema,
  type ConditionType,
  columnToFieldTypesSchema,
} from "./data-frames/schema";

type CsvURL = string;
export type TableData<T> = T[] | CsvURL;

interface ColumnSummariesArgs {
  precompute: boolean;
}

interface ColumnSummaries<T = unknown> {
  data: TableData<T> | null | undefined;
  stats: Record<ColumnName, ColumnHeaderStats>;
  bin_values: Record<ColumnName, BinValues>;
  is_disabled?: boolean;
}

export type GetRowIds = (opts: {}) => Promise<{
  row_ids: number[];
  all_rows: boolean;
  error: string | null;
}>;

export type GetDataUrl = (opts: {}) => Promise<{
  data_url: string | object[];
  format: "csv" | "json" | "arrow";
}>;

export type CalculateTopKRows = (req: {
  column: string;
  k: number;
}) => Promise<{
  data: Array<[unknown, number]>;
}>;

export type PreviewColumn = (opts: { column: string }) => Promise<{
  chart_spec: string | null;
  chart_code: string | null;
  error: string | null;
  missing_packages: string[] | null;
  stats: ColumnHeaderStats | null;
}>;

export interface GetRowResult {
  rows: unknown[];
}

const maybeNumber = z.union([z.number(), z.nan(), z.string()]).nullable();
const columnStats = z.object({
  total: z.number().nullable(),
  nulls: z.number().nullable(),
  unique: z.number().nullable(),
  true: z.number().nullable(),
  false: z.number().nullable(),
  min: maybeNumber,
  max: maybeNumber,
  std: maybeNumber,
  mean: maybeNumber,
  median: maybeNumber,
  p5: maybeNumber,
  p25: maybeNumber,
  p75: maybeNumber,
  p95: maybeNumber,
});

const binValues = z.array(
  z.object({
    bin_start: z.number(),
    bin_end: z.number(),
    count: z.number(),
  }),
);

/**
 * Arguments for a data table
 *
 * @param label - a label of the table
 * @param data - the data to display, or a URL to load the data from
 */
interface Data<T> {
  label: string | null;
  data: TableData<T>;
  totalRows: number | TooManyRows;
  pagination: boolean;
  pageSize: number;
  selection: DataTableSelection;
  showDownload: boolean;
  showFilters: boolean;
  showColumnSummaries: boolean | "stats" | "chart";
  showPageSizeSelector: boolean;
  showColumnExplorer: boolean;
  showChartBuilder: boolean;
  rowHeaders: FieldTypesWithExternalType;
  fieldTypes?: FieldTypesWithExternalType | null;
  freezeColumnsLeft?: string[];
  freezeColumnsRight?: string[];
  textJustifyColumns?: Record<string, "left" | "center" | "right">;
  wrappedColumns?: string[];
  totalColumns: number;
  maxColumns: number | "all";
  hasStableRowId: boolean;
  lazy: boolean;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type DataTableFunctions = {
  download_as: (req: { format: "csv" | "json" | "parquet" }) => Promise<string>;
  get_column_summaries: <T>(
    opts: ColumnSummariesArgs,
  ) => Promise<ColumnSummaries<T>>;
  search: <T>(req: {
    sort?: {
      by: string;
      descending: boolean;
    };
    query?: string;
    filters?: ConditionType[];
    page_number: number;
    page_size: number;
    max_columns?: number | null;
  }) => Promise<{
    data: TableData<T>;
    total_rows: number | TooManyRows;
    cell_styles?: CellStyleState | null;
  }>;
  get_data_url?: GetDataUrl;
  get_row_ids?: GetRowIds;
  calculate_top_k_rows?: CalculateTopKRows;
  preview_column?: PreviewColumn;
};

type S = Array<number | string | { rowId: string; columnName?: string }>;

export const DataTablePlugin = createPlugin<S>("marimo-table")
  .withData(
    z.object({
      initialValue: z.union([
        z.array(z.number()),
        z.array(z.object({ rowId: z.string(), columnName: z.string() })),
      ]),
      label: z.string().nullable(),
      data: z.union([z.string(), z.array(z.object({}).passthrough())]),
      totalRows: z.union([z.number(), z.literal(TOO_MANY_ROWS)]),
      pagination: z.boolean().default(false),
      pageSize: z.number().default(10),
      selection: z
        .enum(["single", "multi", "single-cell", "multi-cell"])
        .nullable()
        .default(null),
      showDownload: z.boolean().default(false),
      showFilters: z.boolean().default(false),
      showColumnSummaries: z
        .union([z.boolean(), z.enum(["stats", "chart"])])
        .default(true),
      showPageSizeSelector: z.boolean().default(true),
      showColumnExplorer: z.boolean().default(true),
      showChartBuilder: z.boolean().default(true),
      rowHeaders: columnToFieldTypesSchema,
      freezeColumnsLeft: z.array(z.string()).optional(),
      freezeColumnsRight: z.array(z.string()).optional(),
      textJustifyColumns: z
        .record(z.enum(["left", "center", "right"]))
        .optional(),
      wrappedColumns: z.array(z.string()).optional(),
      fieldTypes: columnToFieldTypesSchema.nullish(),
      totalColumns: z.number(),
      maxColumns: z.union([z.number(), z.literal("all")]).default("all"),
      hasStableRowId: z.boolean().default(false),
      cellStyles: z.record(z.record(z.object({}).passthrough())).optional(),
      // Whether to load the data lazily.
      lazy: z.boolean().default(false),
      // If lazy, this will preload the first page of data
      // without user confirmation.
      preload: z.boolean().default(false),
    }),
  )
  .withFunctions<DataTableFunctions>({
    download_as: rpc
      .input(z.object({ format: z.enum(["csv", "json", "parquet"]) }))
      .output(z.string()),
    get_column_summaries: rpc
      .input(z.object({ precompute: z.boolean() }))
      .output(
        z.object({
          data: z
            .union([z.string(), z.array(z.object({}).passthrough())])
            .nullable(),
          stats: z.record(z.string(), columnStats),
          bin_values: z.record(z.string(), binValues),
          is_disabled: z.boolean().optional(),
        }),
      ),
    search: rpc
      .input(
        z.object({
          sort: z
            .object({ by: z.string(), descending: z.boolean() })
            .optional(),
          query: z.string().optional(),
          filters: z.array(ConditionSchema).optional(),
          page_number: z.number(),
          page_size: z.number(),
          max_columns: z.number().nullable().optional(),
        }),
      )
      .output(
        z.object({
          data: z.union([z.string(), z.array(z.object({}).passthrough())]),
          total_rows: z.union([z.number(), z.literal(TOO_MANY_ROWS)]),
          cell_styles: z
            .record(z.record(z.object({}).passthrough()))
            .nullable(),
        }),
      ),
    get_row_ids: rpc.input(z.object({}).passthrough()).output(
      z.object({
        row_ids: z.array(z.number()),
        all_rows: z.boolean(),
        error: z.string().nullable(),
      }),
    ),
    get_data_url: rpc.input(z.object({}).passthrough()).output(
      z.object({
        data_url: z.union([z.string(), z.array(z.object({}).passthrough())]),
        format: z.enum(["csv", "json", "arrow"]),
      }),
    ),
    calculate_top_k_rows: rpc
      .input(z.object({ column: z.string(), k: z.number() }))
      .output(
        z.object({
          data: z.array(z.tuple([z.any(), z.number()])),
        }),
      ),
    preview_column: rpc.input(z.object({ column: z.string() })).output(
      z.object({
        chart_spec: z.string().nullable(),
        chart_code: z.string().nullable(),
        error: z.string().nullable(),
        missing_packages: z.array(z.string()).nullable(),
        stats: columnStats.nullable(),
      }),
    ),
  })
  .renderer((props) => {
    return (
      <TableProviders>
        <LazyDataTableComponent
          isLazy={props.data.lazy}
          preload={props.data.preload}
        >
          <LoadingDataTableComponent
            {...props.data}
            {...props.functions}
            host={props.host}
            enableSearch={true}
            data={props.data.data}
            value={props.value}
            setValue={props.setValue}
          />
        </LazyDataTableComponent>
      </TableProviders>
    );
  });

const LazyDataTableComponent = ({
  isLazy: initialIsLazy,
  children,
  preload,
}: {
  isLazy: boolean;
  children: React.ReactNode;
  preload: boolean;
}) => {
  const [isLazy, setIsLazy] = useState(initialIsLazy && !preload);

  if (isLazy) {
    return (
      <div className="flex h-20 items-center justify-center">
        <Button variant="outline" size="xs" onClick={() => setIsLazy(false)}>
          <Table2Icon className="mr-2 h-4 w-4" />
          Preview data
        </Button>
      </div>
    );
  }
  return children;
};

interface DataTableProps<T> extends Data<T>, DataTableFunctions {
  className?: string;
  // Selection
  value: S;
  setValue: (value: S) => void;
  // Search
  enableSearch: boolean;
  // Filters
  enableFilters?: boolean;
  cellStyles?: CellStyleState | null;
  toggleDisplayHeader?: () => void;
  host: HTMLElement;
  cellId?: CellId | null;
}

export type SetFilters = OnChangeFn<ColumnFiltersState>;

interface DataTableSearchProps {
  // Pagination
  paginationState: PaginationState;
  setPaginationState: OnChangeFn<PaginationState>;
  // Sorting
  sorting: SortingState;
  setSorting: OnChangeFn<SortingState>;
  // Searching
  searchQuery: string | undefined;
  setSearchQuery: ((query: string) => void) | undefined;
  reloading: boolean;
  // Filters
  filters?: ColumnFiltersState;
  setFilters?: SetFilters;
  hasStableRowId: boolean;
}

export const LoadingDataTableComponent = memo(
  <T extends {}>(
    props: Omit<DataTableProps<T>, "sorting"> & { data: TableData<T> },
  ) => {
    const cellId = findCellId(props.host);

    const search = props.search;
    const setValue = props.setValue;
    // Sorting/searching state
    const [sorting, setSorting] = useState<SortingState>([]);
    const [paginationState, setPaginationState] =
      React.useState<PaginationState>({
        pageSize: props.pageSize,
        pageIndex: 0,
      });
    const [searchQuery, setSearchQuery] = useState<string>("");
    const [filters, setFilters] = useState<ColumnFiltersState>([]);
    const [displayHeader, setDisplayHeader] = useState(() => {
      // Show the header if a single chart is configured
      if (!props.showChartBuilder || !cellId) {
        return false;
      }
      return hasChart(cellId);
    });

    // We need to clear the selection when sort, query, or filters change
    // if we don't have a stable ID for each row, which is determined by
    // _marimo_row_id.
    useEffectSkipFirstRender(() => {
      if (!props.hasStableRowId) {
        setValue([]);
      }
    }, [setValue, filters, searchQuery, sorting, props.hasStableRowId]);

    // If pageSize changes, reset pagination state
    useEffect(() => {
      setPaginationState({ pageIndex: 0, pageSize: props.pageSize });
    }, [props.pageSize]);

    // Data loading
    const { data, error, isPending, isFetching } = useAsyncData<{
      rows: T[];
      totalRows: number | TooManyRows;
      cellStyles: CellStyleState | undefined | null;
    }>(async () => {
      // If there is no data, return an empty array
      if (props.totalRows === 0) {
        return { rows: Arrays.EMPTY, totalRows: 0, cellStyles: {} };
      }

      // Table data is a url string or an array of objects
      let tableData = props.data;
      let totalRows = props.totalRows;
      let cellStyles = props.cellStyles;

      const pageSizeChanged = paginationState.pageSize !== props.pageSize;

      // If it is just the first page and no search query,
      // we can show the initial page.
      const canShowInitialPage =
        searchQuery === "" &&
        paginationState.pageIndex === 0 &&
        filters.length === 0 &&
        sorting.length === 0 &&
        !props.lazy &&
        !pageSizeChanged;

      if (sorting.length > 1) {
        Logger.warn("Multiple sort columns are not supported");
      }

      // If we have sort/search/filter, use the search function
      const searchResultsPromise = search<T>({
        sort:
          sorting.length > 0
            ? {
                by: sorting[0].id,
                descending: sorting[0].desc,
              }
            : undefined,
        query: searchQuery,
        page_number: paginationState.pageIndex,
        page_size: paginationState.pageSize,
        filters: filters.flatMap((filter) => {
          return filterToFilterCondition(
            filter.id,
            filter.value as ColumnFilterValue,
          );
        }),
      });

      if (canShowInitialPage) {
        // We still want to run the search,
        // so the backend knows the current state for selection
        // see https://github.com/marimo-team/marimo/issues/2756
        // But we should catch errors; this may happen for static exports.
        void searchResultsPromise.catch((error) => {
          Logger.error(error);
        });
      } else {
        const searchResults = await searchResultsPromise;
        tableData = searchResults.data;
        totalRows = searchResults.total_rows;
        cellStyles = searchResults.cell_styles || {};
      }
      tableData = await loadTableData(tableData);
      return {
        rows: tableData,
        totalRows: totalRows,
        cellStyles,
      };
    }, [
      sorting,
      search,
      filters,
      searchQuery,
      useDeepCompareMemoize(props.fieldTypes),
      props.data,
      props.totalRows,
      props.lazy,
      paginationState.pageSize,
      paginationState.pageIndex,
    ]);

    const getRow = useCallback(
      async (rowId: number) => {
        const result = await search<T>({
          page_number: rowId,
          page_size: 1,
          sort:
            sorting.length > 0
              ? {
                  by: sorting[0].id,
                  descending: sorting[0].desc,
                }
              : undefined,
          query: searchQuery,
          filters: filters.flatMap((filter) => {
            return filterToFilterCondition(
              filter.id,
              filter.value as ColumnFilterValue,
            );
          }),
          // Do not clamp number of columns since we are viewing a single row
          max_columns: null,
        });
        const loadedData = await loadTableData(result.data);
        return {
          rows: loadedData,
        };
      },
      [search, sorting, filters, searchQuery],
    );

    // If total rows change, reset pageIndex
    useEffect(() => {
      setPaginationState((state) =>
        state.pageIndex === 0 ? state : { ...state, pageIndex: 0 },
      );
    }, [data?.totalRows]);

    const precompute = getFeatureFlag("performant_table_charts");

    // Column summaries
    const { data: columnSummaries, error: columnSummariesError } = useAsyncData<
      ColumnSummaries<T>
    >(async () => {
      if (props.totalRows === 0 || !props.showColumnSummaries) {
        return { data: null, stats: {}, bin_values: {} };
      }
      return props.get_column_summaries({ precompute });
    }, [
      props.get_column_summaries,
      props.showColumnSummaries,
      filters,
      searchQuery,
      props.totalRows,
      props.data,
    ]);

    useEffect(() => {
      if (columnSummariesError) {
        Logger.error(columnSummariesError);
      }
    }, [columnSummariesError]);

    if (isPending) {
      return (
        <DelayMount milliseconds={200}>
          <LoadingTable
            pageSize={
              props.totalRows !== TOO_MANY_ROWS && props.totalRows > 0
                ? props.totalRows
                : props.pageSize
            }
          />
        </DelayMount>
      );
    }

    let errorComponent: React.ReactNode = null;
    if (error) {
      Logger.error(error);
      errorComponent = !isStaticNotebook() && (
        <Alert variant="destructive" className="mb-2">
          <AlertTitle>Error</AlertTitle>
          <div className="text-md">
            {error.message || "An unknown error occurred"}
          </div>
        </Alert>
      );
    }

    const toggleDisplayHeader = () => {
      setDisplayHeader(!displayHeader);
    };

    const dataTable = (
      <DataTableComponent
        {...props}
        data={data?.rows ?? Arrays.EMPTY}
        columnSummaries={columnSummaries}
        sorting={sorting}
        setSorting={setSorting}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        filters={filters}
        setFilters={setFilters}
        reloading={isFetching && !isPending}
        totalRows={data?.totalRows ?? props.totalRows}
        paginationState={paginationState}
        setPaginationState={setPaginationState}
        cellStyles={data?.cellStyles ?? props.cellStyles}
        toggleDisplayHeader={toggleDisplayHeader}
        getRow={getRow}
        cellId={cellId}
      />
    );

    return (
      <>
        {errorComponent}
        {props.showChartBuilder ? (
          <TablePanel
            displayHeader={displayHeader}
            dataTable={dataTable}
            getDataUrl={props.get_data_url}
            fieldTypes={props.fieldTypes}
            cellId={cellId}
          />
        ) : (
          dataTable
        )}
      </>
    );
  },
);
LoadingDataTableComponent.displayName = "LoadingDataTableComponent";

const DataTableComponent = ({
  label,
  data,
  totalRows,
  maxColumns,
  pagination,
  selection,
  value,
  showFilters,
  showDownload,
  showPageSizeSelector,
  showColumnExplorer,
  showChartBuilder,
  rowHeaders,
  fieldTypes,
  paginationState,
  setPaginationState,
  download_as: downloadAs,
  columnSummaries,
  className,
  setValue,
  sorting,
  setSorting,
  enableSearch,
  searchQuery,
  setSearchQuery,
  filters,
  setFilters,
  reloading,
  freezeColumnsLeft,
  freezeColumnsRight,
  textJustifyColumns,
  wrappedColumns,
  totalColumns,
  get_row_ids,
  cellStyles,
  toggleDisplayHeader,
  calculate_top_k_rows,
  preview_column,
  getRow,
  cellId,
}: DataTableProps<unknown> &
  DataTableSearchProps & {
    data: unknown[];
    columnSummaries?: ColumnSummaries;
    getRow: (rowIdx: number) => Promise<GetRowResult>;
  }): JSX.Element => {
  const id = useId();
  const [viewedRowIdx, setViewedRowIdx] = useState(0);
  const { isPanelOpen, togglePanel } = usePanelOwnership(id, cellId);

  const chartSpecModel = useMemo(() => {
    if (!columnSummaries) {
      return ColumnChartSpecModel.EMPTY;
    }
    if (!fieldTypes || !columnSummaries.stats) {
      return ColumnChartSpecModel.EMPTY;
    }
    const fieldTypesWithoutExternalTypes = toFieldTypes(fieldTypes);
    return new ColumnChartSpecModel(
      columnSummaries.data || [],
      fieldTypesWithoutExternalTypes,
      columnSummaries.stats,
      columnSummaries.bin_values,
      {
        includeCharts: Boolean(columnSummaries.data),
        usePreComputedValues: getFeatureFlag("performant_table_charts"),
      },
    );
  }, [fieldTypes, columnSummaries]);

  const fieldTypesOrInferred = fieldTypes ?? inferFieldTypes(data);

  const memoizedUnclampedFieldTypes =
    useDeepCompareMemoize(fieldTypesOrInferred);

  const memoizedClampedFieldTypes = useMemo(() => {
    if (maxColumns === "all") {
      return memoizedUnclampedFieldTypes;
    }
    return memoizedUnclampedFieldTypes.slice(0, maxColumns);
  }, [maxColumns, memoizedUnclampedFieldTypes]);

  const memoizedRowHeaders = useDeepCompareMemoize(rowHeaders);
  const memoizedTextJustifyColumns = useDeepCompareMemoize(textJustifyColumns);
  const memoizedWrappedColumns = useDeepCompareMemoize(wrappedColumns);
  const memoizedChartSpecModel = useDeepCompareMemoize(chartSpecModel);
  const showDataTypes = Boolean(fieldTypes);
  const shownColumns = memoizedClampedFieldTypes.length;

  const columns = useMemo(
    () =>
      generateColumns({
        rowHeaders: memoizedRowHeaders,
        selection: selection,
        chartSpecModel: memoizedChartSpecModel,
        fieldTypes: memoizedClampedFieldTypes,
        textJustifyColumns: memoizedTextJustifyColumns,
        wrappedColumns: memoizedWrappedColumns,
        // Only show data types if they are explicitly set
        showDataTypes: showDataTypes,
        calculateTopKRows: calculate_top_k_rows,
      }),
    [
      selection,
      showDataTypes,
      memoizedChartSpecModel,
      memoizedRowHeaders,
      memoizedClampedFieldTypes,
      memoizedTextJustifyColumns,
      memoizedWrappedColumns,
      calculate_top_k_rows,
    ],
  );

  const rowSelection = useMemo(
    () => Object.fromEntries((value || []).map((v) => [v, true])),
    [value],
  );

  const handleRowSelectionChange: OnChangeFn<RowSelectionState> = useEvent(
    (updater) => {
      if (selection === "single") {
        const nextValue = Functions.asUpdater(updater)({});
        setValue(Object.keys(nextValue).slice(0, 1));
      }

      if (selection === "multi") {
        const nextValue = Functions.asUpdater(updater)(rowSelection);
        setValue(Object.keys(nextValue));
      }
    },
  );

  const cellSelection = value.filter(
    (v) => v instanceof Object && v.columnName !== undefined,
  ) as CellSelectionState;

  const handleCellSelectionChange: OnChangeFn<CellSelectionState> = useEvent(
    (updater) => {
      if (selection === "single-cell") {
        const nextValue = Functions.asUpdater(updater)(cellSelection);
        // This maps to the _value in marimo/_plugins/ui/_impl/table.py I think
        setValue(nextValue.slice(0, 1));
      }

      if (selection === "multi-cell") {
        const nextValue = Functions.asUpdater(updater)(cellSelection);
        setValue(nextValue);
      }
    },
  );

  const isSelectable = selection === "multi" || selection === "single";
  const showColExplorer =
    showColumnExplorer && preview_column && isPanelOpen("column-explorer");

  return (
    <>
      {/* When the totalRows is "too_many" and the pageSize is the same as the
       * number of rows, we are likely displaying all the data (could be more, but we don't know the total). */}
      {totalRows === TOO_MANY_ROWS &&
        paginationState.pageSize === data.length && (
          <Banner className="mb-1 rounded">
            Previewing the first {paginationState.pageSize} rows.
          </Banner>
        )}
      {shownColumns < totalColumns && shownColumns > 0 && (
        <Banner className="mb-1 rounded">
          Result clipped. Showing {shownColumns} of {totalColumns} columns.
        </Banner>
      )}
      {columnSummaries?.is_disabled && (
        // Note: Keep the text in sync with the constant defined in table_manager.py
        //       This hard-code can be removed when Functions can pass structural
        //       error information from the backend
        <Banner className="mb-1 rounded">
          Column summaries are unavailable. Filter your data to fewer than
          1,000,000 rows.
        </Banner>
      )}

      {isPanelOpen("row-viewer") && (
        <ContextAwarePanelItem>
          <RowViewerPanel
            getRow={getRow}
            fieldTypes={memoizedUnclampedFieldTypes}
            totalRows={totalRows}
            rowIdx={viewedRowIdx}
            setRowIdx={setViewedRowIdx}
            isSelectable={isSelectable}
            isRowSelected={rowSelection[viewedRowIdx]}
            handleRowSelectionChange={handleRowSelectionChange}
          />
        </ContextAwarePanelItem>
      )}
      {showColExplorer && (
        <ContextAwarePanelItem>
          <ColumnExplorerPanel
            previewColumn={preview_column}
            fieldTypes={memoizedUnclampedFieldTypes}
            totalRows={totalRows}
            totalColumns={totalColumns}
            tableId={id}
          />
        </ContextAwarePanelItem>
      )}

      <ColumnChartContext value={chartSpecModel}>
        <Labeled label={label} align="top" fullWidth={true}>
          <DataTable
            data={data}
            columns={columns}
            className={className}
            sorting={sorting}
            totalRows={totalRows}
            totalColumns={totalColumns}
            manualSorting={true}
            setSorting={setSorting}
            pagination={pagination}
            manualPagination={true}
            selection={selection}
            paginationState={paginationState}
            setPaginationState={setPaginationState}
            rowSelection={rowSelection}
            cellSelection={cellSelection}
            cellStyling={cellStyles}
            downloadAs={showDownload ? downloadAs : undefined}
            enableSearch={enableSearch}
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
            showFilters={showFilters}
            filters={filters}
            onFiltersChange={setFilters}
            reloading={reloading}
            onRowSelectionChange={handleRowSelectionChange}
            freezeColumnsLeft={freezeColumnsLeft}
            freezeColumnsRight={freezeColumnsRight}
            onCellSelectionChange={handleCellSelectionChange}
            getRowIds={get_row_ids}
            toggleDisplayHeader={toggleDisplayHeader}
            showChartBuilder={showChartBuilder}
            showPageSizeSelector={showPageSizeSelector}
            showColumnExplorer={showColumnExplorer}
            togglePanel={togglePanel}
            isPanelOpen={isPanelOpen}
            viewedRowIdx={viewedRowIdx}
            onViewedRowChange={(rowIdx) => setViewedRowIdx(rowIdx)}
          />
        </Labeled>
      </ColumnChartContext>
    </>
  );
};

/**
 * Common providers for data tables
 */
export const TableProviders: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  return (
    <Provider store={store}>
      <SlotzProvider controller={slotsController}>
        <TooltipProvider>{children}</TooltipProvider>
      </SlotzProvider>
    </Provider>
  );
};
