/* Copyright 2024 Marimo. All rights reserved. */

import { TooltipProvider } from "@radix-ui/react-tooltip";
import agGridCss from "ag-grid-community/styles/ag-grid.css?inline";
import agThemeCss from "ag-grid-community/styles/ag-theme-quartz.css?inline";
import jspreadsheetCss from "jspreadsheet-ce/dist/jspreadsheet.css?inline";
import jssThemesCss from "jspreadsheet-ce/dist/jspreadsheet.themes.css?inline";
import React from "react";
import { z } from "zod";
import { LoadingTable } from "@/components/data-table/loading-table";
import { toFieldTypes } from "@/components/data-table/types";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { DelayMount } from "@/components/utils/delay-mount";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { DATA_TYPES } from "@/core/kernel/messages";
import { useAsyncData } from "@/hooks/useAsyncData";
import { createPlugin } from "../core/builder";
import type { Setter } from "../types";
import gridCss from "./data-editor/css/aggrid.css?inline";
import jssGridCss from "./data-editor/css/jssgrid.css?inline";
import jsuitesCss from "./data-editor/css/jsuites.css?inline";
import materialFontsCss from "./data-editor/css/material-fonts.css?inline";
import type { DataEditorProps } from "./data-editor/data-editor";
import type { Edits } from "./data-editor/types";
import { vegaLoadData } from "./vega/loader";
import { getVegaFieldTypes } from "./vega/utils";

interface EditsProp {
  edits: Edits;
}

type CsvURL = string;
type TableData<T> = T[] | CsvURL;

// Lazy load the data editors since they bring in 3rd party libraries
const AgGridDataEditor = React.lazy(() => import("./data-editor/data-editor"));
const SpreadsheetEditor = React.lazy(
  () => import("./data-editor/jspreadsheet-editor"),
);

export const DataEditorPlugin = createPlugin<EditsProp>("marimo-data-editor", {
  cssStyles: [
    gridCss,
    agGridCss,
    agThemeCss,
    jsuitesCss,
    jssGridCss,
    jspreadsheetCss,
    materialFontsCss,
    jssThemesCss,
  ],
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
          host={props.host}
        />
      </TooltipProvider>
    );
  });

interface Props
  extends Omit<DataEditorProps<object>, "data" | "onAddEdits" | "onAddRows"> {
  data: TableData<object>;
  edits: EditsProp["edits"];
  onEdits: Setter<EditsProp>;
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

  const spreadsheetEditor = getFeatureFlag("spreadsheet_editor");
  if (spreadsheetEditor) {
    return (
      <SpreadsheetEditor
        data={data}
        onAddEdits={(edits) => {
          props.onEdits((v) => ({ ...v, edits: [...v.edits, ...edits] }));
        }}
        fieldTypes={props.fieldTypes}
        host={props.host}
        pagination={props.pagination}
        pageSize={props.pageSize}
      />
    );
  }

  return (
    <AgGridDataEditor
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
