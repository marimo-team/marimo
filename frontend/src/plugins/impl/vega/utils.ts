/* Copyright 2026 Marimo. All rights reserved. */

import { Objects } from "@/utils/objects";
import type { DataType, FieldTypes, VegaDataType } from "./vega-loader";

export type ContainerWidth = number | "container";

/**
 * Get the container width from a Vega-Lite spec.
 *
 * For unit specs, `width` is at the top level. For facet/repeat specs,
 * `width` is nested inside `spec`. This does not handle hconcat/vconcat and Vega spec
 * where the width may be a signal. These cases are covered by
 * the CSS fallback `.vega-embed:has(> .chart-wrapper.fit-x)`.
 */
export function getContainerWidth(spec: unknown): ContainerWidth | undefined {
  if (typeof spec === "object" && spec !== null) {
    if ("width" in spec) {
      return spec.width as ContainerWidth | undefined;
    }
    // Faceted/repeated spec
    if ("spec" in spec) {
      return getContainerWidth(spec.spec);
    }
  }
  return undefined;
}

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
  types: Record<string, DataType> | undefined | null,
): FieldTypes | "auto" {
  if (!types || Object.keys(types).length === 0) {
    // If fieldTypes is provided, use it to parse the data
    // Otherwise, infer the data types
    return "auto";
  }
  // Convert all 'date' to 'string', because dates don't format back to
  // the correct formatting. For example, a date like '2024-01-01' will
  // be formatted to '2024-01-01T00:00:00.000Z'.
  return Objects.mapValues(types, (type): VegaDataType => {
    if (type === "date") {
      return "string";
    }
    if (type === "time") {
      return "string";
    }
    if (type === "datetime") {
      return "date";
    }
    return type;
  });
}
