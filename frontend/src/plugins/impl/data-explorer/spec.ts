/* Copyright 2024 Marimo. All rights reserved. */
import type { EncodingQuery } from "compassql/build/src/query/encoding";
import type { SpecQuery } from "compassql/build/src/query/spec";
import {
  type SpecificEncoding,
  toFieldQuery,
  type EncodingChannel,
} from "./encoding";
import type { ChartSpec } from "./state/types";

export function toSpecQuery(spec: ChartSpec): SpecQuery {
  return {
    mark: spec.mark,
    encodings: adaptEncodings(spec.encoding),
    config: spec.config,
  };
}

function adaptEncodings(
  encoding: SpecificEncoding | undefined,
): EncodingQuery[] {
  if (!encoding) {
    return [];
  }
  return Object.entries(encoding).map(([channel, def]) => {
    return toFieldQuery(def, channel as EncodingChannel);
  });
}
