/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { ColumnFiltersState, RowData } from "@tanstack/react-table";
import type { DataType } from "@/core/kernel/messages";
import type {
  FilterConditionType,
  FilterGroupType,
} from "@/plugins/impl/data-frames/schema";
import type { ColumnId } from "@/plugins/impl/data-frames/types";
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import { assertNever } from "@/utils/assertNever";
import { Logger } from "@/utils/Logger";

declare module "@tanstack/react-table" {
  //allows us to define custom properties for our columns
  interface ColumnMeta<TData extends RowData, TValue> {
    rowHeader?: boolean;
    dtype?: string;
    dataType?: DataType;
    filterType?: FilterType;
    minFractionDigits?: number;
  }
}

export type FilterType =
  | "text"
  | "number"
  | "date"
  | "datetime"
  | "time"
  | "select"
  | "boolean";

export const NULLISH_OPS = ["is_null", "is_not_null"] as const;
export const MEMBERSHIP_OPS = ["in", "not_in"] as const;
export const NUMBER_COMPARISON_OPS = [
  "==",
  "!=",
  ">",
  ">=",
  "<",
  "<=",
] as const;
export const TEXT_SCALAR_OPS = [
  "contains",
  "equals",
  "does_not_equal",
  "regex",
  "starts_with",
  "ends_with",
] as const;

export const DATETIME_COMPARISON_OPS = [
  "==",
  "!=",
  ">",
  ">=",
  "<",
  "<=",
] as const;

export const NUMBER_OPS = [
  "between",
  ...NUMBER_COMPARISON_OPS,
  ...NULLISH_OPS,
] as const;
export const TEXT_OPS = [
  ...TEXT_SCALAR_OPS,
  ...MEMBERSHIP_OPS,
  "is_empty",
  ...NULLISH_OPS,
] as const;
export const DATETIME_OPS = [
  "between",
  ...DATETIME_COMPARISON_OPS,
  ...NULLISH_OPS,
] as const;

export type NullishOp = (typeof NULLISH_OPS)[number];
export type MembershipOp = (typeof MEMBERSHIP_OPS)[number];
export type NumberComparisonOp = (typeof NUMBER_COMPARISON_OPS)[number];
export type TextScalarOp = (typeof TEXT_SCALAR_OPS)[number];
export type DatetimeComparisonOp = (typeof DATETIME_COMPARISON_OPS)[number];

interface NullishOpts {
  operator: NullishOp;
}

type NumberFilterOpts =
  | { operator: "between"; min: number; max: number }
  | { operator: NumberComparisonOp; value: number }
  | NullishOpts;

type TextFilterOpts =
  | { operator: TextScalarOp; text: string }
  | { operator: MembershipOp; values: string[] }
  | { operator: "is_empty" }
  | NullishOpts;

type DateLikeFilterOpts =
  | { operator: "between"; min: Date; max: Date }
  | { operator: DatetimeComparisonOp; value: Date }
  | NullishOpts;

// Filter is a factory function that creates a filter object
export const Filter = {
  number(opts: NumberFilterOpts) {
    return {
      type: "number",
      ...opts,
    } as const;
  },
  text(opts: TextFilterOpts) {
    return {
      type: "text",
      ...opts,
    } as const;
  },
  date(opts: DateLikeFilterOpts) {
    return {
      type: "date",
      ...opts,
    } as const;
  },
  datetime(opts: DateLikeFilterOpts) {
    return {
      type: "datetime",
      ...opts,
    } as const;
  },
  time(opts: DateLikeFilterOpts) {
    return {
      type: "time",
      ...opts,
    } as const;
  },
  boolean(opts: { value?: boolean; operator?: OperatorType }) {
    return {
      type: "boolean",
      ...opts,
    } as const;
  },
  select(opts: { options: unknown[]; operator: OperatorType }) {
    return {
      type: "select",
      ...opts,
    } as const;
  },
};
export type ColumnFilterValue = ReturnType<
  (typeof Filter)[keyof typeof Filter]
>;
export type ColumnFilterForType<T extends FilterType> = T extends FilterType
  ? Extract<ColumnFilterValue, { type: T }>
  : never;

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

