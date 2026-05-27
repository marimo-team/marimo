/* Copyright 2026 Marimo. All rights reserved. */

import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import type { ColumnFilterValue, MembershipFilterType } from "./builders";
import {
  COMPARISON_OPS,
  type MembershipOp,
  type NullishOp,
  OPERATORS_BY_TYPE,
  TEXT_SCALAR_OPS,
} from "./operators";
import type { FilterType } from "./types";

const makeOpGuard = <T extends OperatorType>(ops: readonly T[]) => {
  const set = new Set<OperatorType>(ops);
  return (op: OperatorType): op is T => set.has(op);
};

export const isComparisonOp = makeOpGuard(COMPARISON_OPS);
export const isTextScalarOp = makeOpGuard(TEXT_SCALAR_OPS);

export function isMembershipOp(op: OperatorType): op is MembershipOp {
  return op === "in" || op === "not_in";
}

export function isNullishFilter(
  filter: ColumnFilterValue,
): filter is Extract<ColumnFilterValue, { operator: NullishOp }> {
  return filter.operator === "is_null" || filter.operator === "is_not_null";
}

export type DateLikeFilterType = Extract<
  FilterType,
  "date" | "datetime" | "time"
>;

const DATE_LIKE_TYPES: ReadonlySet<FilterType> = new Set([
  "date",
  "datetime",
  "time",
]);

export const isDateLikeType = (type: FilterType): type is DateLikeFilterType =>
  DATE_LIKE_TYPES.has(type);

export function isMembershipFilterType(
  type: FilterType,
): type is MembershipFilterType {
  const ops = OPERATORS_BY_TYPE[type];
  return ops.includes("in") || ops.includes("not_in");
}
