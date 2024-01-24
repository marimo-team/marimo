/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable react-hooks/rules-of-hooks */
import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";
import { DataFrameComponent } from "@/plugins/impl/data-frames/DataFramePlugin";
import { Transformations } from "@/plugins/impl/data-frames/schema";

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
        columns={{
          name: "object",
          age: "int",
          height: "float",
          picture: "bytes",
        }}
        dataframeName={"df"}
        value={value}
        setValue={(v) => {
          console.log(v);
          setValue(v);
        }}
        get_dataframe={() => Promise.reject(new Error("not implemented"))}
      />
    );
  },
};
