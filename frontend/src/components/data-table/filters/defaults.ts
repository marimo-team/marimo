/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Column } from "@tanstack/react-table";
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import type { ColumnFilterValue } from "./builders";
import { isMembershipFilterType, isMembershipOp } from "./guards";
import { EDITABLE_FILTER_TYPES, type FilterType } from "./types";

export function columnEditableType<TData, TValue>(
  column: Column<TData, TValue>,
): FilterType {
  const ft = column.columnDef.meta?.filterType;
  if (!ft || !EDITABLE_FILTER_TYPES.has(ft)) {
    throw new Error(
      `Invalid or missing filterType for column ${column.id}: ${ft}`,
    );
  }
  return ft;
}

/** Minimal ColumnFilterValue for a (type, operator) pair, seeding extra fields for shapes that require them. */
export function defaultFilterValueFor(
  type: FilterType,
  operator: OperatorType,
): ColumnFilterValue {
  if (isMembershipFilterType(type) && isMembershipOp(operator)) {
    return { type, operator, values: [] };
  }
  return { type, operator } as ColumnFilterValue;
}
