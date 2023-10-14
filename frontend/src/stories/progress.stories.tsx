/* Copyright 2023 Marimo. All rights reserved. */
import { Progress } from "@/components/ui/progress";
import type { Meta, StoryFn } from "@storybook/react";

const meta: Meta<typeof Progress> = {
  title: "Progress",
  component: Progress,
  args: {},
};

export default meta;

const Template: StoryFn<typeof Progress> = (args) => (
  <div className="bg-background">
    <Progress {...args} />
  </div>
);

export const Empty = Template.bind({});
Empty.args = {
  value: 0,
};

export const Half = Template.bind({});
Half.args = {
  value: 50,
};

export const Full = Template.bind({});
Full.args = {
  value: 100,
};
