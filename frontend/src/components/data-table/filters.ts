/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import type { RowData } from "@tanstack/react-table";
import type { DataType } from "@/core/kernel/messages";
import type { ConditionType } from "@/plugins/impl/data-frames/schema";
import type { ColumnId } from "@/plugins/impl/data-frames/types";
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import { assertNever } from "@/utils/assertNever";

declare module "@tanstack/react-table" {
  //allows us to define custom properties for our columns
  interface ColumnMeta<TData extends RowData, TValue> {
    rowHeader?: boolean;
    dtype?: string;
    dataType?: DataType;
    filterType?: FilterType;
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
  number(opts: { min?: number; max?: number }) {
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
  date(opts: { min?: Date; max?: Date }) {
    return {
      type: "date",
      ...opts,
    } as const;
  },
  datetime(opts: { min?: Date; max?: Date }) {
    return {
      type: "datetime",
      ...opts,
    } as const;
  },
  time(opts: { min?: Date; max?: Date }) {
    return {
      type: "time",
      ...opts,
    } as const;
  },
  boolean(value: boolean) {
    return {
      type: "boolean",
      value,
    } as const;
  },
  select(options: unknown[]) {
    return {
      type: "select",
      options,
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
): ConditionType[] | ConditionType {
  if (!filter) {
    return [];
  }
  const columnId = columnIdString as ColumnId;
  switch (filter.type) {
    case "number": {
      const conditions: ConditionType[] = [];
      if (filter.min !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: ">=",
          value: filter.min,
        });
      }
      if (filter.max !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: "<=",
          value: filter.max,
        });
      }
      return conditions;
    }
    case "text":
      return {
        column_id: columnId,
        operator: filter.operator,
        value: filter.text,
      };
    case "datetime": {
      const conditions: ConditionType[] = [];
      if (filter.min !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: ">=",
          value: filter.min.toISOString(),
        });
      }
      if (filter.max !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: "<=",
          value: filter.max.toISOString(),
        });
      }
      return conditions;
    }
    case "date": {
      const conditions: ConditionType[] = [];
      if (filter.min !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: ">=",
          value: filter.min.toISOString(),
        });
      }
      if (filter.max !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: "<=",
          value: filter.max.toISOString(),
        });
      }
      return conditions;
    }
    case "time": {
      const conditions: ConditionType[] = [];
      if (filter.min !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: ">=",
          value: filter.min.toISOString(),
        });
      }
      if (filter.max !== undefined) {
        conditions.push({
          column_id: columnId,
          operator: "<=",
          value: filter.max.toISOString(),
        });
      }
      return conditions;
    }
    case "boolean":
      if (filter.value) {
        return {
          column_id: columnId,
          operator: "is_true",
        };
      }
      if (!filter.value) {
        return {
          column_id: columnId,
          operator: "is_false",
        };
      }

      return [];
    case "select":
      return {
        column_id: columnId,
        operator: "in",
        value: filter.options,
      };

    default:
      assertNever(filter);
  }
}
