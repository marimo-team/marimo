/* Copyright 2024 Marimo. All rights reserved. */

import {
  LineChartIcon,
  BarChartIcon,
  PieChartIcon,
  SigmaIcon,
  HashIcon,
  BaselineIcon,
  AlignCenterVerticalIcon,
  ArrowDownToLineIcon,
  ArrowUpToLineIcon,
  ChartScatterIcon,
  SquareFunctionIcon,
  TableIcon,
  AreaChartIcon,
} from "lucide-react";
import type { ColorScheme } from "vega";
import type {
  AggregationFn,
  ChartType,
  SelectableDataType,
  TimeUnit,
} from "./types";

export const COUNT_FIELD = "__count__";
export const DEFAULT_COLOR_SCHEME = "default";

export const CHART_TYPE_ICON: Record<ChartType, React.ElementType> = {
  line: LineChartIcon,
  bar: BarChartIcon,
  pie: PieChartIcon,
  scatter: ChartScatterIcon,
  heatmap: TableIcon,
  area: AreaChartIcon,
};

export const AGGREGATION_TYPE_ICON: Record<AggregationFn, React.ElementType> = {
  none: SquareFunctionIcon,
  count: HashIcon,
  sum: SigmaIcon,
  mean: BaselineIcon,
  median: AlignCenterVerticalIcon,
  min: ArrowDownToLineIcon,
  max: ArrowUpToLineIcon,
  distinct: HashIcon,
};

export const AGGREGATION_TYPE_DESCRIPTIONS: Record<AggregationFn, string> = {
  none: "No aggregation",
  count: "Count of records",
  sum: "Sum of values",
  mean: "Mean of values",
  median: "Median of values",
  min: "Minimum value",
  max: "Maximum value",
  distinct: "Distinct values",
};

export const COLOR_SCHEMES: Array<ColorScheme | typeof DEFAULT_COLOR_SCHEME> = [
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

// Set a field to this to reflect that it is not set
export const EMPTY_VALUE = "";

export const TIME_UNIT_DESCRIPTIONS: Record<
  TimeUnit,
  [title: string, description: string]
> = {
  year: ["Year", "2025"],
  quarter: ["Quarter", "Q1 2025"],
  month: ["Month", "Jan 2025"],
  week: ["Week", "Jan 01, 2025"],
  day: ["Day", "Jan 01, 2025"],
  hours: ["Hour", "Jan 01, 2025 12:00"],
  minutes: ["Minute", "Jan 01, 2025 12:34"],
  seconds: ["Second", "Jan 01, 2025 12:34:56"],
  milliseconds: ["Millisecond", "Jan 01, 2025 12:34:56.789"],
  date: ["Date", "Jan 01, 2025"],
  dayofyear: ["Day of Year", "Day 1 of 2025"],
  yearmonth: ["Year Month", "Jan 2025"],
  yearmonthdate: ["Year Month Date", "Jan 01, 2025"],
  monthdate: ["Month Date", "Jan 01"],
};
