/* Copyright 2023 Marimo. All rights reserved. */
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
import { prettyError } from "@/utils/errors";
import { useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

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
    row_headers: Array<[string, string[]]>;
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
    })
  )
  .withFunctions<PluginFunctions>({
    // Get the data as a URL
    get_dataframe: rpc.input(z.object({})).output(
      z.object({
        url: z.string(),
        row_headers: z.array(z.tuple([z.string(), z.array(z.any())])),
      })
    ),
  })
  .renderer((props) => (
    <DataFrameComponent
      {...props.data}
      {...props.functions}
      value={props.value}
      setValue={props.setValue}
    />
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
}: DataTableProps): JSX.Element => {
  const { data, error } = useAsyncData(
    () => get_dataframe({}),
    [value?.transforms]
  );
  const { url, row_headers } = data || {};

  const [internalValue, setInternalValue] = useState<Transformations>(
    value || EMPTY
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
        <TabsContent value="transform" className="mt-1">
          <TransformPanel
            initialValue={internalValue}
            columns={columns}
            onChange={(v) => {
              // Update the value valid changes
              setValue(v);
              setInternalValue(v);
            }}
            onInvalidChange={setInternalValue}
          />
        </TabsContent>
        <TabsContent value="code" className="mt-1">
          <CodePanel dataframeName={dataframeName} transforms={value} />
        </TabsContent>
      </Tabs>
      {error && <ErrorBanner error={error} />}
      <LoadingDataTableComponent
        label={null}
        className="rounded-b border"
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

const ErrorBanner = ({ error }: { error: Error }) => {
  const [open, setOpen] = useState(false);

  if (!error) {
    return null;
  }

  const message = prettyError(error);

  return (
    <>
      <div
        className="text-error border-[var(--red-6)] bg-[var(--red-2)] text-sm p-2 border cursor-pointer hover:bg-[var(--red-3)]"
        onClick={() => setOpen(true)}
      >
        <span className="line-clamp-4">{message}</span>
      </div>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent className="max-w-[80%]">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-error">Error</AlertDialogTitle>
          </AlertDialogHeader>
          <div className="text-error text-sm p-2 font-mono">{message}</div>
          <AlertDialogFooter>
            <AlertDialogAction autoFocus={true} onClick={() => setOpen(false)}>
              Ok
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
