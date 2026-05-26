/* Copyright 2026 Marimo. All rights reserved. */

import type {
  BooleanOp,
  ComparisonOp,
  MembershipOp,
  NullishOp,
  TextScalarOp,
} from "./operators";
import type { FilterType } from "./types";

interface NullishOpts {
  operator: NullishOp;
}

interface MembershipOpts {
  operator: MembershipOp;
  values: unknown[];
}

interface BetweenRangeOpts<T> {
  operator: "between";
  min: T;
  max: T;
}

type NumberFilterOpts =
  | { operator: ComparisonOp; value: number }
  | BetweenRangeOpts<number>
  | MembershipOpts
  | NullishOpts;

type TextFilterOpts =
  | { operator: TextScalarOp; text: string }
  | { operator: "is_empty" }
  | MembershipOpts
  | NullishOpts;

type DateLikeFilterOpts =
  | { operator: ComparisonOp; value: Date }
  | BetweenRangeOpts<Date>
  | NullishOpts;

interface BooleanFilterOpts {
  operator: BooleanOp;
}

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
  boolean(opts: BooleanFilterOpts) {
    return {
      type: "boolean",
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
export type MembershipFilterType = Extract<
  ColumnFilterValue,
  { operator: "in" | "not_in" }
>["type"];

export interface Snapshot {
  columnId: string;
  value: ColumnFilterValue;
}
