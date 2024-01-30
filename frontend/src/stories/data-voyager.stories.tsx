/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable react-hooks/rules-of-hooks */
import { DataVoyagerComponent } from "@/plugins/impl/data-voyager/DataVoyagerPlugin";
import { ChartSpec } from "@/plugins/impl/data-voyager/state/types";
import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";

const meta: Meta = {
  title: "DataVoyager",
  args: {},
};

export default meta;

export const DataVoyager: StoryObj = {
  render: () => {
    const [value, setValue] = useState<ChartSpec>();
    return (
      <DataVoyagerComponent
        data="https://github.com/vega/vega/blob/main/docs/data/stocks.csv"
        value={value}
        setValue={(v) => {
          console.log(v);
          setValue(v);
        }}
      />
    );
  },
};
