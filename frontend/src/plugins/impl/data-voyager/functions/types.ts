/* Copyright 2024 Marimo. All rights reserved. */

// Subset of aggregate operations that we support
type AggregateOp =
  | "average"
  | "count"
  | "distinct"
  | "max"
  | "mean"
  | "median"
  | "min"
  | "q1"
  | "q3"
  | "stderr"
  | "stdev"
  | "sum";

// Subset of time units that we support
export type TimeUnitOp =
  | "year"
  | "month"
  | "date"
  | "day"
  | "hours"
  | "minutes"
  | "seconds"
  | "milliseconds"
  | "yearmonth"
  | "yearmonthdate"
  | "monthdate";

export type FieldFunction = AggregateOp | "bin" | TimeUnitOp;
