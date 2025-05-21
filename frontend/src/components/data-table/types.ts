/* Copyright 2024 Marimo. All rights reserved. */

import type { DataType } from "@/core/kernel/messages";
import { Objects } from "@/utils/objects";

export type ColumnName = string;

export interface ColumnHeaderStats {
  total?: number | null;
  nulls?: number | null;
  unique?: number | null;
  true?: number | null;
  false?: number | null;
  min?: number | string | null;
  max?: number | string | null;
  mean?: number | string | null;
  median?: number | string | null;
  std?: number | string | null;
  p5?: number | string | null;
  p25?: number | string | null;
  p75?: number | string | null;
  p95?: number | string | null;
}

export type FieldTypesWithExternalType = Array<
  [columnName: string, [dataType: DataType, externalType: string]]
>;
export type FieldTypes = Record<string, DataType>;

export function toFieldTypes(
  fieldTypes: FieldTypesWithExternalType,
): FieldTypes {
  return Objects.collect(
    fieldTypes,
    ([columnName]) => columnName,
    ([, [type]]) => type,
  );
}

export const SELECT_COLUMN_ID = "__select__";

export const INDEX_COLUMN_NAME = "_marimo_row_id";

export const TOO_MANY_ROWS = "too_many";
export type TooManyRows = typeof TOO_MANY_ROWS;

export type DataTableSelection =
  | "single"
  | "multi"
  | "single-cell"
  | "multi-cell"
  | null;

export function extractTimezone(dtype: string | undefined): string | undefined {
  if (!dtype) {
    return undefined;
  }
  // Check for datetime[X,Y] format
  // We do this for any timezone-aware datetime type
  // not just UTC (as this is what Polars does by default)
  const match = /^datetime\[[^,]+,([^,]+)]$/.exec(dtype);
  return match?.[1]?.trim();
}
