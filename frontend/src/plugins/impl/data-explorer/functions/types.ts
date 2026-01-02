/* Copyright 2026 Marimo. All rights reserved. */

import { isString } from "lodash-es";
import type {
  ArgmaxDef,
  ArgminDef,
} from "vega-lite/types_unstable/aggregate.d.ts";
import type { isAggregateOp as isAggregateOpVega } from "vega-lite/types_unstable/aggregate.js";
import type { AggregateOp } from "vega-typings";

// Vega doesn't expose the constant, so we define all here
const AGGREGATE_OPS: readonly AggregateOp[] = [
  "argmax",
  "argmin",
  "average",
  "count",
  "distinct",
  "exponential",
  "exponentialb",
  "product",
  "max",
  "mean",
  "median",
  "min",
  "missing",
  "q1",
  "q3",
  "ci0",
  "ci1",
  "stderr",
  "stdev",
  "stdevp",
  "sum",
  "valid",
  "values",
  "variance",
  "variancep",
] as const;

// Subset of aggregate operations that we support
const SUPPORTED_AGGREGATE_OPS: readonly AggregateOp[] = [
  "average",
  "count",
  "distinct",
  "max",
  "mean",
  "median",
  "min",
  "q1",
  "q3",
  "stderr",
  "stdev",
  "sum",
];
type SupportedAggregateOp = (typeof SUPPORTED_AGGREGATE_OPS)[number];

// We implement our own isAggregateOp because
// The vega-lite types_unstable import path fails in Vite (module resolution issue)
export const isAggregateOp: typeof isAggregateOpVega = (
  a: string | ArgminDef | ArgmaxDef,
): a is AggregateOp => {
  if (!isString(a)) {
    return false;
  }

  return AGGREGATE_OPS.includes(a as AggregateOp);
};

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

export type FieldFunction = SupportedAggregateOp | "bin" | TimeUnitOp;