function pad4(n: number): string {
  return n.toString().padStart(4, "0");
}

export function dateToISODate(d: Date): string {
  return `${pad4(d.getFullYear())}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

export function dateToISOTime(d: Date): string {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

export function dateToISODateTime(d: Date): string {
  return `${dateToISODate(d)}T${dateToISOTime(d)}`;
}

function isNullishFilter(
  filter: ColumnFilterValue,
): filter is Extract<
  ColumnFilterValue,
  { operator: "is_null" | "is_not_null" }
> {
  return filter.operator === "is_null" || filter.operator === "is_not_null";
}

export function filterToFilterCondition(
  columnIdString: string,
  filter: ColumnFilterValue | undefined,
): FilterConditionType[] {
  if (!filter) {
    return [];
  }
  const columnId = columnIdString as ColumnId;

  if (isNullishFilter(filter)) {
    return [
      {
        column_id: columnId,
        operator: filter.operator,
        type: "condition",
        negate: false,
      },
    ];
  }

  switch (filter.type) {
    case "number":
      switch (filter.operator) {
        case "between":
          return [
            {
              column_id: columnId,
              operator: "between",
              value: { min: filter.min, max: filter.max },
              type: "condition",
              negate: false,
            },
          ];
        case "==":
        case "!=":
        case ">":
        case ">=":
        case "<":
        case "<=":
          return [
            {
              column_id: columnId,
              operator: filter.operator,
              value: filter.value,
              type: "condition",
              negate: false,
            },
          ];
        default:
          assertNever(filter);
      }
    case "text":
      switch (filter.operator) {
        case "contains":
        case "equals":
        case "does_not_equal":
        case "regex":
        case "starts_with":
        case "ends_with":
          return [
            {
              column_id: columnId,
              operator: filter.operator,
              value: filter.text,
              type: "condition",
              negate: false,
            },
          ];
        case "in":
        case "not_in":
          return [
            {
              column_id: columnId,
              operator: filter.operator,
              value: filter.values,
              type: "condition",
              negate: false,
            },
          ];
        case "is_empty":
          return [
            {
              column_id: columnId,
              operator: "is_empty",
              type: "condition",
              negate: false,
            },
          ];
        default:
          assertNever(filter);
      }
    case "date":
    case "datetime":
    case "time": {
      const encode =
        filter.type === "date"
          ? dateToISODate
          : filter.type === "time"
            ? dateToISOTime
            : dateToISODateTime;
      switch (filter.operator) {
        case "between":
          return [
            {
              column_id: columnId,
              operator: "between",
              value: { min: encode(filter.min), max: encode(filter.max) },
              type: "condition",
              negate: false,
            },
          ];
        case "==":
        case "!=":
        case ">":
        case ">=":
        case "<":
        case "<=":
          return [
            {
              column_id: columnId,
              operator: filter.operator,
              value: encode(filter.value),
              type: "condition",
              negate: false,
            },
          ];
        default:
          assertNever(filter);
      }
    }
    case "boolean":
      if (filter.value) {
        return [
          {
            column_id: columnId,
            operator: "is_true",
            type: "condition",
            negate: false,
          },
        ];
      }
      if (!filter.value) {
        return [
          {
            column_id: columnId,
            operator: "is_false",
            type: "condition",
            negate: false,
          },
        ];
      }

      return [];
    case "select": {
      let operator = filter.operator;
      if (filter.operator !== "in" && filter.operator !== "not_in") {
        Logger.warn("Invalid operator for select filter", {
          operator: filter.operator,
        });
        operator = "in";
      }
      return [
        {
          column_id: columnId,
          operator,
          value: filter.options,
          type: "condition",
          negate: false,
        },
      ];
    }

    default:
      assertNever(filter);
  }
}

export function filtersToFilterGroup(
  columnFilters: ColumnFiltersState,
): FilterGroupType {
  const conditions = columnFilters.flatMap((filter) =>
    filterToFilterCondition(filter.id, filter.value as ColumnFilterValue),
  );
  // To maintain existing behavior "and" all the conditions
  return {
    type: "group",
    operator: "and",
    children: conditions,
    negate: false,
  };
}
