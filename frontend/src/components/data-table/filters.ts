/* Copyright 2024 Marimo. All rights reserved. */

import { DataType } from "@/core/kernel/messages";
import { ConditionType } from "@/plugins/impl/data-frames/schema";
import { ColumnId } from "@/plugins/impl/data-frames/types";
import { assertNever } from "@/utils/assertNever";
import { RowData } from "@tanstack/react-table";

declare module "@tanstack/react-table" {
  //allows us to define custom properties for our columns
  interface ColumnMeta<TData extends RowData, TValue> {
    type?: "primitive" | "mime";
    rowHeader?: boolean;
    dtype?: string;
    dataType?: DataType;
    filterType?: FilterType;
  }
}

export type FilterType = "text" | "number" | "date" | "select" | "boolean";

// Filter is a factory function that creates a filter object
export const Filter = {
  number(opts: { min?: number; max?: number }) {
    return {
      type: "number",
      ...opts,
    } as const;
  },
  text(text: string) {
    return {
      type: "text",
      text,
    } as const;
  },
  date(opts: { min?: Date; max?: Date }) {
    return {
      type: "date",
      ...opts,
    } as const;
  },
  boolean(value: boolean) {
    return {
      type: "boolean",
      value,
    } as const;
  },
  select(options: string[]) {
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
  columnId: string,
  filter: ColumnFilterValue | undefined
): ConditionType[] | ConditionType {
  if (!filter) {
    return [];
  }
  const column_id = columnId as ColumnId;
  switch (filter.type) {
    case "number": {
      const conditions: ConditionType[] = [];
      if (filter.min !== undefined) {
        conditions.push({
          column_id,
          operator: ">=",
          value: filter.min,
        });
      }
      if (filter.max !== undefined) {
        conditions.push({
          column_id,
          operator: "<=",
          value: filter.max,
        });
      }
      return conditions;
    }
    case "text":
      return {
        column_id,
        operator: "contains",
        value: filter.text,
      };
    case "date": {
      const conditions: ConditionType[] = [];
      if (filter.min !== undefined) {
        conditions.push({
          column_id,
          operator: ">=",
          value: filter.min.toISOString(),
        });
      }
      if (filter.max !== undefined) {
        conditions.push({
          column_id,
          operator: "<=",
          value: filter.max.toISOString(),
        });
      }
      return conditions;
    }
    case "boolean":
      if (filter.value) {
        return {
          column_id,
          operator: "is_true",
        };
      }
      if (!filter.value) {
        return {
          column_id,
          operator: "is_false",
        };
      }

      return [];
    case "select":
      return {
        column_id,
        operator: "in",
        value: filter.options,
      };

    default:
      assertNever(filter);
  }
}
