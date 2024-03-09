/* Copyright 2024 Marimo. All rights reserved. */
import {
  GenericVegaSpec,
  Mark,
  SelectionType,
  VegaLiteSpec,
  VegaLiteUnitSpec,
} from "./types";
import { findEncodedFields, makeEncodingInteractive } from "./encodings";
import { Params } from "./params";
import { Marks } from "./marks";

export function makeSelectable<T extends VegaLiteSpec>(
  spec: T,
  opts: {
    chartSelection?: boolean | "interval" | "point";
    fieldSelection?: boolean | string[];
  },
): T {
  // Both default to true
  const { chartSelection = true, fieldSelection = true } = opts;

  // Disable selection if both are false
  if (!chartSelection && !fieldSelection) {
    return spec;
  }

  if ("vconcat" in spec) {
    const subSpecs = spec.vconcat.map((subSpec) =>
      "mark" in subSpec ? makeChartInteractive(subSpec) : subSpec,
    );
    return { ...spec, vconcat: subSpecs };
  }

  if ("hconcat" in spec) {
    const subSpecs = spec.hconcat.map((subSpec) =>
      "mark" in subSpec ? makeChartInteractive(subSpec) : subSpec,
    );
    return { ...spec, hconcat: subSpecs };
  }

  if ("layer" in spec) {
    const subSpecs = spec.layer.map((subSpec, idx) => {
      if (!("mark" in subSpec)) {
        return subSpec;
      }
      let resolvedSpec = subSpec as VegaLiteUnitSpec;
      resolvedSpec = makeChartSelectable(resolvedSpec, chartSelection, idx);
      resolvedSpec = makeChartInteractive(resolvedSpec);
      return resolvedSpec;
    });
    return { ...spec, layer: subSpecs };
  }

  if (!("mark" in spec)) {
    return spec;
  }

  let resolvedSpec: VegaLiteUnitSpec = spec;
  resolvedSpec = makeLegendSelectable(resolvedSpec, fieldSelection);
  resolvedSpec = makeChartSelectable(resolvedSpec, chartSelection, undefined);
  resolvedSpec = makeChartInteractive(resolvedSpec);

  return resolvedSpec as T;
}

/**
 * Given a spec, add the necessary parameters to make the legend selectable.
 */
function makeLegendSelectable(
  spec: VegaLiteUnitSpec,
  fieldSelection: boolean | string[],
): VegaLiteUnitSpec {
  // If fieldSelection is false, we don't do anything
  if (fieldSelection === false) {
    return spec;
  }

  let legendFields = findEncodedFields(spec);
  // If fieldSelection is an array, we filter the fields
  if (Array.isArray(fieldSelection)) {
    legendFields = legendFields.filter((field) =>
      fieldSelection.includes(field),
    );
  }

  const legendParams = legendFields.map((field) => Params.legend(field));
  const nextParams = [...(spec.params || []), ...legendParams];

  return {
    ...spec,
    params: nextParams,
  } as VegaLiteUnitSpec;
}

/**
 * Given a spec, add the necessary parameters to make the chart selectable.
 */
function makeChartSelectable(
  spec: VegaLiteUnitSpec,
  chartSelection: boolean | "interval" | "point",
  /**
   * If the spec is part of a layer, we need to know the layer number.
   * This is so we can give unique names to the parameters.
   */
  layerNum: number | undefined,
): VegaLiteUnitSpec {
  // If chartSelection is false, we don't do anything
  if (chartSelection === false) {
    return spec;
  }

  let mark: Mark;
  try {
    mark = Marks.getMarkType(spec.mark);
  } catch {
    return spec;
  }

  // We don't do anything if the mark is text
  if (mark === "text") {
    return spec;
  }

  const resolvedChartSelection =
    chartSelection === true ? getBestSelectionForMark(mark) : [chartSelection];

  if (!resolvedChartSelection) {
    return spec;
  }

  const params = resolvedChartSelection.map((selectionType) =>
    selectionType === "interval"
      ? Params.interval(spec, layerNum)
      : Params.point(spec, layerNum),
  );

  const nextParams = [...(spec.params || []), ...params];

  return {
    ...spec,
    params: nextParams,
  } as VegaLiteUnitSpec;
}

/**
 * Makes a chart clickable and adds an opacity encoding to the chart.
 */
function makeChartInteractive<T extends GenericVegaSpec>(spec: T): T {
  const prevEncodings = "encoding" in spec ? spec.encoding : undefined;
  const params = spec.params || [];
  const paramNames = params.map((param) => param.name);

  if (params.length === 0) {
    return spec;
  }

  const mark = Marks.getMarkType(spec.mark);
  // We don't do anything if the mark is text
  if (mark === "text") {
    return spec;
  }

  return {
    ...spec,
    mark: Marks.makeClickable(spec.mark),
    encoding: makeEncodingInteractive(
      "opacity",
      prevEncodings || {},
      paramNames,
      spec.mark,
    ),
  };
}

function getBestSelectionForMark(mark: Mark): SelectionType[] | undefined {
  switch (mark) {
    case "text":
    case "arc":
    case "area":
      return ["point"];
    case "bar":
      return ["point", "interval"];
    // there is no best selection for line
    case "line":
      return undefined;
    default:
      return ["point", "interval"];
  }
}
