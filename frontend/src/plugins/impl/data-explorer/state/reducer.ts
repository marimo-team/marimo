/* Copyright 2024 Marimo. All rights reserved. */
import { SpecificEncoding } from "../encoding";
import { createReducer } from "@/utils/createReducer";
import { ChartSpec } from "./types";
import { SHORT_WILDCARD } from "compassql/build/src/wildcard";
import { atom, useSetAtom } from "jotai";
import { useMemo } from "react";
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

const { reducer, createActions } = createReducer(initialState, {
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
});

export const chartSpecAtom = atom<ChartSpec>(initialState());

export function useChartSpecActions(onChange?: (spec: ChartSpec) => void) {
  const setState = useSetAtom(chartSpecAtom);

  return useMemo(() => {
    const actions = createActions((action) => {
      setState((state) => {
        const newState = reducer(state, action);
        onChange?.(newState);
        return newState;
      });
    });
    return actions;
  }, [setState, onChange]);
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
