/* Copyright 2023 Marimo. All rights reserved. */
import { Mark, SelectionType, VegaLiteSpec, VegaLiteUnitedSpec } from "./types";
import { findEncodedFields, makeEncodingInteractive } from "./encodings";
import { Params } from "./params";
import { Marks } from "./marks";

export function makeSelectable(
  spec: VegaLiteSpec,
  opts: {
    chartSelection?: boolean | "interval" | "point";
    fieldSelection?: boolean | string[];
  }
): VegaLiteSpec {
  if (!("mark" in spec)) {
    return spec;
  }

  // Both default to true
  const { chartSelection = true, fieldSelection = true } = opts;

  // Disable selection if both are false
  if (!chartSelection && !fieldSelection) {
    return spec;
  }

  let resolvedSpec = spec;
  resolvedSpec = makeLegendSelectable(resolvedSpec, fieldSelection);
  resolvedSpec = makeChartSelectable(resolvedSpec, chartSelection);
  resolvedSpec = makeChartInteractive(resolvedSpec);

  return resolvedSpec;
}

/**
 * Given a spec, add the necessary parameters to make the legend selectable.
 */
function makeLegendSelectable(
  spec: VegaLiteUnitedSpec,
  fieldSelection: boolean | string[]
): VegaLiteUnitedSpec {
  // If fieldSelection is false, we don't do anything
  if (fieldSelection === false) {
    return spec;
  }

  let legendFields = findEncodedFields(spec);
  // If fieldSelection is an array, we filter the fields
  if (Array.isArray(fieldSelection)) {
    legendFields = legendFields.filter((field) =>
      fieldSelection.includes(field)
    );
  }

  const legendParams = legendFields.map((field) => Params.legend(field));
  const nextParams = [...(spec.params || []), ...legendParams];

  return {
    ...spec,
    params: nextParams,
  } as VegaLiteUnitedSpec;
}

/**
 * Given a spec, add the necessary parameters to make the chart selectable.
 */
function makeChartSelectable(
  spec: VegaLiteUnitedSpec,
  chartSelection: boolean | "interval" | "point"
): VegaLiteUnitedSpec {
  // If chartSelection is false, we don't do anything
  if (chartSelection === false) {
    return spec;
  }

  const mark = Marks.getMarkType(spec.mark);
  const resolvedChartSelection =
    chartSelection === true ? getBestSelectionForMark(mark) : chartSelection;

  if (!resolvedChartSelection) {
    return spec;
  }

  const params =
    resolvedChartSelection === "interval"
      ? [Params.interval(mark)]
      : [Params.point(mark)];

  const nextParams = [...(spec.params || []), ...params];

  return {
    ...spec,
    params: nextParams,
  } as VegaLiteUnitedSpec;
}

function makeChartInteractive(spec: VegaLiteUnitedSpec): VegaLiteUnitedSpec {
  const prevEncodings = "encoding" in spec ? spec.encoding : undefined;
  const params = spec.params || [];
  const paramNames = params.map((param) => param.name);

  if (params.length === 0) {
    return spec;
  }

  return {
    ...spec,
    mark: Marks.makeClickable(spec.mark),
    encoding: makeEncodingInteractive("color", prevEncodings || {}, paramNames),
  } as VegaLiteUnitedSpec;
}

function getBestSelectionForMark(mark: Mark): SelectionType | undefined {
  switch (mark) {
    case "text":
    case "arc":
    case "area":
      return "point";
    // there is no best selection for line
    case "line":
      return undefined;
    default:
      return "interval";
  }
}
