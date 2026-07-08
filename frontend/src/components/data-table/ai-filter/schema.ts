/* Copyright 2026 Marimo. All rights reserved. */

import type { FieldDef, FieldType, FilterSchema } from "better-filter-bar";
import type { DataType } from "@/core/kernel/messages";
import type { FieldTypesWithExternalType } from "../types";

/**
 * Map a marimo {@link DataType} to a better-filter-bar {@link FieldType}.
 * Categorical columns are treated as text (enum values aren't populated yet).
 */
export function dataTypeToFieldType(dataType: DataType): FieldType {
  switch (dataType) {
    case "integer":
    case "number":
      return "number";
    case "boolean":
      return "boolean";
    case "date":
    case "datetime":
    case "time":
      return "date";
    default:
      return "text";
  }
}

/** Build a better-filter-bar schema from a marimo table's field types. */
export function fieldTypesToFilterSchema(
  fieldTypes: FieldTypesWithExternalType | null | undefined,
): FilterSchema {
  const fields: FieldDef[] = (fieldTypes ?? []).map(
    ([columnName, [dataType]]) => toFieldDef(columnName, dataType),
  );

  return {
    fields,
    // Lenient: an unknown column warns instead of failing the whole query.
    allowUnknownFields: true,
  };
}

function toFieldDef(name: string, dataType: DataType): FieldDef {
  const type = dataTypeToFieldType(dataType);
  switch (type) {
    case "number":
      return { name, label: name, type: "number" };
    case "boolean":
      return { name, label: name, type: "boolean" };
    case "date":
      return {
        name,
        label: name,
        type: "date",
        includeTime: dataType === "datetime" || dataType === "time",
      };
    default:
      return { name, label: name, type: "text" };
  }
}
