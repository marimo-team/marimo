/* Copyright 2026 Marimo. All rights reserved. */

import type { FieldTypesWithExternalType } from "@/components/data-table/types";
import type { ColumnDataTypes, ColumnId } from "../types";

/**
 * Get the effective columns at a given transform step.
 *
 * @param columns - Original columns (fallback)
 * @param columnTypesPerStep - Column types at each step from backend
 *   - Index 0 = original columns
 *   - Index N = columns after transform N-1
 * @param selectedTransform - Index of the currently selected transform
 * @returns The effective columns before the selected transform
 */
export function getEffectiveColumns(
  columns: ColumnDataTypes,
  columnTypesPerStep: FieldTypesWithExternalType[] | undefined,
  stepIndex = 0,
): ColumnDataTypes {
  // If no columnTypesPerStep, fall back to original columns
  if (!columnTypesPerStep || columnTypesPerStep.length === 0) {
    return columns;
  }

  // columnTypesPerStep[0] = original columns
  // columnTypesPerStep[N] = columns after transform N-1
  // For the selected transform, we want columns BEFORE it, so index = selectedTransform
  const safeIndex = Math.min(stepIndex, columnTypesPerStep.length - 1);
  const fieldTypes = columnTypesPerStep[safeIndex];

  if (!fieldTypes) {
    return columns;
  }

  const newColumns = new Map<ColumnId, string>();
  for (const [name, [dataType]] of fieldTypes) {
    newColumns.set(name as ColumnId, dataType);
  }
  return newColumns;
}
