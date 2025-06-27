/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable react-hooks/rules-of-hooks */
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { SwitchableMultiSelect } from "@/components/forms/switchable-multi-select";
import { TooltipProvider } from "@/components/ui/tooltip";

const meta: Meta = {
  title: "SwitchableMultiSelect",
  component: SwitchableMultiSelect,
  args: {},
};

export default meta;
type Story = StoryObj;

export const Primary: Story = {
  render: (args, ctx) => {
    const [value, setValue] = useState<string[]>([]);
    return (
      <TooltipProvider>
        <SwitchableMultiSelect
          options={["apple", "banana", "blueberry", "grapes", "pineapple"]}
          value={value}
          placeholder="Select a fruit"
          onChange={(value) => setValue(value)}
        />
      </TooltipProvider>
    );
  },
};
