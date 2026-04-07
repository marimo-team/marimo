/* Copyright 2026 Marimo. All rights reserved. */

import type { RowData } from "@tanstack/react-table";
import type { DataType } from "@/core/kernel/messages";
import { Objects } from "@/utils/objects";

declare module "@tanstack/react-table" {
  interface TableMeta<TData extends RowData> {
    rawData?: TData[]; // raw data for filtering/copying (present only if format_mapping is provided)
  }
}

// Pixel heights derived from Tailwind classes applied to table elements.
// row: h-6 = 24px (TableRow in renderers.tsx)
// header: min-h-10 = 40px (TableHead in renderers.tsx)
export const TABLE_ROW_HEIGHT_PX = 24;
export const TABLE_HEADER_HEIGHT_PX = 40;

// Below this column count, the table uses w-auto with a filler column
// to prevent columns from stretching unnecessarily
export const AUTO_WIDTH_MAX_COLUMNS = 4;

// Default number of visible rows when virtualizing without an explicit maxHeight.
export const DEFAULT_VIRTUAL_ROWS = 15;

// Minimum row count before virtualization kicks in. Below this threshold the
// DOM overhead is negligible and the virtualizer's measurement cost isn't
// worth it. Must be greater than DEFAULT_VIRTUAL_ROWS.
export const MIN_ROWS_TO_VIRTUALIZE = 100;

export type ColumnName = string;

export const ColumnHeaderStatsKeys = [
  "total",
  "nulls",
  "unique",
  "true",
  "false",
  "min",
  "max",
  "mean",
  "median",
  "std",
  "p5",
  "p25",
  "p75",
  "p95",
] as const;
export type ColumnHeaderStatsKey = (typeof ColumnHeaderStatsKeys)[number];
export type ColumnHeaderStats = Record<
  ColumnHeaderStatsKey,
  number | string | null
>;

export type FieldTypesWithExternalType = [
  columnName: string,
  [dataType: DataType, externalType: string],
][];
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

interface BinValue {
  bin_start: number | string | Date | null;
  bin_end: number | string | Date | null;
  count: number;
}
export type BinValues = BinValue[];

interface ValueCount {
  value: string;
  count: number;
}
export type ValueCounts = ValueCount[];

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
  // Check for datetime[X,Y] and datetime64[X,Y] format
  // We do this for any timezone-aware datetime type
  // not just UTC (as this is what Polars does by default)
  const match = /^datetime(?:64)?\[[^,]+,([^,]+)]$/.exec(dtype);
  return match?.[1]?.trim();
}

export type PageRange =
  | { type: "page"; page: number }
  | { type: "ellipsis"; key: string };
