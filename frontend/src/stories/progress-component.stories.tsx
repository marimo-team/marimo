/* Copyright 2024 Marimo. All rights reserved. */

import type { Meta, StoryFn } from "@storybook/react";
import { ProgressComponent } from "@/plugins/layout/ProgressPlugin";

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

export const WithRate = Template.bind({});
WithRate.args = {
  title: "Parsing documents",
  subtitle: "This may take a few seconds",
  progress: 4,
  total: 10,
  rate: 2,
};

export const WithEta = Template.bind({});
WithEta.args = {
  title: "Parsing documents",
  subtitle: "This may take a few seconds",
  progress: 4,
  total: 10,
  eta: 20,
};

export const WithRateAndEta = Template.bind({});
WithRateAndEta.args = {
  title: "Parsing documents",
  subtitle: "This may take a few seconds",
  progress: 4,
  total: 10,
  rate: 2,
  eta: 10,
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
