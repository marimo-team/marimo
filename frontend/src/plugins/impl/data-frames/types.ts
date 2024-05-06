/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Strongly typed string/number
 */
export type ColumnId = (string | number) & { __columnId: "columnId" };

/**
 * List of column Id and their data types
 *
 * We cannot use a js map, since maps don't preserve keys as ints (e.g. "1" and 1 are the same key)
 */
export type RawColumnDataTypes = Array<[ColumnId, string]>;
/**
 * Map of column Id and their data types
 * ES6 maps preserve keys as ints (e.g. "1" and 1 are different keys)
 */
export type ColumnDataTypes = Map<ColumnId, string>;

export const NUMPY_DTYPES = [
  "int8",
  "int16",
  "int32",
  "int64",
  "uint8",
  "uint16",
  "uint32",
  "uint64",
  "float16",
  "float32",
  "float64",
  "float128",
  "complex64",
  "complex128",
  "complex256",
  "bool",
  "object",
  "string_",
  "unicode_",
  "datetime64",
  "timedelta64",
] as const;

export const AGGREGATION_FNS = [
  "count",
  "sum",
  "mean",
  "median",
  "min",
  "max",
] as const;
