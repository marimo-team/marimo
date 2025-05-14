/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Similar to VegaLite's ScaleType, https://vega.github.io/vega-lite/docs/scale.html#type
 */
export const SELECTABLE_DATA_TYPES = ["number", "string", "temporal"] as const;
export type SelectableDataType = (typeof SELECTABLE_DATA_TYPES)[number];

/**
 * Used for adding data types in Altair encoding
 */
export const DATA_TYPE_LETTERS: Record<SelectableDataType, string> = {
  number: "Q",
  string: "N",
  temporal: "T",
} as const;
export type DataTypeLetter =
  (typeof DATA_TYPE_LETTERS)[keyof typeof DATA_TYPE_LETTERS];

/**
 * Similar to VegaLite's TimeUnit, https://vega.github.io/vega-lite/docs/timeunit.html
 */
export const SINGLE_TIME_UNITS = [
  // Individual units
  "year", // Gregorian calendar years.
  "quarter", // Three-month intervals, starting in one of January, April, July, and October.
  "month", // Calendar months (January, February, etc.).
  "date", // Calendar day of the month (January 1, January 2, etc.).
  "week", // Sunday-based weeks. Days before the first Sunday of the year are considered to be in week 0, the first Sunday of the year is the start of week 1, the second Sunday week 2, etc..
  "day", // Day of the week (Sunday, Monday, etc.).
  "dayofyear", // Day of the year (1, 2, …, 365, etc.).
  "hours", // Hours of the day (12:00am, 1:00am, etc.).
  "minutes", // Minutes in an hour (12:00, 12:01, etc.).
  "seconds", // Seconds in a minute (12:00:00, 12:00:01, etc.).
  "milliseconds", // Milliseconds in a second.
] as const;
// Common combinations of the above
export const COMBINED_TIME_UNITS = [
  "yearmonth",
  "yearmonthdate",
  "monthdate",
] as const;
export const TIME_UNITS = [
  ...SINGLE_TIME_UNITS,
  ...COMBINED_TIME_UNITS,
] as const;
export type TimeUnit = (typeof TIME_UNITS)[number];

// Time units that are not selectable options but are used for tooltips
export const TIME_UNIT_TOOLTIPS = [
  ...TIME_UNITS,
  "yearmonthdatehoursminutesseconds",
  "yearmonthdate",
  "hoursminutesseconds",
] as const;
export type TimeUnitTooltip = (typeof TIME_UNIT_TOOLTIPS)[number];

/**
 * Similar to VegaLite's SortOrder, https://vega.github.io/vega-lite/docs/sort.html#order
 */
export const SORT_TYPES = ["ascending", "descending"] as const;
export type SortType = (typeof SORT_TYPES)[number];

export const NONE_AGGREGATION = "none";
export const BIN_AGGREGATION = "bin"; // We use this not to aggregate, but to bin

/**
 * Subset of VegaLite's AggregateOp, https://vega.github.io/vega-lite/docs/aggregate.html#op
 */
export const AGGREGATION_FNS = [
  NONE_AGGREGATION,
  "count",
  "sum",
  "mean",
  "median",
  "min",
  "max",
  "distinct",
  "valid",
  "stdev",
  "stdevp",
  "variance",
  "variancep",
  BIN_AGGREGATION,
] as const;
export type AggregationFn = (typeof AGGREGATION_FNS)[number];

/*
 * Subset of AGGREGATION_FNS that are valid for string data types
 */
export const STRING_AGGREGATION_FNS: AggregationFn[] = [
  "none",
  "count",
  "distinct",
  "valid",
];

/**
 * Subset of VegaLite's MarkType, https://vega.github.io/vega-lite/docs/mark.html#types
 */
export const ChartType = {
  LINE: "line",
  BAR: "bar",
  PIE: "pie",
  SCATTER: "scatter",
  HEATMAP: "heatmap",
  AREA: "area",
} as const;
export type ChartType = (typeof ChartType)[keyof typeof ChartType];
export const CHART_TYPES = Object.values(ChartType);
