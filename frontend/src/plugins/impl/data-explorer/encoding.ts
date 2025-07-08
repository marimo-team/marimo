/* Copyright 2024 Marimo. All rights reserved. */
import type { FieldQuery } from "compassql/build/src/query/encoding";
import type { ExpandedType } from "compassql/build/src/query/expandedtype";
import {
  isWildcard,
  type SHORT_WILDCARD,
  type WildcardProperty,
} from "compassql/build/src/wildcard";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import {
  fromFieldQueryFunctionMixins,
  toFieldQueryFunctionMixins,
} from "./functions/function";
import type { FieldFunction } from "./functions/types";
import { removeUndefined } from "./queries/removeUndefined";

// This code is adapted and simplified from https://github.com/vega/voyager

/**
 * Subset of encodings that we support
 */
export type EncodingChannel =
  | "x"
  | "y"
  | "shape"
  | "color"
  | "fill"
  | "stroke"
  | "opacity"
  | "size"
  | "row"
  | "column";

/**
 * Definition for a field encoding
 */
export interface FieldDefinition {
  field: WildcardProperty<string>;

  fn?: FieldFunction | undefined;

  scale?: FieldQuery["scale"];
  axis?: FieldQuery["axis"];
  legend?: FieldQuery["legend"];

  // Unused, maybe later
  // sort?: SortOrder | SortField<string>;
  // stack?: StackOffset;

  type?: ExpandedType;
  description?: string;
}

export type SpecificEncoding = Partial<
  Record<EncodingChannel, FieldDefinition | undefined>
>;

export function toFieldQuery(
  fieldDef: FieldDefinition,
  channel: EncodingChannel | SHORT_WILDCARD,
): FieldQuery {
  const { fn, ...rest } = fieldDef;

  return {
    channel,
    ...toFieldQueryFunctionMixins(fn),
    ...rest,
  };
}

export function fromFieldQuery(fieldQ: FieldQuery): FieldDefinition {
  const {
    aggregate,
    bin,
    timeUnit,
    field,
    scale,
    legend,
    axis,
    sort,
    description,
  } = fieldQ;
  let { type } = fieldQ;

  if (isWildcard(type)) {
    throw new Error("Wildcard not support");
  }
  if (type === "ordinal") {
    Logger.warn("Ordinal type is not supported. Using nominal type instead.");
    type = "nominal";
  }

  const fn = fromFieldQueryFunctionMixins({ aggregate, bin, timeUnit });
  invariant(field !== undefined, "Field is required for fieldQ");

  return removeUndefined({
    field,
    fn,
    type: type,
    sort,
    scale,
    axis,
    legend,
    description,
  });
}
