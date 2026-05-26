/* Copyright 2026 Marimo. All rights reserved. */

import { logNever } from "@/utils/assertNever";
import {
  dateToLocalISODate,
  dateToLocalISOTime,
  exactDateTime,
} from "@/utils/dates";
import { OPERATOR_LABELS } from "../operator-labels";
import { stringifyUnknownValue } from "../utils";
import type { ColumnFilterValue } from "./builders";
import type { FormattedFilter } from "./types";

interface FormatContext {
  locale: string;
  timezone: string | undefined;
}

export function formatValue(
  value: ColumnFilterValue,
  ctx: FormatContext,
): FormattedFilter | undefined {
  if (!("type" in value)) {
    return;
  }

  if (value.operator === "is_null") {
    return { kind: "scalar", operator: "is null" };
  }
  if (value.operator === "is_not_null") {
    return { kind: "scalar", operator: "is not null" };
  }

  if (value.type === "number") {
    switch (value.operator) {
      case "between":
        return {
          kind: "scalar",
          operator: OPERATOR_LABELS.between.toLowerCase(),
          value: `${value.min} - ${value.max}`,
        };
      case "==":
      case "!=":
      case ">":
      case ">=":
      case "<":
      case "<=":
        return {
          kind: "scalar",
          operator: value.operator,
          value: String(value.value),
        };
      case "in":
      case "not_in":
        return {
          kind: "list",
          operator: value.operator === "in" ? "is in" : "not in",
          items: value.values
            .map((v) => stringifyUnknownValue({ value: v }))
            .toSorted((a, b) => a.localeCompare(b)),
        };
    }
  }
  if (value.type === "text") {
    switch (value.operator) {
      case "in":
      case "not_in":
        return {
          kind: "list",
          operator: value.operator === "in" ? "is in" : "not in",
          items: value.values
            .map((v) => stringifyUnknownValue({ value: v }))
            .toSorted((a, b) => a.localeCompare(b)),
        };
      case "is_empty":
        return { kind: "scalar", operator: "is empty" };
      case "contains":
      case "equals":
      case "does_not_equal":
      case "regex":
      case "starts_with":
      case "ends_with":
        return {
          kind: "scalar",
          operator: OPERATOR_LABELS[value.operator].toLowerCase(),
          value: `"${value.text}"`,
        };
    }
  }
  if (
    value.type === "date" ||
    value.type === "datetime" ||
    value.type === "time"
  ) {
    const format =
      value.type === "date"
        ? dateToLocalISODate
        : value.type === "time"
          ? dateToLocalISOTime
          : (d: Date) => exactDateTime(d, ctx.timezone, ctx.locale);
    switch (value.operator) {
      case "between":
        return {
          kind: "scalar",
          operator: OPERATOR_LABELS.between.toLowerCase(),
          value: `${format(value.min)} - ${format(value.max)}`,
        };
      case "==":
      case "!=":
      case ">":
      case ">=":
      case "<":
      case "<=":
        return {
          kind: "scalar",
          operator: value.operator,
          value: format(value.value),
        };
    }
  }
  if (value.type === "boolean") {
    switch (value.operator) {
      case "is_true":
        return { kind: "scalar", operator: "is True" };
      case "is_false":
        return { kind: "scalar", operator: "is False" };
    }
  }
  logNever(value);
  return undefined;
}
