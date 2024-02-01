/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import { Transformations } from "./schema";
import { TransformPanel } from "./panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Code2Icon, FunctionSquareIcon } from "lucide-react";
import { CodePanel } from "./python/code-panel";
import { ColumnDataTypes } from "./types";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import { useAsyncData } from "@/hooks/useAsyncData";
import { LoadingDataTableComponent } from "../DataTablePlugin";
import { Functions } from "@/utils/functions";
import { Arrays } from "@/utils/arrays";
import { useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Banner, ErrorBanner } from "../common/error-banner";

/**
 * Arguments for a data table
 *
 * @param label - a label of the table
 * @param data - the data to display
 */
interface Data {
  label?: string | null;
  columns: ColumnDataTypes;
  dataframeName: string;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  get_dataframe: (req: {}) => Promise<{
    url: string;
    has_more: boolean;
    total_rows: number;
    row_headers: Array<[string, string[]]>;
  }>;
  get_column_values: (req: { column: string }) => Promise<{
    values: unknown[];
    too_many_values: boolean;
  }>;
};

// Value is selection, but it is not currently exposed to the user
type S = Transformations | undefined;

export const DataFramePlugin = createPlugin<S>("marimo-dataframe")
  .withData(
    z.object({
      label: z.string().nullish(),
      dataframeName: z.string(),
      columns: z
        .object({})
        .passthrough()
        .transform((value) => value as ColumnDataTypes),
    }),
  )
  .withFunctions<PluginFunctions>({
    // Get the data as a URL
    get_dataframe: rpc.input(z.object({})).output(
      z.object({
        url: z.string(),
        has_more: z.boolean(),
        total_rows: z.number(),
        row_headers: z.array(z.tuple([z.string(), z.array(z.any())])),
      }),
    ),
    get_column_values: rpc.input(z.object({ column: z.string() })).output(
      z.object({
        values: z.array(z.any()),
        too_many_values: z.boolean(),
      }),
    ),
  })
  .renderer((props) => (
    <TooltipProvider>
      <DataFrameComponent
        {...props.data}
        {...props.functions}
        value={props.value}
        setValue={props.setValue}
      />
    </TooltipProvider>
  ));

interface DataTableProps extends Data, PluginFunctions {
  value: S;
  setValue: (value: S) => void;
}

const EMPTY: Transformations = {
  transforms: [],
};

export const DataFrameComponent = ({
  columns,
  dataframeName,
  value,
  setValue,
  get_dataframe,
  get_column_values,
}: DataTableProps): JSX.Element => {
  const { data, error } = useAsyncData(
    () => get_dataframe({}),
    [value?.transforms],
  );
  const { url, has_more, total_rows, row_headers } = data || {};

  const [internalValue, setInternalValue] = useState<Transformations>(
    value || EMPTY,
  );

  return (
    <div>
      <Tabs defaultValue="transform">
        <TabsList className="h-8">
          <TabsTrigger value="transform" className="text-xs py-1">
            <FunctionSquareIcon className="w-3 h-3 mr-2" />
            Transform
          </TabsTrigger>
          <TabsTrigger value="code" className="text-xs py-1">
            <Code2Icon className="w-3 h-3 mr-2" />
            Code
          </TabsTrigger>
        </TabsList>
        <TabsContent
          value="transform"
          className="mt-1 border rounded-t overflow-hidden"
        >
          <TransformPanel
            initialValue={internalValue}
            columns={columns}
            onChange={(v) => {
              // Update the value valid changes
              setValue(v);
              setInternalValue(v);
            }}
            onInvalidChange={setInternalValue}
            getColumnValues={get_column_values}
          />
        </TabsContent>
        <TabsContent
          value="code"
          className="mt-1 border rounded-t overflow-hidden"
        >
          <CodePanel dataframeName={dataframeName} transforms={value} />
        </TabsContent>
      </Tabs>
      {error && <ErrorBanner error={error} />}
      {has_more && total_rows && (
        <Banner>Result clipped. Total rows {prettyNumber(total_rows)}.</Banner>
      )}
      <LoadingDataTableComponent
        label={null}
        className="rounded-b border-x border-b"
        data={url || ""}
        pageSize={5}
        pagination={true}
        rowHeaders={row_headers || Arrays.EMPTY}
        showDownload={false}
        download_as={Functions.THROW}
        value={Arrays.EMPTY}
        setValue={Functions.NOOP}
        selection={null}
      />
    </div>
  );
};

function prettyNumber(value: number): string {
  return new Intl.NumberFormat().format(value);
}
