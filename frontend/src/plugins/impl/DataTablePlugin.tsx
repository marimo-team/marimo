/* Copyright 2024 Marimo. All rights reserved. */
import { memo, useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { DataTable } from "../../components/data-table/data-table";
import {
  generateColumns,
  inferFieldTypes,
} from "../../components/data-table/columns";
import { Labeled } from "./common/labeled";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { rpc } from "../core/rpc";
import { createPlugin } from "../core/builder";
import { vegaLoadData } from "./vega/loader";
import { getVegaFieldTypes } from "./vega/utils";
import { Banner } from "./common/error-banner";
import { ColumnChartSpecModel } from "@/components/data-table/chart-spec-model";
import { ColumnChartContext } from "@/components/data-table/column-summary";
import { Logger } from "@/utils/Logger";

import {
  INDEX_COLUMN_NAME,
  type DataTableSelection,
  toFieldTypes,
  type ColumnHeaderSummary,
  type FieldTypesWithExternalType,
} from "@/components/data-table/types";
import type {
  ColumnFiltersState,
  OnChangeFn,
  PaginationState,
  RowSelectionState,
  SortingState,
} from "@tanstack/react-table";
import useEvent from "react-use-event-hook";
import { Functions } from "@/utils/functions";
import { ConditionSchema, type ConditionType } from "./data-frames/schema";
import {
  type ColumnFilterValue,
  filterToFilterCondition,
} from "@/components/data-table/filters";
import React from "react";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import { Arrays } from "@/utils/arrays";
import { LoadingTable } from "@/components/data-table/loading-table";
import { useAsyncData } from "@/hooks/useAsyncData";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { DelayMount } from "@/components/utils/delay-mount";
import { DATA_TYPES } from "@/core/kernel/messages";
import { useEffectSkipFirstRender } from "@/hooks/useEffectSkipFirstRender";
import type { CellSelectionState } from "@/components/data-table/cell-selection/types";

type CsvURL = string;
type TableData<T> = T[] | CsvURL;
interface ColumnSummaries<T = unknown> {
  data: TableData<T> | null | undefined;
  summaries: ColumnHeaderSummary[];
  is_disabled?: boolean;
}

/**
 * Arguments for a data table
 *
 * @param label - a label of the table
 * @param data - the data to display, or a URL to load the data from
 */
interface Data<T> {
  label: string | null;
  data: TableData<T>;
  totalRows: number | "too_many";
  pagination: boolean;
  pageSize: number;
  selection: DataTableSelection;
  showDownload: boolean;
  showFilters: boolean;
  showColumnSummaries: boolean | "stats" | "chart";
  rowHeaders: string[];
  fieldTypes?: FieldTypesWithExternalType | null;
  freezeColumnsLeft?: string[];
  freezeColumnsRight?: string[];
  textJustifyColumns?: Record<string, "left" | "center" | "right">;
  wrappedColumns?: string[];
  totalColumns: number;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type Functions = {
  download_as: (req: { format: "csv" | "json" }) => Promise<string>;
  get_column_summaries: <T>(opts: {}) => Promise<ColumnSummaries<T>>;
  search: <T>(req: {
    sort?: {
      by: string;
      descending: boolean;
    };
    query?: string;
    filters?: ConditionType[];
    page_number: number;
    page_size: number;
  }) => Promise<{
    data: TableData<T>;
    total_rows: number;
  }>;
};

// TODO: this was Array<number | string>
// I don't quite get this. Does it represent the row-id?
// Is the row-id the index property in our case?
type S = Array<{ rowId: string; columnName?: string }>;

export const DataTablePlugin = createPlugin<S>("marimo-table")
  .withData(
    z.object({
      initialValue: z.array(z.number()),
      label: z.string().nullable(),
      data: z.union([z.string(), z.array(z.object({}).passthrough())]),
      totalRows: z.union([z.number(), z.literal("too_many")]),
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
      rowHeaders: z.array(z.string()),
      freezeColumnsLeft: z.array(z.string()).optional(),
      freezeColumnsRight: z.array(z.string()).optional(),
      textJustifyColumns: z
        .record(z.enum(["left", "center", "right"]))
        .optional(),
      wrappedColumns: z.array(z.string()).optional(),
      fieldTypes: z
        .array(
          z.tuple([
            z.coerce.string(),
            z.tuple([z.enum(DATA_TYPES), z.string()]),
          ]),
        )
        .nullish(),
      totalColumns: z.number(),
    }),
  )
  .withFunctions<Functions>({
    download_as: rpc
      .input(z.object({ format: z.enum(["csv", "json"]) }))
      .output(z.string()),
    get_column_summaries: rpc.input(z.object({}).passthrough()).output(
      z.object({
        data: z
          .union([z.string(), z.array(z.object({}).passthrough())])
          .nullable(),
        summaries: z.array(
          z.object({
            column: z.union([z.number(), z.string()]),
            min: z.union([z.number(), z.string()]).nullish(),
            max: z.union([z.number(), z.string()]).nullish(),
            unique: z.union([z.number(), z.array(z.any())]).nullish(),
            nulls: z.number().nullish(),
            true: z.number().nullish(),
            false: z.number().nullish(),
          }),
        ),
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
        }),
      )
      .output(
        z.object({
          data: z.union([z.string(), z.array(z.object({}).passthrough())]),
          total_rows: z.number(),
        }),
      ),
  })
  .renderer((props) => {
    return (
      <TooltipProvider>
        <LoadingDataTableComponent
          {...props.data}
          {...props.functions}
          enableSearch={true}
          data={props.data.data}
          value={props.value}
          setValue={props.setValue}
        />
      </TooltipProvider>
    );
  });

interface DataTableProps<T> extends Data<T>, Functions {
  className?: string;
  // Selection
  value: S;
  setValue: (value: S) => void;
  // Search
  enableSearch: boolean;
  // Filters
  enableFilters?: boolean;
}

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
  setFilters?: OnChangeFn<ColumnFiltersState>;
}

export const LoadingDataTableComponent = memo(
  <T extends {}>(
    props: Omit<DataTableProps<T>, "sorting"> & { data: TableData<T> },
  ) => {
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

    // We need to clear the selection when sort, query, or filters change
    // if we don't have a stable ID for each row, which is determined by
    // _marimo_row_id.
    const hasStableRowId = props.fieldTypes?.some(
      (fieldType) => fieldType[0] === INDEX_COLUMN_NAME,
    );
    useEffectSkipFirstRender(() => {
      if (!hasStableRowId) {
        setValue([]);
      }
    }, [setValue, filters, searchQuery, sorting, hasStableRowId]);

    // If pageSize changes, reset pagination state
    useEffect(() => {
      if (paginationState.pageSize !== props.pageSize) {
        setPaginationState({
          pageIndex: 0,
          pageSize: props.pageSize,
        });
      }
    }, [props.pageSize, paginationState.pageSize]);

    // Data loading
    const { data, loading, error } = useAsyncData<{
      rows: T[];
      totalRows: number | "too_many";
    }>(async () => {
      // If there is no data, return an empty array
      if (props.totalRows === 0) {
        return { rows: Arrays.EMPTY, totalRows: 0 };
      }

      // Table data is a url string or an array of objects
      let tableData = props.data;
      let totalRows = props.totalRows;

      // If it is just the first page and no search query,
      // we can show the initial page.
      const canShowInitialPage =
        searchQuery === "" &&
        paginationState.pageIndex === 0 &&
        filters.length === 0 &&
        sorting.length === 0;

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
        void searchResultsPromise;
      } else {
        const searchResults = await searchResultsPromise;
        tableData = searchResults.data;
        totalRows = searchResults.total_rows;
      }

      // If we already have the data, return it
      if (Array.isArray(tableData)) {
        return {
          rows: tableData,
          totalRows: totalRows,
        };
      }

      const withoutExternalTypes = toFieldTypes(props.fieldTypes ?? []);

      // Otherwise, load the data from the URL
      tableData = await vegaLoadData(
        tableData,
        { type: "csv", parse: getVegaFieldTypes(withoutExternalTypes) },
        { handleBigIntAndNumberLike: true },
      );

      return {
        rows: tableData,
        totalRows: totalRows,
      };
    }, [
      sorting,
      search,
      filters,
      searchQuery,
      useDeepCompareMemoize(props.fieldTypes),
      props.data,
      paginationState.pageSize,
      paginationState.pageIndex,
    ]);

    // If total rows change, reset pageIndex
    useEffect(() => {
      setPaginationState((state) =>
        state.pageIndex === 0 ? state : { ...state, pageIndex: 0 },
      );
    }, [data?.totalRows]);

    // Column summaries
    const { data: columnSummaries, error: columnSummariesError } = useAsyncData<
      ColumnSummaries<T>
    >(() => {
      if (props.totalRows === 0 || !props.showColumnSummaries) {
        return Promise.resolve({ data: null, summaries: [] });
      }
      return props.get_column_summaries({});
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

    if (loading && !data) {
      return (
        <DelayMount milliseconds={200}>
          <LoadingTable
            pageSize={
              props.totalRows !== "too_many" && props.totalRows > 0
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
      errorComponent = (
        <Alert variant="destructive" className="mb-2">
          <AlertTitle>Error</AlertTitle>
          <div className="text-md">
            {error.message || "An unknown error occurred"}
          </div>
        </Alert>
      );
    }

    return (
      <>
        {errorComponent}
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
          reloading={loading}
          totalRows={data?.totalRows ?? props.totalRows}
          paginationState={paginationState}
          setPaginationState={setPaginationState}
        />
      </>
    );
  },
);
LoadingDataTableComponent.displayName = "LoadingDataTableComponent";

const DataTableComponent = ({
  label,
  data,
  totalRows,
  pagination,
  selection,
  value,
  showFilters,
  showDownload,
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
}: DataTableProps<unknown> &
  DataTableSearchProps & {
    data: unknown[];
    columnSummaries?: ColumnSummaries;
  }): JSX.Element => {
  const chartSpecModel = useMemo(() => {
    if (!columnSummaries) {
      return ColumnChartSpecModel.EMPTY;
    }
    if (!fieldTypes || !columnSummaries.summaries) {
      return ColumnChartSpecModel.EMPTY;
    }
    const fieldTypesWithoutExternalTypes = toFieldTypes(fieldTypes);
    return new ColumnChartSpecModel(
      columnSummaries.data || [],
      fieldTypesWithoutExternalTypes,
      columnSummaries.summaries,
      {
        includeCharts: Boolean(columnSummaries.data),
      },
    );
  }, [fieldTypes, columnSummaries]);

  const fieldTypesOrInferred = fieldTypes ?? inferFieldTypes(data);
  const shownColumns = fieldTypesOrInferred.length;

  const memoizedRowHeaders = useDeepCompareMemoize(rowHeaders);
  const memoizedFieldTypes = useDeepCompareMemoize(fieldTypesOrInferred);
  const memoizedTextJustifyColumns = useDeepCompareMemoize(textJustifyColumns);
  const memoizedWrappedColumns = useDeepCompareMemoize(wrappedColumns);
  const columns = useMemo(
    () =>
      generateColumns({
        rowHeaders: memoizedRowHeaders,
        selection: selection,
        fieldTypes: memoizedFieldTypes,
        textJustifyColumns: memoizedTextJustifyColumns,
        wrappedColumns: memoizedWrappedColumns,
        // Only show data types if they are explicitly set
        showDataTypes: Boolean(memoizedFieldTypes),
      }),
    [
      selection,
      memoizedRowHeaders,
      memoizedFieldTypes,
      memoizedTextJustifyColumns,
      memoizedWrappedColumns,
    ],
  );

  const rowSelection = useMemo(
    () => Object.fromEntries((value || []).map((v) => [v.rowId, true])),
    [value],
  );

  const handleRowSelectionChange: OnChangeFn<RowSelectionState> = useEvent(
    (updater) => {
      if (selection === "single") {
        const nextValue = Functions.asUpdater(updater)({});
        setValue(
          Object.keys(nextValue)
            .slice(0, 1)
            .map((r) => ({ rowId: r })),
        );
      }

      if (selection === "multi") {
        const nextValue = Functions.asUpdater(updater)(rowSelection);
        setValue(Object.keys(nextValue).map((r) => ({ rowId: r })));
      }
    },
  );

  const handleCellSelectionChange: OnChangeFn<CellSelectionState> = useEvent(
    (updater) => {
      if (selection === "single-cell") {
        const nextValue = Functions.asUpdater(updater)([]);
        // This maps to the _value in marimo/_plugins/ui/_impl/table.py I think
        setValue(nextValue.slice(0, 1));
      }
    },
  );

  return (
    <>
      {/* // HACK: We assume "too_many" is coming from a SQL table */}
      {totalRows === "too_many" && (
        <Banner className="mb-2 rounded">
          Result clipped. If no LIMIT is given, we only show the first 300 rows.
        </Banner>
      )}
      {shownColumns < totalColumns && (
        <Banner className="mb-2 rounded">
          Result clipped. Showing {shownColumns} of {totalColumns} columns.
        </Banner>
      )}
      {columnSummaries?.is_disabled && (
        // Note: Keep the text in sync with the constant defined in table_manager.py
        //       This hard-code can be removed when Functions can pass structural
        //       error information from the backend
        <Banner className="mb-2 rounded">
          Column summaries are unavailable. Filter your data to fewer than
          1,000,000 rows.
        </Banner>
      )}
      <ColumnChartContext.Provider value={chartSpecModel}>
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
          />
        </Labeled>
      </ColumnChartContext.Provider>
    </>
  );
};
