/* Copyright 2023 Marimo. All rights reserved. */
import { Debugger } from "@/components/debugger/debugger-code";
import type { Meta, StoryFn } from "@storybook/react";

const meta: Meta<typeof Debugger> = {
  title: "Debugger",
  component: Debugger,
  args: {},
};

export default meta;

const Template: StoryFn<typeof Debugger> = (args) => (
  <div className="bg-background">
    <Debugger {...args} />
  </div>
);

export const Default = Template.bind({});
Default.args = {
  code: "print('Hello, world!')",
  onSubmit: (code) => console.log(code),
};
