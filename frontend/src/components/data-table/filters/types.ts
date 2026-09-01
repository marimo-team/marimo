/* Copyright 2026 Marimo. All rights reserved. */

import type { RowData } from "@tanstack/react-table";
import type { DataType } from "@/core/kernel/messages";

declare module "@tanstack/react-table" {
  //allows us to define custom properties for our columns
  interface ColumnMeta<TData extends RowData, TValue> {
    rowHeader?: boolean;
    /** Normalized marimo type used for backend-independent UI behavior. */
    dataType?: DataType;
    /** Source-library type, such as pandas `timedelta64[ns]`. */
    dtype?: string;
    filterType?: FilterType;
    minFractionDigits?: number;
    width?: number;
  }
}

const FILTER_TYPES = [
  "text",
  "number",
  "date",
  "datetime",
  "time",
  "boolean",
] as const;
export type FilterType = (typeof FILTER_TYPES)[number];

export const EDITABLE_FILTER_TYPES: ReadonlySet<FilterType> = new Set(
  FILTER_TYPES,
);

export type FormattedFilter =
  | { kind: "scalar"; operator: string; value?: string }
  | { kind: "list"; operator: string; items: string[] };
