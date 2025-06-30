/* Copyright 2024 Marimo. All rights reserved. */

import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { DataFrameComponent } from "@/plugins/impl/data-frames/DataFramePlugin";
import type { Transformations } from "@/plugins/impl/data-frames/schema";
import type { ColumnId } from "@/plugins/impl/data-frames/types";
import { Functions } from "@/utils/functions";

const meta: Meta = {
  title: "DataFrame",
  args: {},
};

export default meta;

export const DataFrame: StoryObj = {
  render: () => {
    const [value, setValue] = useState<Transformations>();
    return (
      <DataFrameComponent
        get_column_values={async () => ({
          values: Array.from({ length: 100 }).map((_, i) => `value ${i}`),
          too_many_values: false,
        })}
        columns={
          new Map<ColumnId, string>([
            ["name" as ColumnId, "object"],
            ["age" as ColumnId, "int"],
            ["height" as ColumnId, "float"],
            ["picture" as ColumnId, "bytes"],
          ])
        }
        pageSize={5}
        value={value}
        setValue={(v) => {
          console.log(v);
          setValue(v);
        }}
        get_dataframe={() => Promise.reject(new Error("not implemented"))}
        search={Functions.THROW}
        host={document.body}
      />
    );
  },
};
