/* Copyright 2023 Marimo. All rights reserved. */
import { ProgressComponent } from "@/plugins/layout/ProgressPlugin";
import type { Meta, StoryFn } from "@storybook/react";

const meta: Meta<typeof ProgressComponent> = {
  title: "ProgressComponent",
  component: ProgressComponent,
  args: {},
};

export default meta;

const Template: StoryFn<typeof ProgressComponent> = (args) => (
  <div className="bg-background">
    <ProgressComponent {...args} />
  </div>
);

export const Default = Template.bind({});
Default.args = {
  title: "Parsing documents",
  subtitle: "This may take a few seconds",
  progress: 4,
  total: 10,
};

export const Spinner = Template.bind({});
Spinner.args = {
  title: "Loading model",
  subtitle: "This may take a few seconds",
  progress: true,
};

export const SpinnerNoTitle = Template.bind({});
SpinnerNoTitle.args = {
  subtitle: "This may take a few seconds",
  progress: true,
};

export const ProgressNoTitle = Template.bind({});
ProgressNoTitle.args = {
  subtitle: "This may take a few seconds",
  progress: 8,
  total: 10,
};
