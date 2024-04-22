/* Copyright 2024 Marimo. All rights reserved. */
import { SpecificEncoding } from "../encoding";
import { createReducerAndAtoms } from "@/utils/createReducer";
import { ChartSpec } from "./types";
import { SHORT_WILDCARD } from "compassql/build/src/wildcard";
import { atom } from "jotai";
import {
  mainViewResult,
  allRelatedViewResults,
  relatedViewResult,
  toQuery,
} from "../queries/queries";
import {
  isQueryEmpty,
  isQueryFull,
  isQuerySpecific,
  removeUndefined,
} from "../queries/utils";
import { histograms } from "../queries/histograms";
import { Schema } from "compassql/build/src/schema";
import { SpecMark } from "../marks";
import { ResultingCharts } from "../queries/types";

function initialState(): ChartSpec {
  return {
    mark: SHORT_WILDCARD,
    encoding: {},
    config: {},
    schema: null,
  };
}

const { valueAtom: chartSpecAtom, useActions } = createReducerAndAtoms(
  initialState,
  {
    setSchema: (state, schema: Schema) => {
      return { ...state, schema };
    },
    setMark: (state, mark: SpecMark) => {
      return { ...state, mark };
    },
    setEncoding: (state, encoding: SpecificEncoding) => {
      // Merge and remove undefined values
      const nextEncoding = removeUndefined({
        ...state.encoding,
        ...encoding,
      });

      return { ...state, encoding: nextEncoding };
    },
    set: (state, next: ChartSpec) => {
      // remove schema
      const { schema, ...rest } = next;
      return { ...state, ...rest };
    },
  },
);

export { chartSpecAtom };

export function useChartSpecActions() {
  return useActions();
}

export const relatedChartSpecsAtom = atom<Partial<ResultingCharts>>((get) => {
  const spec = get(chartSpecAtom);

  // No schema
  if (!spec.schema) {
    return {};
  }

  const query = toQuery({ spec, autoAddCount: true });

  // If the query is empty, we can show the main view and histograms
  if (isQueryEmpty(query.spec)) {
    return {
      main: mainViewResult(query, spec.schema),
      histograms: relatedViewResult(histograms, query, spec.schema),
    };
  }

  // If the query is specific, we can show the main view and related views
  if (isQuerySpecific(query.spec) && !isQueryFull(query.spec)) {
    return {
      main: mainViewResult(query, spec.schema),
      ...allRelatedViewResults(query, spec.schema),
    };
  }

  // Otherwise, we can only show the main view
  return {
    main: mainViewResult(query, spec.schema),
  };
});
