/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable react-hooks/rules-of-hooks */
import { DataExplorerComponent } from "@/plugins/impl/data-explorer/DataExplorerPlugin";
import { ChartSpec } from "@/plugins/impl/data-explorer/state/types";
import type { Meta, StoryObj } from "@storybook/react";
import { useState } from "react";

const meta: Meta = {
  title: "DataExplorer",
  args: {},
};

export default meta;

export const DataExplorer: StoryObj = {
  render: () => {
    const [value, setValue] = useState<ChartSpec>();
    return (
      <DataExplorerComponent
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
