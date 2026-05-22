/* Copyright 2026 Marimo. All rights reserved. */

import type { ColumnFiltersState } from "@tanstack/react-table";
import type {
  FilterConditionType,
  FilterGroupType,
} from "@/plugins/impl/data-frames/schema";
import type { ColumnId } from "@/plugins/impl/data-frames/types";
import { assertNever } from "@/utils/assertNever";
import type { ColumnFilterValue } from "./builders";
import { isNullishFilter } from "./guards";

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
      return [
        {
          column_id: columnId,
          operator: filter.operator,
          type: "condition",
          negate: false,
        },
      ];
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
