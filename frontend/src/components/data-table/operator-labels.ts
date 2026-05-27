/* Copyright 2026 Marimo. All rights reserved. */
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";

export const OPERATOR_LABELS: Record<OperatorType | "between", string> = {
  "==": "Equals",
  "!=": "Doesn't equal",
  ">": "Greater than",
  ">=": "Greater than or equal",
  "<": "Less than",
  "<=": "Less than or equal",
  between: "Between",
  contains: "Contains",
  equals: "Equals",
  does_not_equal: "Doesn't equal",
  starts_with: "Starts with",
  ends_with: "Ends with",
  regex: "Matches regex",
  in: "Is in",
  not_in: "Not in",
  is_empty: "Is empty",
  is_true: "Is true",
  is_false: "Is false",
  is_null: "Is null",
  is_not_null: "Is not null",
};
