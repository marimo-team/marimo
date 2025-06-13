/* Copyright 2024 Marimo. All rights reserved. */

import type { Meta, StoryFn } from "@storybook/react";
import { StatComponent } from "@/plugins/layout/StatPlugin";

const meta: Meta<typeof StatComponent> = {
  title: "Stat",
  component: StatComponent,
  args: {},
};

export default meta;

const Template: StoryFn<typeof StatComponent> = (args) => (
  <div className="max-w-4xl">
    <StatComponent {...args} />
  </div>
);

export const Full = Template.bind({});
Full.args = {
  label: "Revenue",
  value: "$80,000",
  caption: "Last 30 days",
};

export const Increase = Template.bind({});
Increase.args = {
  label: "Revenue",
  value: "$80,000",
  caption: "+42%",
  direction: "increase",
};

export const Decrease = Template.bind({});
Decrease.args = {
  label: "Churn",
  value: "6.4%",
  caption: "-4%",
  direction: "decrease",
};

export const Bordered = Template.bind({});
Bordered.args = {
  label: "Revenue",
  value: "$80,000",
  caption: "Last 30 days",
  bordered: true,
};

export const Grid = () => {
  return (
    <div className="grid grid-cols-4 gap-4">
      <StatComponent
        label="Revenue"
        value="$80,000"
        caption="Last 30 days"
        bordered={true}
      />
      <StatComponent
        label="Profit"
        value="$30,000"
        caption="Last 30 days"
        bordered={true}
      />
      <StatComponent
        label="Marketing Spend"
        value="$10,000"
        caption="+42%"
        direction="increase"
        bordered={true}
      />
      <StatComponent
        label="Churn"
        value="6.4%"
        caption="-4%"
        direction="decrease"
        bordered={true}
      />
    </div>
  );
};

export const Flex = () => {
  return (
    <div className="flex flex-row gap-4">
      <div className="flex-1">
        <StatComponent
          label="Revenue"
          value="$80,000"
          caption="Last 30 days"
          bordered={true}
        />
      </div>
      <div className="flex-1">
        <StatComponent
          label="Profit"
          value="$30,000"
          caption="Last 30 days"
          bordered={true}
        />
      </div>
      <div className="flex-1">
        <StatComponent
          label="Marketing Spend"
          value="$10,000"
          caption="+42%"
          direction="increase"
          bordered={true}
        />
      </div>
      <div className="flex-1">
        <StatComponent
          label="Churn"
          value="6.4%"
          caption="-4%"
          direction="decrease"
          bordered={true}
        />
      </div>
    </div>
  );
};
