/* Copyright 2024 Marimo. All rights reserved. */

import type { DataType } from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";

/**
 * Strongly typed string/number
 */
export type ColumnId = (string | number) & { __columnId: "columnId" };

export type NumPyType = string;

/**
 * List of column Id and their data types
 *
 * We cannot use a js map, since maps don't preserve keys as ints (e.g. "1" and 1 are the same key)
 */
export type RawColumnDataTypes = Array<[ColumnId, [DataType, NumPyType]]>;
/**
 * Map of column Id and their data types
 * ES6 maps preserve keys as ints (e.g. "1" and 1 are different keys)
 */
export type ColumnDataTypes = Map<ColumnId, NumPyType>;

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
  "complex64",
  "complex128",
  "bool",
  "object",
  "str",
  "unicode",
  "datetime64",
  "timedelta64",
] as const;

export function numpyTypeToDataType(
  nptype: (typeof NUMPY_DTYPES)[number],
): DataType {
  switch (nptype) {
    case "int8":
    case "int16":
    case "int32":
    case "int64":
    case "uint8":
    case "uint16":
    case "uint32":
    case "uint64":
      return "integer";
    case "float16":
    case "float32":
    case "float64":
      return "number";
    case "complex64":
    case "complex128":
    case "object":
    case "str":
    case "unicode":
      return "string";
    case "bool":
      return "boolean";
    case "datetime64":
      return "datetime";
    case "timedelta64":
      return "date";
    default:
      logNever(nptype);
      return "unknown";
  }
}

export const AGGREGATION_FNS = [
  "count",
  "sum",
  "mean",
  "median",
  "min",
  "max",
] as const;
