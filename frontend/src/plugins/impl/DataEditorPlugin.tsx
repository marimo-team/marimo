/* Copyright 2026 Marimo. All rights reserved. */

import glideCss from "@glideapps/glide-data-grid/dist/index.css?inline";
import glideCellsCss from "@glideapps/glide-data-grid-cells/dist/index.css?inline";
import React, { useEffect, useState } from "react";
import { z } from "zod";
import { inferFieldTypes } from "@/components/data-table/columns";
import { LoadingTable } from "@/components/data-table/loading-table";
import {
  type FieldTypesWithExternalType,
  toFieldTypes,
} from "@/components/data-table/types";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { DelayMount } from "@/components/utils/delay-mount";
import { useAsyncData } from "@/hooks/useAsyncData";
import { createPlugin } from "../core/builder";
import type { Setter } from "../types";
import { columnToFieldTypesSchema } from "./data-frames/schema";
import { normalizeConfiguredColumns } from "./data-editor/column-types";
import { orderColumnFields } from "./data-editor/data-utils";
import { applyEditorEdits } from "./data-editor/editor-state";
import type {
  ColumnType,
  EditorRow,
  EditorState,
  Edits,
} from "./data-editor/types";
import { vegaLoadData } from "./vega/loader";
import { getVegaFieldTypes } from "./vega/utils";

type CsvURL = string;
type TableData = EditorRow[] | CsvURL;

// Lazy load the data editor since it brings in glide-data-grid
const LazyDataEditor = React.lazy(
  () => import("./data-editor/glide-data-editor"),
);

export const DataEditorPlugin = createPlugin<Edits>("marimo-data-editor", {
  cssStyles: [glideCss, glideCellsCss],
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
      columnTypes: z
        .record(
          z.string(),
          z.union([z.literal("boolean"), z.array(z.string())]),
        )
        .default({}),
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
        editableColumns={props.data.editableColumns}
        columnTypes={props.data.columnTypes}
      />
    );
  });

interface Props {
  data: TableData;
  fieldTypes: FieldTypesWithExternalType | null | undefined;
  edits: Edits;
  onEdits: Setter<Edits>;
  editableColumns: string[] | "all";
  columnNames: string[];
  columnTypes: Record<string, ColumnType>;
}

const LoadingDataEditor = (props: Props) => {
  const [editorState, setEditorState] = useState<EditorState | null>(null);

  // Load the data
  const { data: loadedState, error } = useAsyncData(async () => {
    const withoutExternalTypes = toFieldTypes(props.fieldTypes ?? []);

    // If we already have the data, return it
    // Otherwise, load the data from the URL. Vega's CSV parser takes a
    // plain `Record`; column order doesn't matter for parsing.
    const localData = Array.isArray(props.data)
      ? props.data
      : await vegaLoadData<EditorRow>(
          props.data,
          {
            type: "csv",
            parse: getVegaFieldTypes(Object.fromEntries(withoutExternalTypes)),
          },
          { handleBigIntAndNumberLike: true },
        );

    const columnTypes = new Map(Object.entries(props.columnTypes));
    const inferredFields = toFieldTypes(
      props.fieldTypes ?? inferFieldTypes(localData),
    );
    for (const [columnName, columnType] of columnTypes) {
      if (columnType === "boolean") {
        inferredFields.set(columnName, "boolean");
      }
    }

    return {
      data: normalizeConfiguredColumns(localData, columnTypes),
      columnFields: orderColumnFields(inferredFields, props.columnNames),
      columnTypes,
    } satisfies EditorState;
  }, [props.fieldTypes, props.columnNames, props.columnTypes, props.data]);

  useEffect(() => {
    if (loadedState !== undefined) {
      setEditorState(applyEditorEdits(loadedState, props.edits.edits));
    }
  }, [loadedState, props.edits.edits]);

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

  if (editorState === null) {
    return (
      <DelayMount milliseconds={200}>
        <LoadingTable pageSize={10} />
      </DelayMount>
    );
  }

  return (
    <LazyDataEditor
      data={editorState.data}
      columnFields={editorState.columnFields}
      columnTypes={editorState.columnTypes}
      editableColumns={props.editableColumns}
      onAddEdits={(edits) => {
        setEditorState((state) =>
          state === null ? null : applyEditorEdits(state, edits),
        );
        props.onEdits((v) => ({ ...v, edits: [...v.edits, ...edits] }));
      }}
    />
  );
};
