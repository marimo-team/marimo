/* Copyright 2023 Marimo. All rights reserved. */
import { useMemo } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps } from "@/plugins/types";
import { DataTable } from "../../components/data-table/data-table";
import { generateColumns } from "../../components/data-table/columns";
import { Labeled } from "./common/labeled";

/**
 * Arguments for a data table
 *
 * @param label - a label of the table
 * @param data - the data to display
 */
interface Data<T> {
  label: string | null;
  data: T[];
  pagination: boolean;
  selection: "single" | "multi" | null;
}

// Value is selection, but it is not currently exposed to the user
type S = Array<string | number>;

export class DataTablePlugin implements IPlugin<S, Data<unknown>> {
  tagName = "marimo-table";

  validator = z.object({
    initialValue: z.array(z.number()),
    label: z.string().nullable(),
    data: z.array(z.object({}).passthrough()),
    pagination: z.boolean().default(false),
    selection: z.enum(["single", "multi"]).nullable().default(null),
  });

  render(props: IPluginProps<S, Data<unknown>>): JSX.Element {
    return (
      <DataTableComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface DataTableProps extends Data<unknown> {
  value: S;
  setValue: (value: S) => void;
}

const DataTableComponent = ({
  label,
  data,
  pagination,
  selection,
  value,
  setValue,
}: DataTableProps): JSX.Element => {
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
