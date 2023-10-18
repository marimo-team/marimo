/* Copyright 2023 Marimo. All rights reserved. */

/**
 * Map of column id to data type
 */
export interface ColumnDataTypes {
  [column_id: string]: string;
}

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
