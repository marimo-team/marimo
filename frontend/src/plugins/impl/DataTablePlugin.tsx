/* Copyright 2024 Marimo. All rights reserved. */
import { memo, useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { DataTable } from "../../components/data-table/data-table";
import {
  generateColumns,
  generateIndexColumns,
} from "../../components/data-table/columns";
import { Labeled } from "./common/labeled";
import { useAsyncData } from "@/hooks/useAsyncData";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { rpc } from "../core/rpc";
import { createPlugin } from "../core/builder";
import { vegaLoadData } from "./vega/loader";
import { VegaType } from "./vega/vega-loader";
import { getVegaFieldTypes } from "./vega/utils";
import { Arrays } from "@/utils/arrays";
import { Banner } from "./common/error-banner";
import { prettyNumber } from "@/utils/numbers";
import { ColumnChartSpecModel } from "@/components/data-table/chart-spec-model";
import { ColumnChartContext } from "@/components/data-table/column-summary";
import { Logger } from "@/utils/Logger";
import { LoadingTable } from "@/components/data-table/loading-table";
import { DelayMount } from "@/components/utils/delay-mount";
import { ColumnHeaderSummary } from "@/components/data-table/types";
import { SortingState } from "@tanstack/react-table";

/**
 * Arguments for a data table
 *
 * @param label - a label of the table
 * @param data - the data to display, or a URL to load the data from
 */
interface Data<T> {
  label: string | null;
  data: T[] | string;
  hasMore: boolean;
  totalRows: number;
  pagination: boolean;
  pageSize: number;
  selection: "single" | "multi" | null;
  showDownload: boolean;
  showColumnSummary: boolean;
  rowHeaders: Array<[string, string[]]>;
  fieldTypes?: Record<string, VegaType> | null;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type Functions = {
  download_as: (req: { format: "csv" | "json" }) => Promise<string>;
  get_column_summaries: (opts: {}) => Promise<{
    summaries: ColumnHeaderSummary[];
  }>;
  sort_values: (req: {
    by: string | null;
    descending: boolean;
  }) => Promise<unknown[]>;
};

type S = Array<string | number>;

export const DataTablePlugin = createPlugin<S>("marimo-table")
  .withData(
    z.object({
      initialValue: z.array(z.number()),
      label: z.string().nullable(),
      data: z.union([z.string(), z.array(z.object({}).passthrough())]),
      hasMore: z.boolean().default(false),
      totalRows: z.number(),
      pagination: z.boolean().default(false),
      pageSize: z.number().default(10),
      selection: z.enum(["single", "multi"]).nullable().default(null),
      showDownload: z.boolean().default(false),
      showColumnSummary: z.boolean().default(true),
      rowHeaders: z.array(z.tuple([z.string(), z.array(z.any())])),
      fieldTypes: z
        .record(
          z.enum(["boolean", "integer", "number", "date", "string", "unknown"]),
        )
        .nullish(),
    }),
  )
  .withFunctions<Functions>({
    download_as: rpc
      .input(z.object({ format: z.enum(["csv", "json"]) }))
      .output(z.string()),
    get_column_summaries: rpc.input(z.object({}).passthrough()).output(
      z.object({
        summaries: z.array(
          z.object({
            column: z.union([z.number(), z.string()]),
            min: z.union([z.number(), z.string()]).nullish(),
            max: z.union([z.number(), z.string()]).nullish(),
            unique: z.number().nullish(),
            nulls: z.number().nullish(),
            true: z.number().nullish(),
            false: z.number().nullish(),
          }),
        ),
      }),
    ),
    sort_values: rpc
      .input(z.object({ by: z.string().nullable(), descending: z.boolean() }))
      .output(z.array(z.unknown())),
  })
  .renderer((props) => {
    if (typeof props.data.data === "string") {
      return (
        <LoadingDataTableComponent
          {...props.data}
          {...props.functions}
          data={props.data.data}
          value={props.value}
          setValue={props.setValue}
        />
      );
    }
    return (
      <DataTableComponent
        {...props.data}
        {...props.functions}
        data={props.data.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  });

interface DataTableProps extends Data<unknown>, Functions {
  className?: string;
  value: S;
  setValue: (value: S) => void;
}

export const LoadingDataTableComponent = memo(
  (props: DataTableProps & { data: string }) => {
    const { data, loading, error } = useAsyncData<unknown[]>(() => {
      if (!props.data || props.totalRows === 0) {
        return Promise.resolve([]);
      }
      return vegaLoadData(
        props.data,
        { type: "csv", parse: getVegaFieldTypes(props.fieldTypes) },
        { handleBigInt: true },
      );
    }, [props.data, props.fieldTypes, props.totalRows]);

    const { data: columnSummaries, error: columnSummariesError } =
      useAsyncData(() => {
        if (props.totalRows === 0) {
          return Promise.resolve({ summaries: [] });
        }
        return props.get_column_summaries({});
      }, [props.get_column_summaries, props.totalRows]);

    useEffect(() => {
      if (columnSummariesError) {
        Logger.error(columnSummariesError);
      }
    }, [columnSummariesError]);

    if (loading && !data) {
      return (
        <DelayMount milliseconds={200}>
          <LoadingTable pageSize={props.pageSize} />
        </DelayMount>
      );
    }

    if (error) {
      return (
        <Alert variant="destructive">
          <AlertTitle>Error</AlertTitle>
          <div className="text-md">
            {error.message || "An unknown error occurred"}
          </div>
        </Alert>
      );
    }

    return (
      <DataTableComponent
        {...props}
        data={data || Arrays.EMPTY}
        columnSummaries={columnSummaries?.summaries}
      />
    );
  },
);
LoadingDataTableComponent.displayName = "LoadingDataTableComponent";

const DataTableComponent = ({
  label,
  data,
  hasMore,
  totalRows,
  pagination,
  pageSize,
  selection,
  value,
  showDownload,
  rowHeaders,
  showColumnSummary,
  fieldTypes,
  download_as: downloadAs,
  sort_values: sortValues,
  columnSummaries,
  className,
  setValue,
}: DataTableProps & {
  data: unknown[];
  columnSummaries?: ColumnHeaderSummary[];
}): JSX.Element => {
  const resultsAreClipped = hasMore && totalRows > 0;

  const chartSpecModel = useMemo(() => {
    if (!fieldTypes || !data || !columnSummaries) {
      return ColumnChartSpecModel.EMPTY;
    }
    return new ColumnChartSpecModel(data, fieldTypes, columnSummaries, {
      includeCharts: !resultsAreClipped,
    });
  }, [data, fieldTypes, columnSummaries, resultsAreClipped]);

  const columns = useMemo(
    () => generateColumns(data, generateIndexColumns(rowHeaders), selection),
    [data, selection, rowHeaders],
  );

  const rowSelection = Object.fromEntries((value || []).map((v) => [v, true]));

  const [tableData, setTableData] = useState(data);
  const [sorting, setSorting] = useState<SortingState>([]);

  useEffect(() => {
    setSorting([]);
  }, [data]);

  useEffect(() => {
    if (sorting.length === 0) {
      setTableData(data);
      return;
    }

    const fetchSortedData = async () => {
      const sortKey = columns.length > 2 ? sorting[0].id : null;
      const sortedData = await sortValues({
        by: sortKey,
        descending: sorting[0].desc,
      });
      setTableData(sortedData);
    };

    fetchSortedData();
  }, [sorting, sortValues]);

  return (
    <>
      {hasMore && totalRows && (
        <Banner className="mb-2 rounded">
          Result clipped. Total rows {prettyNumber(totalRows)}.
        </Banner>
      )}
      <ColumnChartContext.Provider value={chartSpecModel}>
        <Labeled label={label} align="top" fullWidth={true}>
          <DataTable
            data={tableData}
            columns={columns}
            className={className}
            sorting={sorting}
            setSorting={setSorting}
            pagination={pagination}
            pageSize={pageSize}
            rowSelection={rowSelection}
            downloadAs={showDownload ? downloadAs : undefined}
            showColumnSummary={showColumnSummary}
            onRowSelectionChange={(updater) => {
              if (selection === "single") {
                const nextValue =
                  typeof updater === "function" ? updater({}) : updater;
                setValue(Object.keys(nextValue).slice(0, 1));
              }

              if (selection === "multi") {
                const nextValue =
                  typeof updater === "function"
                    ? updater(rowSelection)
                    : updater;
                setValue(Object.keys(nextValue));
              }
            }}
          />
        </Labeled>
      </ColumnChartContext.Provider>
    </>
  );
};
