/* Copyright 2024 Marimo. All rights reserved. */
import { Query } from "compassql/build/src/query";
import { SpecQuery } from "compassql/build/src/query/spec";
import { contains } from "vega-lite";
import { NONPOSITION_SCALE_CHANNELS } from "vega-lite/build/src/channel";
import {
  addQuantitativeField,
  addCategoricalField,
  addTemporalField,
} from "./field-suggestion";
import { recommend } from "compassql/build/src";
import { Schema } from "compassql/build/src/schema";
import { SpecQueryModelGroup, SpecQueryModel } from "compassql/build/src/model";
import { isResultTree, getTopResultTreeItem } from "compassql/build/src/result";
import { NamedData } from "vega-lite/build/src/data";
import { isFieldQuery } from "compassql/build/src/query/encoding";
import { EncodingChannel, fromFieldQuery } from "../encoding";
import { ChartSpec } from "../state/types";
import { hasWildcards, isQueryEmpty } from "./utils";
import { toSpecQuery } from "../spec";
import {
  Result,
  QueryCreator,
  ResultPlot,
  PlotFieldInfo,
  ResultingCharts,
  TopLevelFacetedUnitSpec,
} from "./types";

// This code is adapted and simplified from https://github.com/vega/voyager

const NAMED_DATA: NamedData = { name: "source" };

function getFeaturesForRelatedViewRules(spec: SpecQuery) {
  let hasOpenPosition = false;
  let hasStyleChannel = false;
  let hasOpenFacet = false;

  spec.encodings.forEach((encQ) => {
    if (encQ.channel === "x" || encQ.channel === "y") {
      hasOpenPosition = true;
    } else if (encQ.channel === "row" || encQ.channel === "column") {
      hasOpenFacet = true;
    } else if (
      typeof encQ.channel === "string" &&
      contains<string>(NONPOSITION_SCALE_CHANNELS, encQ.channel)
    ) {
      hasStyleChannel = true;
    }
  });

  return {
    hasOpenPosition,
    hasStyleChannel,
    hasOpenFacet,
  };
}

export function allRelatedViewResults(
  query: Query,
  schema: Schema,
): Partial<ResultingCharts> {
  const charts: Partial<ResultingCharts> = {};

  const { hasOpenPosition, hasStyleChannel, hasOpenFacet } =
    getFeaturesForRelatedViewRules(query.spec);

  if (hasOpenPosition || hasStyleChannel) {
    charts.addQuantitativeField = relatedViewResult(
      addQuantitativeField,
      query,
      schema,
    );
  }

  if (hasOpenPosition || hasStyleChannel || hasOpenFacet) {
    charts.addCategoricalField = relatedViewResult(
      addCategoricalField,
      query,
      schema,
    );
  }

  if (hasOpenPosition) {
    charts.addTemporalField = relatedViewResult(
      addTemporalField,
      query,
      schema,
    );
  }

  // Hidden for now
  // charts.alternativeEncodings = relatedViewResult(
  //   alternativeEncodings,
  //   query,
  //   schema
  // );
  return charts;
}

export function mainViewResult(
  mainQuery: Query,
  schema: Schema,
): Result | undefined {
  if (isQueryEmpty(mainQuery.spec)) {
    return {
      plots: [],
      query: mainQuery,
      limit: 1,
    };
  }

  const modelGroup = recommend(mainQuery, schema).result;
  const plots = fromSpecQueryModelGroup(modelGroup, NAMED_DATA);

  return {
    plots: [plots[0]],
    query: mainQuery,
    limit: 1,
  };
}

export function relatedViewResult(
  queryCreator: QueryCreator,
  mainQuery: Query,
  schema: Schema,
): Result {
  const query = queryCreator.createQuery(mainQuery);

  const modelGroup = recommend(query, schema).result;
  const plots = fromSpecQueryModelGroup(modelGroup, NAMED_DATA);

  return {
    plots,
    query,
    limit: queryCreator.limit,
  };
}

function fromSpecQueryModelGroup(
  modelGroup: SpecQueryModelGroup,
  data: NamedData,
): ResultPlot[] {
  return modelGroup.items.map((item) => {
    if (isResultTree<SpecQueryModel>(item)) {
      return toPlot(data, getTopResultTreeItem(item));
    }
    return toPlot(data, item);
  });
}

function toPlot(data: NamedData, specQ: SpecQueryModel): ResultPlot {
  const fieldInfos = specQ
    .getEncodings()
    .filter(isFieldQuery)
    .map((fieldQ): PlotFieldInfo => {
      return {
        fieldDef: fromFieldQuery(fieldQ),
        channel: fieldQ.channel as EncodingChannel,
      };
    });

  return {
    fieldInfos,
    spec: specQ.toSpec(data) as TopLevelFacetedUnitSpec,
  };
}

export function toQuery(params: {
  spec: ChartSpec;
  autoAddCount: boolean;
}): Query {
  const { spec, autoAddCount } = params;
  const specQ = toSpecQuery(spec);
  const { hasAnyWildcard, hasWildcardFn, hasWildcardField } =
    hasWildcards(specQ);

  const groupBy = getDefaultGroupBy({ hasWildcardFn, hasWildcardField });

  return {
    spec: specQ,
    groupBy,
    orderBy: ["fieldOrder", "aggregationQuality", "effectiveness"],
    chooseBy: ["aggregationQuality", "effectiveness"],
    config: hasAnyWildcard ? { autoAddCount } : undefined,
  };
}

function getDefaultGroupBy(args: {
  hasWildcardField: boolean;
  hasWildcardFn: boolean;
}) {
  const { hasWildcardFn, hasWildcardField } = args;

  return hasWildcardFn
    ? "fieldTransform"
    : hasWildcardField
      ? "field"
      : "encoding";
}
