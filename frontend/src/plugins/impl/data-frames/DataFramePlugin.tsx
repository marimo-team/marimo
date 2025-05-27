/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import {
  ConditionSchema,
  type ConditionType,
  type Transformations,
} from "./schema";
import { TransformPanel } from "./panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Code2Icon, DatabaseIcon, FunctionSquareIcon } from "lucide-react";
import type { ColumnDataTypes, ColumnId } from "./types";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import { useAsyncData } from "@/hooks/useAsyncData";
import { LoadingDataTableComponent, TableProviders } from "../DataTablePlugin";
import { Functions } from "@/utils/functions";
import { Arrays } from "@/utils/arrays";
import { memo, useEffect, useRef, useState } from "react";
import { ErrorBanner } from "../common/error-banner";
import type { DataType } from "../vega/vega-loader";
import type { FieldTypesWithExternalType } from "@/components/data-table/types";
import { Spinner } from "@/components/icons/spinner";
import { ReadonlyCode } from "@/components/editor/code/readonly-python-code";
import { isEqual } from "lodash-es";
import { DATA_TYPES } from "@/core/kernel/messages";

type CsvURL = string;
type TableData<T> = T[] | CsvURL;

/**
 * Arguments for a data table
 *
 * @param label - a label of the table
 * @param data - the data to display
 */
interface Data {
  label?: string | null;
  columns: ColumnDataTypes;
  pageSize: number;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  get_dataframe: (req: {}) => Promise<{
    url: string;
    total_rows: number;
    row_headers: string[];
    field_types: FieldTypesWithExternalType | null;
    python_code?: string | null;
    sql_code?: string | null;
  }>;
  get_column_values: (req: { column: string }) => Promise<{
    values: unknown[];
    too_many_values: boolean;
  }>;
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

// Value is selection, but it is not currently exposed to the user
type S = Transformations | undefined;

export const DataFramePlugin = createPlugin<S>("marimo-dataframe")
  .withData(
    z.object({
      label: z.string().nullish(),
      pageSize: z.number().default(5),
      columns: z
        .array(z.tuple([z.string().or(z.number()), z.string(), z.string()]))
        .transform((value) => {
          const map = new Map<ColumnId, string>();
          value.forEach(([key, dataType]) =>
            map.set(key as ColumnId, dataType as DataType),
          );
          return map;
        }),
    }),
  )
  .withFunctions<PluginFunctions>({
    // Get the data as a URL
    get_dataframe: rpc.input(z.object({})).output(
      z.object({
        url: z.string(),
        total_rows: z.number(),
        row_headers: z.array(z.string()),
        field_types: z.array(
          z.tuple([z.string(), z.tuple([z.enum(DATA_TYPES), z.string()])]),
        ),
        python_code: z.string().nullish(),
        sql_code: z.string().nullish(),
      }),
    ),
    get_column_values: rpc.input(z.object({ column: z.string() })).output(
      z.object({
        values: z.array(z.any()),
        too_many_values: z.boolean(),
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
  .renderer((props) => (
    <TableProviders>
      <DataFrameComponent
        {...props.data}
        {...props.functions}
        value={props.value}
        setValue={props.setValue}
        host={props.host}
      />
    </TableProviders>
  ));

interface DataTableProps extends Data, PluginFunctions {
  value: S;
  setValue: (value: S) => void;
  host: HTMLElement;
}

const EMPTY: Transformations = {
  transforms: [],
};

export const DataFrameComponent = memo(
  ({
    columns,
    pageSize,
    value,
    setValue,
    get_dataframe,
    get_column_values,
    search,
    host,
  }: DataTableProps): JSX.Element => {
    const { data, error, loading } = useAsyncData(
      () => get_dataframe({}),
      [value?.transforms],
    );

    const { url, total_rows, row_headers, field_types, python_code, sql_code } =
      data || {};

    const [internalValue, setInternalValue] = useState<Transformations>(
      value || EMPTY,
    );

    // If dataframe changes and value.transforms gets reset, then
    // apply existing transformations (displayed in panel) to new data
    const prevValueRef = useRef(internalValue);

    useEffect(() => {
      prevValueRef.current = internalValue;
    });

    useEffect(() => {
      const prevValue = prevValueRef.current;
      if (value?.transforms.length !== prevValue.transforms.length) {
        setValue(prevValue);
      }
    }, [data, value?.transforms.length, prevValueRef, setValue]);

    return (
      <div>
        <Tabs defaultValue="transform">
          <div className="flex items-center gap-2">
            <TabsList className="h-8">
              <TabsTrigger value="transform" className="text-xs py-1">
                <FunctionSquareIcon className="w-3 h-3 mr-2" />
                Transform
              </TabsTrigger>
              {python_code && (
                <TabsTrigger value="python-code" className="text-xs py-1">
                  <Code2Icon className="w-3 h-3 mr-2" />
                  Python Code
                </TabsTrigger>
              )}
              {sql_code && (
                <TabsTrigger value="sql-code" className="text-xs py-1">
                  <DatabaseIcon className="w-3 h-3 mr-2" />
                  SQL Code
                </TabsTrigger>
              )}
              <div className="flex-grow" />
            </TabsList>
            {loading && <Spinner size="small" />}
          </div>
          <TabsContent
            value="transform"
            className="mt-1 border rounded-t overflow-hidden"
          >
            <TransformPanel
              initialValue={internalValue}
              columns={columns}
              onChange={(newValue) => {
                // Ignore changes that are the same
                if (isEqual(newValue, value)) {
                  return;
                }
                // Update the value valid changes
                setValue(newValue);
                setInternalValue(newValue);
              }}
              onInvalidChange={setInternalValue}
              getColumnValues={get_column_values}
            />
          </TabsContent>
          {python_code && (
            <TabsContent
              value="python-code"
              className="mt-1 border rounded-t overflow-hidden"
            >
              <ReadonlyCode
                minHeight="215px"
                maxHeight="215px"
                code={python_code}
                language="python"
              />
            </TabsContent>
          )}
          {sql_code && (
            <TabsContent
              value="sql-code"
              className="mt-1 border rounded-t overflow-hidden"
            >
              <ReadonlyCode
                minHeight="215px"
                maxHeight="215px"
                code={sql_code}
                language="sql"
              />
            </TabsContent>
          )}
        </Tabs>
        {error && <ErrorBanner error={error} />}
        <LoadingDataTableComponent
          label={null}
          className="rounded-b border-x border-b"
          data={url || ""}
          hasStableRowId={false}
          totalRows={total_rows ?? 0}
          totalColumns={Object.keys(columns).length}
          maxColumns="all"
          pageSize={pageSize}
          pagination={true}
          fieldTypes={field_types}
          rowHeaders={row_headers || Arrays.EMPTY}
          showDownload={false}
          download_as={Functions.THROW}
          enableSearch={false}
          showFilters={false}
          search={search}
          showColumnSummaries={false}
          get_column_summaries={getColumnSummaries}
          value={Arrays.EMPTY}
          setValue={Functions.NOOP}
          selection={null}
          lazy={false}
          host={host}
        />
      </div>
    );
  },
);
DataFrameComponent.displayName = "DataFrameComponent";

function getColumnSummaries() {
  return Promise.resolve({ stats: {}, data: null });
}
