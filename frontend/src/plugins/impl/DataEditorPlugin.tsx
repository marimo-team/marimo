/* Copyright 2026 Marimo. All rights reserved. */

import glideCss from "@glideapps/glide-data-grid/dist/index.css?inline";
import glideCellsCss from "@glideapps/glide-data-grid-cells/dist/index.css?inline";
import React, { useMemo } from "react";
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
      data: z.union([z.string(), z.array(z.looseObject({}))]),
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
  const source = useMemo(
    () => ({
      data: props.data,
      fieldTypes: props.fieldTypes,
      columnNames: props.columnNames,
      columnTypes: props.columnTypes,
    }),
    [props.data, props.fieldTypes, props.columnNames, props.columnTypes],
  );

  const { data: loadedState, error } = useAsyncData(async () => {
    const withoutExternalTypes = toFieldTypes(source.fieldTypes ?? []);

    const localData = Array.isArray(source.data)
      ? source.data
      : await vegaLoadData<EditorRow>(
          source.data,
          {
            type: "csv",
            parse: getVegaFieldTypes(Object.fromEntries(withoutExternalTypes)),
          },
          { handleBigIntAndNumberLike: true },
        );

    const columnTypes = new Map(Object.entries(source.columnTypes));
    const inferredFields = toFieldTypes(
      source.fieldTypes ?? inferFieldTypes(localData),
    );
    for (const [columnName, columnType] of columnTypes) {
      inferredFields.set(
        columnName,
        columnType === "boolean" ? "boolean" : "string",
      );
    }

    return {
      source,
      state: {
        data: normalizeConfiguredColumns(localData, columnTypes),
        columnFields: orderColumnFields(inferredFields, source.columnNames),
        columnTypes,
      } satisfies EditorState,
    };
  }, [source]);

  // useAsyncData retains previous data while a replacement source loads.
  const editorState = useMemo(
    () =>
      loadedState?.source === source
        ? applyEditorEdits(loadedState.state, props.edits.edits)
        : null,
    [loadedState, source, props.edits.edits],
  );

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
        props.onEdits((v) => ({ ...v, edits: [...v.edits, ...edits] }));
      }}
    />
  );
};
