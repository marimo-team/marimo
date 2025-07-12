/* Copyright 2024 Marimo. All rights reserved. */

import glideCss from "@glideapps/glide-data-grid/dist/index.css?inline";
import { TooltipProvider } from "@radix-ui/react-tooltip";
import React from "react";
import { z } from "zod";
import { LoadingTable } from "@/components/data-table/loading-table";
import { toFieldTypes } from "@/components/data-table/types";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { DelayMount } from "@/components/utils/delay-mount";
import { DATA_TYPES } from "@/core/kernel/messages";
import { useAsyncData } from "@/hooks/useAsyncData";
import { createPlugin } from "../core/builder";
import type { Setter } from "../types";
import {
  BulkEdit,
  type DataEditorProps,
  type Edits,
} from "./data-editor/types";
import { vegaLoadData } from "./vega/loader";
import { getVegaFieldTypes } from "./vega/utils";

type CsvURL = string;
type TableData<T> = T[] | CsvURL;

// Lazy load the data editor since it brings in glide-data-grid
const LazyDataEditor = React.lazy(
  () => import("./data-editor/glide-data-editor"),
);

export const DataEditorPlugin = createPlugin<Edits>("marimo-data-editor", {
  cssStyles: [glideCss],
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
      fieldTypes: z
        .array(
          z.tuple([
            z.coerce.string(),
            z.tuple([z.enum(DATA_TYPES), z.string()]),
          ]),
        )
        .nullish(),
      columnSizingMode: z.enum(["auto", "fit"]).default("auto"), // TODO: Remove this
    }),
  )
  .withFunctions({})
  .renderer((props) => {
    return (
      <TooltipProvider>
        <LoadingDataEditor
          data={props.data.data}
          fieldTypes={props.data.fieldTypes}
          edits={props.value}
          onEdits={props.setValue}
          columnSizingMode={props.data.columnSizingMode}
          host={props.host}
        />
      </TooltipProvider>
    );
  });

interface Props
  extends Omit<DataEditorProps<object>, "data" | "onAddEdits" | "onAddRows"> {
  data: TableData<object>;
  edits: Edits;
  onEdits: Setter<Edits>;
  host: HTMLElement;
}

const LoadingDataEditor = (props: Props) => {
  // Load the data
  const { data, error } = useAsyncData(async () => {
    // If we already have the data, return it
    if (Array.isArray(props.data)) {
      return props.data;
    }

    const withoutExternalTypes = toFieldTypes(props.fieldTypes ?? []);

    // Otherwise, load the data from the URL
    return await vegaLoadData(
      props.data,
      { type: "csv", parse: getVegaFieldTypes(withoutExternalTypes) },
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
      fieldTypes={props.fieldTypes}
      edits={props.edits.edits} // TODO: This is returning old edits upon refresh
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
      onDeleteRows={(rowIndexes) => {
        props.onEdits((v) => {
          const newEdits = rowIndexes.map((rowIdx, index) => ({
            rowIdx: rowIdx - index,
            type: BulkEdit.Remove,
          }));
          return {
            ...v,
            edits: [...v.edits, ...newEdits],
          };
        });
      }}
      onRenameColumn={(columnIdx: number, newName: string) => {
        props.onEdits((v) => ({
          ...v,
          edits: [...v.edits, { columnIdx, newName, type: BulkEdit.Rename }],
        }));
      }}
      onDeleteColumn={(columnIdx: number) => {
        props.onEdits((v) => ({
          ...v,
          edits: [...v.edits, { columnIdx, type: BulkEdit.Remove }],
        }));
      }}
      onAddColumn={(columnIdx: number, newName: string) => {
        props.onEdits((v) => ({
          ...v,
          edits: [...v.edits, { columnIdx, newName, type: BulkEdit.Insert }],
        }));
      }}
    />
  );
};
