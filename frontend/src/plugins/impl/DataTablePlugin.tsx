/* Copyright 2024 Marimo. All rights reserved. */
import { useMemo } from "react";
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

/**
 * Arguments for a data table
 *
 * @param label - a label of the table
 * @param data - the data to display, or a URL to load the data from
 */
interface Data<T> {
  label: string | null;
  data: T[] | string;
  pagination: boolean;
  pageSize: number;
  selection: "single" | "multi" | null;
  showDownload: boolean;
  rowHeaders: Array<[string, string[]]>;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type Functions = {
  download_as: (req: { format: "csv" | "json" }) => Promise<string>;
};

type S = Array<string | number>;

export const DataTablePlugin = createPlugin<S>("marimo-table")
  .withData(
    z.object({
      initialValue: z.array(z.number()),
      label: z.string().nullable(),
      data: z.union([z.string(), z.array(z.object({}).passthrough())]),
      pagination: z.boolean().default(false),
      pageSize: z.number().default(10),
      selection: z.enum(["single", "multi"]).nullable().default(null),
      showDownload: z.boolean().default(false),
      rowHeaders: z.array(z.tuple([z.string(), z.array(z.any())])),
    }),
  )
  .withFunctions<Functions>({
    download_as: rpc
      .input(z.object({ format: z.enum(["csv", "json"]) }))
      .output(z.string()),
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

export const LoadingDataTableComponent = (
  props: DataTableProps & { data: string },
) => {
  const { data, loading, error } = useAsyncData<unknown[]>(() => {
    if (!props.data) {
      return Promise.resolve([]);
    }
    return vegaLoadData(props.data, { type: "csv", parse: "auto" }, true);
  }, [props.data]);

  if (loading && !data) {
    return null;
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

  return <DataTableComponent {...props} data={data || []} />;
};

const DataTableComponent = ({
  label,
  data,
  pagination,
  pageSize,
  selection,
  value,
  showDownload,
  rowHeaders,
  download_as: downloadAs,
  className,
  setValue,
}: DataTableProps & {
  data: unknown[];
}): JSX.Element => {
  const columns = useMemo(
    () => generateColumns(data, generateIndexColumns(rowHeaders), selection),
    [data, selection, rowHeaders],
  );

  const rowSelection = Object.fromEntries((value || []).map((v) => [v, true]));

  return (
    <Labeled label={label} align="top" fullWidth={true}>
      <DataTable
        data={data}
        columns={columns}
        className={className}
        pagination={pagination}
        pageSize={pageSize}
        rowSelection={rowSelection}
        downloadAs={showDownload ? downloadAs : undefined}
        onRowSelectionChange={(updater) => {
          if (selection === "single") {
            const nextValue =
              typeof updater === "function" ? updater({}) : updater;
            setValue(Object.keys(nextValue).slice(0, 1));
          }

          if (selection === "multi") {
            const nextValue =
              typeof updater === "function" ? updater(rowSelection) : updater;
            setValue(Object.keys(nextValue));
          }
        }}
      />
    </Labeled>
  );
};
