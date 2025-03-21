/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { createPlugin } from "../core/builder";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import type { DataEditorProps } from "./data-editor/data-editor";
import { useAsyncData } from "@/hooks/useAsyncData";
import { vegaLoadData } from "./vega/loader";
import type { Setter } from "../types";
import { LoadingTable } from "@/components/data-table/loading-table";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { DelayMount } from "@/components/utils/delay-mount";
import React from "react";
import gridCss from "./data-editor/grid.css?inline";
import agGridCss from "ag-grid-community/styles/ag-grid.css?inline";
import agThemeCss from "ag-grid-community/styles/ag-theme-quartz.css?inline";
import { DATA_TYPES } from "@/core/kernel/messages";

type CsvURL = string;
type TableData<T> = T[] | CsvURL;

interface Edits {
  edits: Array<{
    rowIdx: number;
    columnId: string;
    value: unknown;
  }>;
}

// Lazy load the data editor since it brings in ag-grid
const LazyDataEditor = React.lazy(() => import("./data-editor/data-editor"));

export const DataEditorPlugin = createPlugin<Edits>("marimo-data-editor", {
  cssStyles: [gridCss, agGridCss, agThemeCss],
})
  .withData(
    z.object({
      initialValue: z.object({
        edits: z.array(
          z.object({
            rowIdx: z.number(),
            columnId: z.string(),
            value: z.unknown(),
          }),
        ),
      }),
      label: z.string().nullable(),
      data: z.union([z.string(), z.array(z.object({}).passthrough())]),
      pagination: z.boolean().default(false),
      pageSize: z.number().default(10),
      fieldTypes: z
        .array(
          z.tuple([
            z.coerce.string(),
            z.tuple([z.enum(DATA_TYPES), z.string()]),
          ]),
        )
        .nullish(),
      columnSizingMode: z.enum(["auto", "fit"]).default("auto"),
    }),
  )
  .withFunctions({})
  .renderer((props) => {
    return (
      <TooltipProvider>
        <LoadingDataEditor
          data={props.data.data}
          pagination={props.data.pagination}
          pageSize={props.data.pageSize}
          fieldTypes={props.data.fieldTypes}
          edits={props.value.edits}
          onEdits={props.setValue}
          columnSizingMode={props.data.columnSizingMode}
        />
      </TooltipProvider>
    );
  });

interface Props
  extends Omit<DataEditorProps<object>, "data" | "onAddEdits" | "onAddRows"> {
  data: TableData<object>;
  edits: Edits["edits"];
  onEdits: Setter<Edits>;
}

const LoadingDataEditor = (props: Props) => {
  // Load the data
  const { data, error } = useAsyncData(async () => {
    // If we already have the data, return it
    if (Array.isArray(props.data)) {
      return props.data;
    }

    // Otherwise, load the data from the URL
    return await vegaLoadData(
      props.data,
      { type: "json" },
      { handleBigIntAndNumberLike: true },
    );
  }, [props.fieldTypes, props.data]);

  if (error) {
    return (
      <Alert variant="destructive" className="mb-2">
        <AlertTitle>Error</AlertTitle>
        <div className="text-md">
          {error.message || "An unknown error occurred"}
        </div>
      </Alert>
    );
  }

  if (!data) {
    return (
      <DelayMount milliseconds={200}>
        <LoadingTable pageSize={10} />
      </DelayMount>
    );
  }

  return (
    <LazyDataEditor
      data={data}
      pagination={props.pagination}
      pageSize={props.pageSize}
      fieldTypes={props.fieldTypes}
      edits={props.edits}
      onAddEdits={(edits) => {
        props.onEdits((v) => ({ ...v, edits: [...v.edits, ...edits] }));
      }}
      onAddRows={(rows) => {
        const newEdits = rows.flatMap((row, rowIndex) =>
          Object.entries(row).map(([columnId, value]) => ({
            rowIdx: data.length + rowIndex,
            columnId,
            value,
          })),
        );
        props.onEdits((v) => ({ ...v, edits: [...v.edits, ...newEdits] }));
      }}
      columnSizingMode={props.columnSizingMode}
    />
  );
};
