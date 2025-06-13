/* Copyright 2024 Marimo. All rights reserved. */
import {
  isAutoCountQuery,
  isValueQuery,
} from "compassql/build/src/query/encoding";
import type { SpecQuery } from "compassql/build/src/query/spec";
import { isWildcard } from "compassql/build/src/wildcard";
import type { EncodingChannel } from "../encoding";

// This code is adapted and simplified from https://github.com/vega/voyager

export function isQuerySpecific(spec: SpecQuery) {
  return !hasWildcards(spec).hasAnyWildcard;
}

/**
 * A query is full if it has "x", "y", and "color" channels
 * and a facet
 */
export function isQueryFull(spec: SpecQuery) {
  // Must have all these
  const encodings: EncodingChannel[] = ["x", "y", "color"];
  // Must have one of these
  const facets: EncodingChannel[] = ["row", "column"];

  const listedEncodings = new Set(spec.encodings.map((encQ) => encQ.channel));
  const hasAllChannels = encodings.every((channel) =>
    listedEncodings.has(channel),
  );
  const hasFacet = facets.some((facet) => listedEncodings.has(facet));

  return hasAllChannels && hasFacet;
}

export function isQueryEmpty(spec: SpecQuery) {
  return spec.encodings.length === 0;
}

interface HasWildcard {
  hasAnyWildcard: boolean;
  hasWildcardField: boolean;
  hasWildcardFn: boolean;
  hasWildcardChannel: boolean;
}

export function hasWildcards(spec: SpecQuery): HasWildcard {
  let hasWildcardField = false;
  let hasWildcardFn = false;
  let hasWildcardChannel = false;

  for (const encQ of spec.encodings) {
    if (isValueQuery(encQ)) {
      continue;
    }

    if (isAutoCountQuery(encQ)) {
      if (isWildcard(encQ.autoCount)) {
        hasWildcardFn = true;
      }
    } else {
      // encQ is FieldQuery
      if (isWildcard(encQ.field)) {
        hasWildcardField = true;
      }

      if (
        isWildcard(encQ.aggregate) ||
        isWildcard(encQ.bin) ||
        isWildcard(encQ.timeUnit)
      ) {
        hasWildcardFn = true;
      }

      if (isWildcard(encQ.channel)) {
        hasWildcardChannel = true;
      }
    }
  }
  return {
    hasAnyWildcard: hasWildcardChannel || hasWildcardField || hasWildcardFn,
    hasWildcardField,
    hasWildcardFn,
    hasWildcardChannel,
  };
}
