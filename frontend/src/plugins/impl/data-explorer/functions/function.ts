/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-base-to-string */
import { FieldQuery } from "compassql/build/src/query/encoding";
import { isAggregateOp } from "vega-lite/build/src/aggregate";
import { FieldFunction, TimeUnitOp } from "./types";

// This code is adapted and simplified from https://github.com/vega/voyager

type FieldQueryFunctionMixins = Pick<
  FieldQuery,
  "aggregate" | "timeUnit" | "bin"
>;

export function toFieldQueryFunctionMixins(
  fn: FieldFunction | undefined,
): FieldQueryFunctionMixins {
  if (!fn) {
    return {};
  } else if (fn === "bin") {
    return { bin: true };
  } else if (isAggregateOp(fn)) {
    return { aggregate: fn };
  } else if (isTimeUnit(fn)) {
    return { timeUnit: fn };
  }
  return {};
}

function isTimeUnit(fn: FieldFunction): fn is TimeUnitOp {
  if (!fn) {
    return false;
  }
  return (
    SINGLE_TEMPORAL_FUNCTIONS.includes(fn) ||
    MULTI_TEMPORAL_FUNCTIONS.includes(fn)
  );
}

export const QUANTITATIVE_FUNCTIONS: FieldFunction[] = [
  "bin",
  "min",
  "max",
  "mean",
  "median",
  "sum",
];

export const SINGLE_TEMPORAL_FUNCTIONS: FieldFunction[] = [
  "year",
  "month",
  "date",
  "day",
  "hours",
  "minutes",
  "seconds",
  "milliseconds",
];

export const MULTI_TEMPORAL_FUNCTIONS: FieldFunction[] = [
  "yearmonth",
  "yearmonthdate",
  "monthdate",
];

export function fromFieldQueryFunctionMixins(
  fieldQuery: FieldQueryFunctionMixins,
): FieldFunction | undefined {
  const { aggregate, bin, timeUnit } = fieldQuery;
  if (bin) {
    return "bin";
  }
  if (aggregate) {
    return aggregate.toString() as FieldFunction;
  }
  if (timeUnit) {
    return timeUnit.toString() as FieldFunction;
  }

  return undefined;
}
