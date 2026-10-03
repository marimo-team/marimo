/* Copyright 2026 Marimo. All rights reserved. */

import {
  AlignCenterVerticalIcon,
  AreaChartIcon,
  ArrowDownToLineIcon,
  ArrowUpToLineIcon,
  BarChartIcon,
  BaselineIcon,
  ChartColumn,
  ChartNoAxesColumn,
  ChartScatterIcon,
  HashIcon,
  LineChartIcon,
  PieChartIcon,
  RulerDimensionLine,
  SigmaIcon,
  SquareFunctionIcon,
  TableIcon,
} from "lucide-react";
import type { ColorScheme } from "vega-typings";
import type {
  AggregationFn,
  ChartType,
  SelectableDataType,
  TimeUnit,
  ValidAggregationFn,
} from "./types";

export const COUNT_FIELD = "__count__";
export const DEFAULT_COLOR_SCHEME = "default";
export const DEFAULT_TIME_UNIT = "yearmonthdate";
export const DEFAULT_MAX_BINS_FACET = 6;

// Set a field to this to reflect that it is not set
export const EMPTY_VALUE = "";

export const CHART_TYPE_ICON: Record<ChartType, React.ElementType> = {
  line: LineChartIcon,
  bar: BarChartIcon,
  pie: PieChartIcon,
  scatter: ChartScatterIcon,
  heatmap: TableIcon,
  area: AreaChartIcon,
};

export const DEFAULT_AGGREGATION: ValidAggregationFn = "mean"; // For y-axis, we default to mean
export const AGGREGATION_TYPE_ICON: Partial<
  Record<AggregationFn, React.ElementType>
> = {
  none: SquareFunctionIcon,
  count: HashIcon,
  sum: SigmaIcon,
  mean: BaselineIcon,
  median: AlignCenterVerticalIcon,
  min: ArrowDownToLineIcon,
  max: ArrowUpToLineIcon,
  distinct: HashIcon,
  valid: HashIcon,
  stdev: ChartNoAxesColumn,
  stdevp: ChartNoAxesColumn,
  variance: ChartColumn,
  variancep: ChartColumn,
  bin: RulerDimensionLine,
};

export const AGGREGATION_TYPE_DESCRIPTIONS: Partial<
  Record<AggregationFn, string>
> = {
  none: "No aggregation",
  count: "Count of records",
  sum: "Sum of values",
  mean: "Mean of values",
  median: "Median of values",
  min: "Minimum value",
  max: "Maximum value",
  distinct: "Count of distinct records",
  valid: "Count non-null records",
  stdev: "Standard deviation",
  stdevp: "Standard deviation of population",
  variance: "Variance",
  variancep: "Variance of population",
  bin: "Group values into bins",
};

export const COLOR_SCHEMES: (ColorScheme | typeof DEFAULT_COLOR_SCHEME)[] = [
  DEFAULT_COLOR_SCHEME,
  // Categorical schemes
  "accent",
  "category10",
  "category20",
  "category20b",
  "category20c",
  "dark2",
  "paired",
  "pastel1",
  "pastel2",
  "set1",
  "set2",
  "set3",
  "tableau10",
  "tableau20",
  // Sequential single-hue schemes
  "blues",
  "greens",
  "greys",
  "oranges",
  "purples",
  "reds",
  // Sequential multi-hue schemes
  "bluegreen",
  "bluepurple",
  "goldgreen",
  "goldorange",
  "goldred",
  "greenblue",
  "orangered",
  "purplebluegreen",
  "purplered",
  "redpurple",
  "yellowgreenblue",
  "yelloworangered",
  // Diverging schemes
  "blueorange",
  "brownbluegreen",
  "purplegreen",
  "pinkyellowgreen",
  "purpleorange",
  "redblue",
  "redgrey",
  "redyellowblue",
  "redyellowgreen",
  "spectral",
  // Cyclical schemes
  "rainbow",
  "sinebow",
] as const;

export const SCALE_TYPE_DESCRIPTIONS: Record<SelectableDataType, string> = {
  number: "Continuous numerical scale",
  string: "Discrete categorical scale (inputs treated as strings)",
  temporal: "Continuous temporal scale",
};

export const TIME_UNIT_DESCRIPTIONS: Record<
  TimeUnit,
  [title: string, description: string]
> = {
  year: ["Year", "2025"],
  quarter: ["Quarter of year", "Q1"],
  month: ["Month of year", "Jan"],
  week: ["Week of year", "Week 1"],
  day: ["Day of week", "Sunday"],
  hours: ["Hour of day", "12:00"],
  minutes: ["Minute of hour", "34"],
  seconds: ["Second of minute", "56"],
  milliseconds: ["Millisecond of second", "789"],
  date: ["Day of month", "1"],
  dayofyear: ["Day of year", "Day 1"],
  yearmonth: ["Year Month", "Jan 2025"],
  yearmonthdate: ["Year Month Date", "Jan 01, 2025"],
  yearmonthdatehours: ["Calendar hour", "Jan 01, 2025 12:00"],
  monthdate: ["Month Date", "Jan 01"],
};
