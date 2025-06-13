/* Copyright 2024 Marimo. All rights reserved. */

import type { Meta } from "@storybook/react";
import type { VegaLiteSpec } from "@/plugins/impl/vega/types";
import VegaComponent from "@/plugins/impl/vega/vega-component";
import {
  AREA_CHART,
  BAR_CHART,
  CIRCLE_2_CHART,
  CIRCLE_CHART,
  DONUT_CHART,
  LINE_CHART,
  PIE_CHART,
  POINT_CHART,
  RECT_CHART,
  RULE_CHART,
  SQUARE_CHART,
  STACKED_BAR_CHART,
  TICK_CHART,
} from "./__fixtures__/vega";

const meta: Meta = {
  title: "Vega",
  args: {},
};
export default meta;

const selectionOptions = [true, false, "interval", "point"] as const;

const chartWithData = (spec: VegaLiteSpec) => (
  <div className="flex flex-col gap-4">
    {selectionOptions.map((selection) => (
      <VegaComponent
        key={String(selection)}
        setValue={console.log}
        value={{}}
        spec={spec}
        chartSelection={selection}
        fieldSelection={true}
      />
    ))}
  </div>
);

export const AreaChart = () => chartWithData(AREA_CHART);
export const BarChart = () => chartWithData(BAR_CHART);
export const CircleChart = () => chartWithData(CIRCLE_CHART);
export const Circle2Chart = () => chartWithData(CIRCLE_2_CHART);
export const DonutChart = () => chartWithData(DONUT_CHART);
export const LineChart = () => chartWithData(LINE_CHART);
export const PieChart = () => chartWithData(PIE_CHART);
export const PointScatterChart = () => chartWithData(POINT_CHART);
export const RectChart = () => chartWithData(RECT_CHART);
export const RuleChart = () => chartWithData(RULE_CHART);
export const SquareChart = () => chartWithData(SQUARE_CHART);
export const StackedBarChart = () => chartWithData(STACKED_BAR_CHART);
export const TickChart = () => chartWithData(TICK_CHART);
