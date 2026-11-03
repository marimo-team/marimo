/* Copyright 2026 Marimo. All rights reserved. */

import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { NotebookAccessSelector } from "./notebook-access-selector";

const meta = {
  title: "Chat/Notebook access",
  component: NotebookAccessSelector,
  args: { value: "ask", onValueChange: () => undefined },
  render: function Render(args) {
    const [value, setValue] = useState(args.value);
    return <NotebookAccessSelector value={value} onValueChange={setValue} />;
  },
} satisfies Meta<typeof NotebookAccessSelector>;

export default meta;
type Story = StoryObj<typeof meta>;

export const ReadOnly: Story = { args: { value: "ask" } };
export const SuggestEdits: Story = { args: { value: "agent" } };
export const FullAccess: Story = { args: { value: "code_mode" } };
