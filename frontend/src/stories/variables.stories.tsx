/* Copyright 2023 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react";
import { VariableTable } from "@/components/variables/variables-table";
import { CellId } from "@/core/model/ids";

const meta: Meta<typeof VariableTable> = {
  title: "VariableTable",
  component: VariableTable,
  args: {},
};

const variables = {
  "a": {
    "name": "a",
    "declaredBy": "1",
    "usedBy": ["2"],
  },
  "b": {
    "name": "b",
    "declaredBy": "2",
    "usedBy": ["3"],
  },
  "my_super_super_long_variable_name": {
    "name": "my_super_super_long_variable_name",
    "declaredBy": "3",
    "usedBy": Array.from({ length: 15 }, (_, i) => `${i + 4}`),
  },
  "c": {
    "name": "c",
    "declaredBy": "4",
    "usedBy": Array.from({ length: 3 }, (_, i) => `${i + 4}`),
  },
}

export default meta;
type Story = StoryObj<typeof VariableTable>;

export const Primary: Story = {
  render: () => (
    <div className="max-w-4xl">
      <VariableTable
        variables={variables}
        cellIds={["2", "1", "3"] as CellId[]}
      />
    </div>
  ),
};
