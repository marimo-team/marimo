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

// Filter is a factory function that creates a filter object
export const Filter = {
  number(opts: { min?: number; max?: number; operator?: OperatorType }) {
    return {
      type: "number",
      ...opts,
    } as const;
  },
  text(opts: { text?: string; operator: OperatorType }) {
    return {
      type: "text",
      ...opts,
    } as const;
  },
  date(opts: { min?: Date; max?: Date; operator?: OperatorType }) {
    return {
      type: "date",
      ...opts,
    } as const;
  },
  datetime(opts: { min?: Date; max?: Date; operator?: OperatorType }) {
    return {
      type: "datetime",
      ...opts,
    } as const;
  },
  time(opts: { min?: Date; max?: Date; operator?: OperatorType }) {
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

export function filterToFilterCondition(
  columnIdString: string,
  filter: ColumnFilterValue | undefined,
): FilterConditionType[] {
  if (!filter) {
    return [];
  }
  const columnId = columnIdString as ColumnId;

  if (filter.operator === "is_null" || filter.operator === "is_not_null") {
    return [
      {
        column_id: columnId,
        operator: filter.operator,
        value: undefined,
        type: "condition",
        negate: false,
      },
    ];
  }

  switch (filter.type) {
    case "number": {
      const conditions: FilterConditionType[] = [];
      if (filter.min !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: ">=",
          value: filter.min,
          type: "condition",
          negate: false,
        });
      }
      if (filter.max !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: "<=",
          value: filter.max,
          type: "condition",
          negate: false,
        });
      }
      return conditions;
    }
    case "text":
      return [
        {
          column_id: columnId,
          operator: filter.operator,
          value: filter.text,
          type: "condition",
          negate: false,
        },
      ];
    case "datetime": {
      const conditions: FilterConditionType[] = [];
      if (filter.min !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: ">=",
          value: filter.min.toISOString(),
          type: "condition",
          negate: false,
        });
      }
      if (filter.max !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: "<=",
          value: filter.max.toISOString(),
          type: "condition",
          negate: false,
        });
      }
      return conditions;
    }
    case "date": {
      const conditions: FilterConditionType[] = [];
      if (filter.min !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: ">=",
          value: filter.min.toISOString(),
          type: "condition",
          negate: false,
        });
      }
      if (filter.max !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: "<=",
          value: filter.max.toISOString(),
          type: "condition",
          negate: false,
        });
      }
      return conditions;
    }
    case "time": {
      const conditions: FilterConditionType[] = [];
      if (filter.min !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: ">=",
          value: filter.min.toISOString(),
          type: "condition",
          negate: false,
        });
      }
      if (filter.max !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: "<=",
          value: filter.max.toISOString(),
          type: "condition",
          negate: false,
        });
      }
      return conditions;
    }
    case "boolean":
      if (filter.value) {
        return [
          {
            column_id: columnId,
            operator: "is_true",
            value: undefined,
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
            value: undefined,
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
