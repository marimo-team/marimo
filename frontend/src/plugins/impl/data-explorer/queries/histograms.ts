/* Copyright 2024 Marimo. All rights reserved. */
import { Query } from "compassql/build/src/query/query";
import { SHORT_WILDCARD } from "compassql/build/src/wildcard";
import { QueryCreator } from "./types";

// This code is adapted and simplified from https://github.com/vega/voyager

export const histograms: QueryCreator = {
  type: "histograms",
  limit: 12,
  createQuery(query: Query): Query {
    return {
      spec: {
        data: query.spec.data,
        mark: SHORT_WILDCARD,
        transform: query.spec.transform,
        encodings: [
          {
            channel: SHORT_WILDCARD,
            bin: SHORT_WILDCARD,
            timeUnit: SHORT_WILDCARD,
            field: SHORT_WILDCARD,
            type: SHORT_WILDCARD,
          },
          {
            channel: SHORT_WILDCARD,
            aggregate: "count",
            field: "*",
            type: "quantitative",
          },
        ],
      },
      groupBy: "fieldTransform",
      orderBy: ["fieldOrder", "aggregationQuality", "effectiveness"],
      chooseBy: ["aggregationQuality", "effectiveness"],
      config: {
        autoAddCount: false,
      },
    };
  },
};
