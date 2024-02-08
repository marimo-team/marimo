/* Copyright 2024 Marimo. All rights reserved. */
import { EncodingQuery } from "compassql/build/src/query/encoding";
import { SpecQuery } from "compassql/build/src/query/spec";
import { SpecificEncoding, toFieldQuery, EncodingChannel } from "./encoding";
import { ChartSpec } from "./state/types";

export function toSpecQuery(spec: ChartSpec): SpecQuery {
  return {
    mark: spec.mark,
    encodings: adaptEncodings(spec.encoding),
    config: spec.config,
  };
}

function adaptEncodings(encoding: SpecificEncoding): EncodingQuery[] {
  return Object.entries(encoding).map(([channel, def]) => {
    return toFieldQuery(def, channel as EncodingChannel);
  });
}
