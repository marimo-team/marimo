/* Copyright 2026 Marimo. All rights reserved. */

import fortuneCss from "@fortune-sheet/react/dist/index.css?inline";
import React, { useState } from "react";
import { z } from "zod";
import { inferFieldTypes } from "@/components/data-table/columns";
import { LoadingTable } from "@/components/data-table/loading-table";
import { type FieldTypes, toFieldTypes } from "@/components/data-table/types";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { DelayMount } from "@/components/utils/delay-mount";
import { DATA_TYPES } from "@/core/kernel/messages";
import { useAsyncData } from "@/hooks/useAsyncData";
import { createPlugin } from "../core/builder";
import { rpc } from "../core/rpc";
import type { Setter } from "../types";
import { vegaLoadData } from "./vega/loader";
import { getVegaFieldTypes } from "./vega/utils";

type CsvURL = string;
type TableData<T> = T[] | CsvURL;

type FieldTypesProps = any;

export type PluginFunctions = {
  run_custom_function: (req: { name: string; args: any[] }) => Promise<any>;
};

const LazyWorkbook = React.lazy(() => import("./spreadsheet/workbook-wrapper"));

export const SpreadsheetPlugin = createPlugin<Record<string, any>[] | null>(
  "marimo-spreadsheet",
  {
    cssStyles: [fortuneCss],
  },
)
  .withData(
    z.object({
      label: z.string().nullable().optional(),
      data: z.union([z.string(), z.array(z.object({}).passthrough())]),
      fieldTypes: z
        .array(
          z.tuple([
            z.coerce.string(),
            z.tuple([z.enum(DATA_TYPES), z.string()]),
          ]),
        )
        .nullish(),
      customFunctions: z
        .array(z.string())
        .nullish()
        .transform((val) => val ?? []),
    }),
  )
  .withFunctions<PluginFunctions>({
    run_custom_function: rpc
      .input(z.object({ name: z.string(), args: z.array(z.any()) }))
      .output(z.any()),
  })
  .renderer((props) => {
    console.log("SpreadsheetPlugin received data:", props.data);
    return (
      <LoadingSpreadsheet
        data={props.data.data}
        fieldTypes={props.data.fieldTypes}
        customFunctions={props.data.customFunctions}
        run_custom_function={props.functions.run_custom_function}
        value={props.value}
        onChange={props.setValue}
      />
    );
  });

interface LoadingSpreadsheetProps {
  data: TableData<object>;
  fieldTypes: FieldTypesProps | null | undefined;
  customFunctions: string[];
  run_custom_function: PluginFunctions["run_custom_function"];
  value: Record<string, any>[] | null;
  onChange: Setter<Record<string, any>[] | null>;
}

const LoadingSpreadsheet = (props: LoadingSpreadsheetProps) => {
  const [data, setData] = useState<Record<string, any>[]>([]);
  const [columnFields, setColumnFields] = useState<FieldTypes>(new Map());
  const [isLoading, setIsLoading] = useState(true);

  const { error } = useAsyncData(async () => {
    setIsLoading(true);
    const withoutExternalTypes = toFieldTypes(props.fieldTypes ?? []);

    const localData = Array.isArray(props.data)
      ? (props.data as Record<string, any>[])
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
      toFieldTypes(props.fieldTypes ?? inferFieldTypes(localData)),
    );
    setIsLoading(false);
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

  if (isLoading) {
    return (
      <DelayMount milliseconds={200}>
        <LoadingTable pageSize={10} />
      </DelayMount>
    );
  }

  const initialData =
    props.value && props.value.length > 0 ? props.value : data;
  const columnNames = [...columnFields.keys()];

  return (
    <React.Suspense fallback={<LoadingTable pageSize={10} />}>
      <LazyWorkbook
        initialData={initialData}
        columnNames={columnNames}
        customFunctions={props.customFunctions}
        run_custom_function={props.run_custom_function}
        onChange={props.onChange}
      />
    </React.Suspense>
  );
};
