/* Copyright 2026 Marimo. All rights reserved. */

import glideCss from "@glideapps/glide-data-grid/dist/index.css?inline";
import React, { useState } from "react";
import { z } from "zod";
import { inferFieldTypes } from "@/components/data-table/columns";
import { LoadingTable } from "@/components/data-table/loading-table";
import { type FieldTypes, toFieldTypes } from "@/components/data-table/types";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { DelayMount } from "@/components/utils/delay-mount";
import type { DataType } from "@/core/kernel/messages";
import { useAsyncData } from "@/hooks/useAsyncData";
import { createPlugin } from "../core/builder";
import type { Setter } from "../types";
import { columnToFieldTypesSchema } from "./data-frames/schema";
import {
  BulkEdit,
  type DataEditorProps,
  type Edits,
} from "./data-editor/types";
import { orderColumnFields } from "./data-editor/data-utils";
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
      fieldTypes: columnToFieldTypesSchema.nullish(),
      columnNames: z.array(z.string()).default([]),
      editableColumns: z.union([z.array(z.string()), z.literal("all")]),
      columnSizingMode: z.enum(["auto", "fit"]).default("auto"), // TODO: Remove this
    }),
  )
  .withFunctions({})
  .renderer((props) => {
    return (
      <LoadingDataEditor
        data={props.data.data}
        fieldTypes={props.data.fieldTypes}
        columnNames={props.data.columnNames}
        edits={props.value}
        onEdits={props.setValue}
        host={props.host}
        editableColumns={props.data.editableColumns}
      />
    );
  });

interface Props extends Omit<
  DataEditorProps<object>,
  "data" | "onAddEdits" | "onAddRows"
> {
  data: TableData<object>;
  edits: Edits;
  onEdits: Setter<Edits>;
  host: HTMLElement;
  editableColumns: string[] | "all";
  columnNames: string[];
}

const LoadingDataEditor = (props: Props) => {
  const [data, setData] = useState<unknown[] | null>(null);
  const [columnFields, setColumnFields] = useState<FieldTypes>(new Map());

  // Load the data
  const { error } = useAsyncData(async () => {
    const withoutExternalTypes = toFieldTypes(props.fieldTypes ?? []);

    // If we already have the data, return it
    // Otherwise, load the data from the URL. Vega's CSV parser takes a
    // plain `Record`; column order doesn't matter for parsing.
    const localData = Array.isArray(props.data)
      ? props.data
      : await vegaLoadData(
          props.data,
          {
            type: "csv",
            parse: getVegaFieldTypes(Object.fromEntries(withoutExternalTypes)),
          },
          { handleBigIntAndNumberLike: true },
        );

    setData(localData);
    setColumnFields(
      orderColumnFields(
        toFieldTypes(props.fieldTypes ?? inferFieldTypes(localData)),
        props.columnNames,
      ),
    );
  }, [props.fieldTypes, props.columnNames, props.data]);

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

  if (data === null) {
    return (
      <DelayMount milliseconds={200}>
        <LoadingTable pageSize={10} />
      </DelayMount>
    );
  }

  return (
    <LazyDataEditor
      data={data}
      setData={(nextData) => {
        if (typeof nextData === "function") {
          setData((previousData) => nextData(previousData ?? []));
        } else {
          setData(nextData);
        }
      }}
      columnFields={columnFields}
      setColumnFields={setColumnFields}
      editableColumns={props.editableColumns}
      edits={props.edits.edits}
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
      onAddColumn={(columnIdx: number, newName: string, dataType: DataType) => {
        props.onEdits((v) => ({
          ...v,
          edits: [
            ...v.edits,
            { columnIdx, newName, dataType, type: BulkEdit.Insert },
          ],
        }));
      }}
    />
  );
};
