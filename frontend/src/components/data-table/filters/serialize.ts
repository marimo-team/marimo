/* Copyright 2026 Marimo. All rights reserved. */

import type { ColumnFiltersState } from "@tanstack/react-table";
import type {
  FilterConditionType,
  FilterGroupType,
} from "@/plugins/impl/data-frames/schema";
import type { ColumnId } from "@/plugins/impl/data-frames/types";
import { assertNever } from "@/utils/assertNever";
import {
  dateToLocalISODate,
  dateToLocalISODateTime,
  dateToLocalISOTime,
} from "@/utils/dates";
import type { ColumnFilterValue } from "./builders";
import { isNullishFilter } from "./guards";

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
          ? dateToLocalISODate
          : filter.type === "time"
            ? dateToLocalISOTime
            : dateToLocalISODateTime;
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
