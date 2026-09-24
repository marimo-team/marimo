/* Copyright 2026 Marimo. All rights reserved. */

import type { DataType } from "@/core/kernel/messages";
import type { FieldTypesWithExternalType } from "./types";
import { uniformSample } from "./uniformSample";

function inferDataType(value: unknown): [type: DataType, displayType: string] {
  if (typeof value === "string") {
    return ["string", "string"];
  }
  if (typeof value === "number") {
    return ["number", "number"];
  }
  if (value instanceof Date) {
    return ["datetime", "datetime"];
  }
  if (typeof value === "boolean") {
    return ["boolean", "boolean"];
  }
  if (value == null) {
    return ["unknown", "object"];
  }
  return ["unknown", "object"];
}

export function inferFieldTypes<T>(items: T[]): FieldTypesWithExternalType {
  // No items
  if (items.length === 0) {
    return [];
  }

  // Not an object
  if (typeof items[0] !== "object") {
    return [];
  }

  const fieldTypes = new Map<string, [DataType, string]>();

  // This can be slow for large datasets,
  // so only sample 10 evenly distributed rows
  uniformSample(items, 10).forEach((item) => {
    if (typeof item !== "object" || item === null) {
      return;
    }
    // We will be a bit defensive and assume values are not homogeneous.
    // If any is a mimetype, then we will treat it as a mimetype (i.e. not sortable)
    Object.entries(item).forEach(([key, value]) => {
      // Keep the first-seen order, but infer the last non-null value's type.
      if (!fieldTypes.has(key) || value != null) {
        fieldTypes.set(key, inferDataType(value));
      }
    });
  });

  return [...fieldTypes.entries()];
}
