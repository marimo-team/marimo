/* Copyright 2024 Marimo. All rights reserved. */

import {
  LineChartIcon,
  BarChartIcon,
  PieChartIcon,
  SigmaIcon,
  CircleSlash2,
  MinusIcon,
  PlusIcon,
  BinaryIcon,
  ChartScatterIcon,
} from "lucide-react";
import type { ChartType } from "./storage";
import type { AGGREGATION_FNS } from "@/plugins/impl/data-frames/types";
import type { ColorScheme } from "vega";
import { DEFAULT_COLOR_SCHEME, type ScaleType } from "./chart-schemas";

export const CHART_TYPE_ICON: Record<ChartType, React.ElementType> = {
  line: LineChartIcon,
  bar: BarChartIcon,
  pie: PieChartIcon,
  scatter: ChartScatterIcon,
};

export const AGGREGATION_TYPE_ICON: Record<
  (typeof AGGREGATION_FNS)[number],
  React.ElementType
> = {
  count: BinaryIcon,
  sum: SigmaIcon,
  mean: CircleSlash2,
  median: CircleSlash2,
  min: MinusIcon,
  max: PlusIcon,
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

export const SCALE_TYPE_DESCRIPTIONS: Record<ScaleType, string> = {
  number: "Continuous numerical scale",
  string: "Discrete categorical scale (inputs treated as strings)",
  temporal: "Continuous temporal scale",
};

// Set a field to this to reflect that it is not set
export const EMPTY_VALUE = "";
