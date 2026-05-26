/* Copyright 2026 Marimo. All rights reserved. */

import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import type { FilterType } from "./types";

// Primitive operator groups — each describes one shape of filter value.
export const NULLISH_OPS = ["is_null", "is_not_null"] as const;
export const MEMBERSHIP_OPS = ["in", "not_in"] as const;
export const COMPARISON_OPS = ["==", "!=", ">", ">=", "<", "<="] as const;
export const TEXT_SCALAR_OPS = [
  "contains",
  "equals",
  "does_not_equal",
  "regex",
  "starts_with",
  "ends_with",
] as const;
export const BOOLEAN_VALUE_OPS = ["is_true", "is_false"] as const;
export const EMPTY_OPS = ["is_empty"] as const;

// Operators that carry no payload — `{ operator }` with no other field.
export const UNARY_OPS = [
  ...NULLISH_OPS,
  ...BOOLEAN_VALUE_OPS,
  ...EMPTY_OPS,
] as const;

// Per-type op lists used by the editor and validators.
export const BOOLEAN_OPS = [...BOOLEAN_VALUE_OPS, ...NULLISH_OPS] as const;
export const NUMBER_OPS = [
  "between",
  ...COMPARISON_OPS,
  ...MEMBERSHIP_OPS,
  ...NULLISH_OPS,
] as const;
export const TEXT_OPS = [
  ...TEXT_SCALAR_OPS,
  ...MEMBERSHIP_OPS,
  ...EMPTY_OPS,
  ...NULLISH_OPS,
] as const;
export const DATETIME_OPS = [
  "between",
  ...COMPARISON_OPS,
  ...NULLISH_OPS,
] as const;

export type NullishOp = (typeof NULLISH_OPS)[number];
export type MembershipOp = (typeof MEMBERSHIP_OPS)[number];
export type ComparisonOp = (typeof COMPARISON_OPS)[number];
export type TextScalarOp = (typeof TEXT_SCALAR_OPS)[number];
export type BooleanValueOp = (typeof BOOLEAN_VALUE_OPS)[number];
export type BooleanOp = (typeof BOOLEAN_OPS)[number];

export const OPERATORS_BY_TYPE: Record<
  FilterType,
  ReadonlyArray<OperatorType>
> = {
  number: NUMBER_OPS,
  text: TEXT_OPS,
  boolean: BOOLEAN_OPS,
  date: DATETIME_OPS,
  datetime: DATETIME_OPS,
  time: DATETIME_OPS,
};

export const DEFAULT_OPERATOR_FOR_TYPE: Record<FilterType, OperatorType> = {
  number: "between",
  text: "contains",
  boolean: "is_true",
  date: "==",
  datetime: "==",
  time: "between",
};

export const OPERATORS_WITHOUT_VALUE = new Set<OperatorType>(UNARY_OPS);
