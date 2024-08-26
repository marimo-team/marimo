/* Copyright 2024 Marimo. All rights reserved. */

import { Objects } from "@/utils/objects";
import type { FieldTypes } from "./vega-loader";

export function mergeAsArrays<T>(
  left: T | T[] | undefined,
  right: T | T[] | undefined,
): T[] {
  return [...toArray(left), ...toArray(right)];
}

function toArray<T>(value: T | T[] | undefined): T[] {
  if (!value) {
    return [];
  }
  if (Array.isArray(value)) {
    return value;
  }
  return [value];
}

export function getVegaFieldTypes(
  types: FieldTypes | undefined | null,
): FieldTypes | "auto" {
  if (!types || Object.keys(types).length === 0) {
    // If fieldTypes is provided, use it to parse the data
    // Otherwise, infer the data types
    return "auto";
  }
  // Convert all 'data' to 'string', because dates don't format back to
  // the correct formatting. For example, a date like '2024-01-01' will
  // be formatted to '2024-01-01T00:00:00.000Z'.
  return Objects.mapValues(types, (type) => {
    if (type === "date") {
      return "string";
    }
    return type;
  });
}
