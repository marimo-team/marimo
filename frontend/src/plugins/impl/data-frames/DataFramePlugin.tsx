/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";

import { IPlugin, IPluginProps } from "@/plugins/types";
import { Transformations } from "./schema";
import { TransformPanel } from "./panel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Code2Icon, FunctionSquareIcon } from "lucide-react";
import { CodePanel } from "./python/code-panel";
import { ColumnDataTypes } from "./types";

/**
 * Arguments for a data table
 *
 * @param label - a label of the table
 * @param data - the data to display
 */
interface Data {
  label?: string | null;
  columns: ColumnDataTypes;
  name: string;
}

// Value is selection, but it is not currently exposed to the user
type S = Transformations | undefined;

export class DataFramePlugin implements IPlugin<S, Data> {
  tagName = "marimo-dataframe";

  validator = z.object({
    label: z.string().nullish(),
    name: z.string(),
    columns: z
      .object({})
      .passthrough()
      .transform((value) => value as ColumnDataTypes),
  });

  render(props: IPluginProps<S, Data>): JSX.Element {
    return (
      <DataFrameComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface DataTableProps extends Data {
  value: S;
  setValue: (value: S) => void;
}

const DataFrameComponent = ({
  columns,
  name,
  value,
  setValue,
}: DataTableProps): JSX.Element => {
  return (
    <div>
      {/* <div className="flex flex-row border-b border-gray-200 mb-2">
        {Object.entries(metadata).map(([key, value]) => {
          return (
            <div className="flex flex-row" key={key}>
              <div className="flex flex-col">
                <Label>{key}</Label>
                {typeof value === "string" ? (
                  <Label>{value}</Label>
                ) : (
                  Array.isArray(value) && <Label>{value.join(", ")}</Label>
                )}
              </div>
            </div>
          );
        })}
      </div> */}
      <Tabs defaultValue="transform">
        <TabsList>
          <TabsTrigger value="transform">
            <FunctionSquareIcon className="w-3 h-3 mr-2" />
            Transform
          </TabsTrigger>
          {/* <TabsTrigger value="preview">
            <DatabaseIcon className="w-3 h-3 mr-2" />
            Preview
          </TabsTrigger> */}
          <TabsTrigger value="code">
            <Code2Icon className="w-3 h-3 mr-2" />
            Code
          </TabsTrigger>
        </TabsList>
        <TabsContent value="transform">
          <TransformPanel
            initialValue={{
              transforms: value?.transforms ?? [],
            }}
            columns={columns}
            onChange={setValue}
          />
        </TabsContent>
        <TabsContent value="preview">
          {/* <DataTablePanel data={[]} /> */}
        </TabsContent>
        <TabsContent value="code">
          <CodePanel dataframeName={name} transforms={value} />
        </TabsContent>
      </Tabs>
    </div>
  );
};
