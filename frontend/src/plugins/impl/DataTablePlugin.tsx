/* Copyright 2023 Marimo. All rights reserved. */
import { useMemo } from "react";
import { z } from "zod";
// @ts-expect-error - no types
import { loader as createLoader, read } from "vega-loader";

import { DataTable } from "../../components/data-table/data-table";
import { generateColumns } from "../../components/data-table/columns";
import { Labeled } from "./common/labeled";
import { useAsyncData } from "@/hooks/useAsyncData";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { rpc } from "../core/rpc";
import { createPlugin } from "../core/builder";

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
  selection: "single" | "multi" | null;
  showDownload: boolean;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type Functions = {
  download_as: (req: { format: "csv" | "json" }) => Promise<string>;
};

type S = Array<string | number>;

const loader = createLoader();

export const DataTablePlugin = createPlugin<S>("marimo-table")
  .withData(
    z.object({
      initialValue: z.array(z.number()),
      label: z.string().nullable(),
      data: z.union([z.string(), z.array(z.object({}).passthrough())]),
      pagination: z.boolean().default(false),
      selection: z.enum(["single", "multi"]).nullable().default(null),
      showDownload: z.boolean().default(false),
    })
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
  value: S;
  setValue: (value: S) => void;
}

const LoadingDataTableComponent = (
  props: DataTableProps & { data: string }
) => {
  const { data, loading, error } = useAsyncData<unknown[]>(() => {
    return loader.load(props.data).then((csvData: string) => {
      // csv -> json
      return read(csvData, { type: "csv", parse: "auto" });
    });
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
  selection,
  value,
  showDownload,
  download_as: downloadAs,
  setValue,
}: DataTableProps & {
  data: unknown[];
}): JSX.Element => {
  const columns = useMemo(
    () => generateColumns(data, selection),
    [data, selection]
  );

  const rowSelection = Object.fromEntries((value || []).map((v) => [v, true]));

  return (
    <Labeled label={label} align="top">
      <DataTable
        data={data}
        columns={columns}
        pagination={pagination}
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
