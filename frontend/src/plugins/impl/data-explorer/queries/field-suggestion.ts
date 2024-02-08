/* Copyright 2024 Marimo. All rights reserved. */
import { FieldQuery } from "compassql/build/src/query/encoding";
import { Query } from "compassql/build/src/query/query";
import { SHORT_WILDCARD } from "compassql/build/src/wildcard";
import { QueryCreator, ResultingCharts } from "./types";

// This code is adapted and simplified from https://github.com/vega/voyager

function makeFieldSuggestionQueryCreator(params: {
  type: keyof ResultingCharts;
  limit: number;
  additionalFieldQuery: FieldQuery;
}): QueryCreator {
  const { type, limit, additionalFieldQuery } = params;
  return {
    type,
    limit: limit,
    createQuery(query: Query): Query {
      return {
        spec: {
          ...query.spec,
          encodings: [...query.spec.encodings, additionalFieldQuery],
        },
        groupBy: "field",
        orderBy: ["fieldOrder", "aggregationQuality", "effectiveness"],
        chooseBy: ["aggregationQuality", "effectiveness"],
        config: { autoAddCount: true },
      };
    },
  };
}

export const addCategoricalField = makeFieldSuggestionQueryCreator({
  type: "addCategoricalField",
  limit: 4,
  additionalFieldQuery: {
    channel: SHORT_WILDCARD,
    field: SHORT_WILDCARD,
    type: "nominal",
  },
});

export const addQuantitativeField = makeFieldSuggestionQueryCreator({
  type: "addQuantitativeField",
  limit: 4,
  additionalFieldQuery: {
    channel: SHORT_WILDCARD,
    bin: SHORT_WILDCARD,
    aggregate: SHORT_WILDCARD,
    field: SHORT_WILDCARD,
    type: "quantitative",
  },
});

export const addTemporalField = makeFieldSuggestionQueryCreator({
  type: "addTemporalField",
  limit: 2,
  additionalFieldQuery: {
    channel: SHORT_WILDCARD,
    hasFn: true, // Do not show raw time in the summary
    timeUnit: SHORT_WILDCARD,
    field: SHORT_WILDCARD,
    type: "temporal",
  },
});
