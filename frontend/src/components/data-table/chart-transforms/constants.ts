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
} from "lucide-react";
import type { ColorScheme } from "vega";
import { DEFAULT_COLOR_SCHEME } from "./chart-schemas";
import type { AggregationFn, SelectableDataType, TimeUnit } from "./types";

export const ChartType = {
  LINE: "line",
  BAR: "bar",
  PIE: "pie",
  SCATTER: "scatter",
} as const;
export type ChartType = (typeof ChartType)[keyof typeof ChartType];
export const CHART_TYPES = Object.values(ChartType);

export const CHART_TYPE_ICON: Record<ChartType, React.ElementType> = {
  line: LineChartIcon,
  bar: BarChartIcon,
  pie: PieChartIcon,
  scatter: ChartScatterIcon,
};

export const AGGREGATION_TYPE_ICON: Record<AggregationFn, React.ElementType> = {
  count: HashIcon,
  sum: SigmaIcon,
  mean: BaselineIcon,
  median: AlignCenterVerticalIcon,
  min: ArrowDownToLineIcon,
  max: ArrowUpToLineIcon,
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

export const TIME_UNIT_DESCRIPTIONS: Record<TimeUnit, string> = {
  year: "2025",
  quarter: "Q1 2025",
  month: "Jan 2025",
  week: "Jan 01, 2025",
  day: "Jan 01, 2025",
  hours: "Jan 01, 2025 12:00",
  minutes: "Jan 01, 2025 12:34",
  seconds: "Jan 01, 2025 12:34:56",
  milliseconds: "Jan 01, 2025 12:34:56.789",
  date: "Jan 01, 2025",
  dayofyear: "Day 1 of 2025",
  yearmonth: "Jan 2025",
  yearmonthdate: "Jan 01, 2025",
  monthdate: "Jan 01",
};
