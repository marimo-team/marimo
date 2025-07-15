/* Copyright 2024 Marimo. All rights reserved. */
import type { Query } from "compassql/build/src/query";
import type { VisualizationSpec } from "react-vega";
import type { NamedData } from "vega-lite/types_unstable/data.js";
import type { TopLevel } from "vega-lite/types_unstable/spec/toplevel.js";
import type { FacetedUnitSpec } from "vega-lite/types_unstable/spec/unit.js";
import type { EncodingChannel, FieldDefinition } from "../encoding";

export interface PlotFieldInfo {
  fieldDef: FieldDefinition;
  channel: EncodingChannel;
}

export interface ResultPlot {
  fieldInfos: PlotFieldInfo[];

  /**
   * Spec to be used for rendering.
   */
  spec: VisualizationSpec;
}

export interface Result {
  plots: ResultPlot[] | null;

  query: Query;

  limit: number;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any, @typescript-eslint/no-redundant-type-constituents
export type TopLevelFacetedUnitSpec = TopLevel<FacetedUnitSpec<any, any>> & {
  data: NamedData;
};

export interface ResultingCharts {
  main: Result;

  histograms: Result;

  addCategoricalField: Result;
  addQuantitativeField: Result;
  addTemporalField: Result;

  alternativeEncodings: Result;
  summaries: Result;
}

export interface QueryCreator {
  type: keyof ResultingCharts;

  limit: number;

  createQuery(query: Query): Query;
}
