/* Copyright 2024 Marimo. All rights reserved. */

import { findEncodedFields, makeEncodingInteractive } from "./encodings";
import { Marks } from "./marks";
import { getBinnedFields, Params } from "./params";
import type {
  GenericVegaSpec,
  Mark,
  SelectionType,
  VegaLiteSpec,
  VegaLiteUnitSpec,
} from "./types";

export function makeSelectable<T extends VegaLiteSpec>(
  spec: T,
  opts: {
    chartSelection?: boolean | "interval" | "point";
    fieldSelection?: boolean | string[];
  },
): T {
  // Both default to true
  let { chartSelection = true, fieldSelection = true } = opts;

  // Disable selection if both are false
  if (!chartSelection && !fieldSelection) {
    return spec;
  }

  // If params already exist, we don't add any more
  const hasLegendParam = spec.params?.some((param) => param.bind === "legend");
  if (hasLegendParam) {
    fieldSelection = false;
  }
  const hasChartParam = spec.params?.some((param) => !param.bind);
  if (hasChartParam) {
    chartSelection = false;
  }

  if ("vconcat" in spec) {
    const subSpecs = spec.vconcat.map((subSpec) =>
      "mark" in subSpec
        ? makeSelectable(subSpec as VegaLiteUnitSpec, {
            chartSelection,
            fieldSelection,
          })
        : subSpec,
    );
    // No pan/zoom for vconcat
    return { ...spec, vconcat: subSpecs };
  }

  if ("hconcat" in spec) {
    const subSpecs = spec.hconcat.map((subSpec) =>
      "mark" in subSpec
        ? makeSelectable(subSpec as VegaLiteUnitSpec, {
            chartSelection,
            fieldSelection,
          })
        : subSpec,
    );
    // No pan/zoom for hconcat
    return { ...spec, hconcat: subSpecs };
  }

  if ("layer" in spec) {
    // Check if legend params already exist at the top level
    const hasTopLevelLegendParam = spec.params?.some(
      (param) => param.bind === "legend",
    );
    const shouldAddLegendSelection =
      fieldSelection !== false && !hasTopLevelLegendParam;

    // Collect all unique legend fields from all layers to avoid duplicates
    let legendFields: string[] = [];
    if (shouldAddLegendSelection) {
      const allFields = spec.layer.flatMap((subSpec) => {
        if (!("mark" in subSpec)) {
          return [];
        }
        return findEncodedFields(subSpec as VegaLiteUnitSpec);
      });
      legendFields = [...new Set(allFields)]; // Remove duplicates

      // If fieldSelection is an array, filter the fields
      if (Array.isArray(fieldSelection)) {
        legendFields = legendFields.filter((field) =>
          fieldSelection.includes(field),
        );
      }
    }

    const subSpecs = spec.layer.map((subSpec, idx) => {
      if (!("mark" in subSpec)) {
        return subSpec;
      }
      let resolvedSpec = subSpec as VegaLiteUnitSpec;

      // Only add legend params to the first layer to avoid duplicates
      if (idx === 0 && legendFields.length > 0) {
        const legendParams = legendFields.map((field) => Params.legend(field));
        resolvedSpec = {
          ...resolvedSpec,
          params: [...(resolvedSpec.params || []), ...legendParams],
        };
      }

      resolvedSpec = makeChartSelectable(resolvedSpec, chartSelection, idx);
      resolvedSpec = makeChartInteractive(resolvedSpec);
      if (idx === 0) {
        resolvedSpec = makeChartPanZoom(resolvedSpec);
      }
      return resolvedSpec;
    });
    return { ...spec, layer: subSpecs };
  }

  if (!("mark" in spec)) {
    return spec;
  }
  // error, errorbar, boxplot are not interactive
  if (!Marks.isInteractive(spec.mark)) {
    return spec;
  }

  let resolvedSpec: VegaLiteUnitSpec = spec;
  resolvedSpec = makeLegendSelectable(resolvedSpec, fieldSelection);
  resolvedSpec = makeChartSelectable(resolvedSpec, chartSelection, undefined);
  resolvedSpec = makeChartInteractive(resolvedSpec);
  resolvedSpec = makeChartPanZoom(resolvedSpec);

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
 *
 * Not supported marks:
 * - geoshape
 * - text
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

  // We don't do anything if the mark is geoshape
  if (mark === "geoshape") {
    return spec;
  }

  const binnedFields = getBinnedFields(spec);

  // If chartSelection is true, we use the best selection for based on the spec
  // For binned charts, we use point selection
  // Otherwise, we use the best selection for the mark
  const resolvedChartSelection: SelectionType[] | undefined =
    chartSelection === true
      ? binnedFields.length > 0
        ? ["point"]
        : getBestSelectionForMark(mark)
      : [chartSelection];

  if (!resolvedChartSelection || resolvedChartSelection.length === 0) {
    return spec;
  }

  const params = resolvedChartSelection.map((selectionType) =>
    selectionType === "interval"
      ? Params.interval(spec, layerNum)
      : Params.point(spec, layerNum),
  );

  const nextParams = [...(spec.params || []), ...params];

  // For binned charts, we need TWO params:
  // 1. The regular selection param (point/interval) - sends signals to backend for filtering
  // 2. The bin_coloring param - controls opacity/coloring, NO signal listener
  // This separation allows us to filter on binned ranges while providing visual feedback
  if (binnedFields.length > 0) {
    if (resolvedChartSelection.includes("point")) {
      nextParams.push(Params.binColoring(layerNum));
    }
  }

  return {
    ...spec,
    params: nextParams,
  } as VegaLiteUnitSpec;
}

/**
 * Given a spec, add the necessary parameters to make the chart pan/zoomable.
 *
 * Not supported marks:
 * - geoshape
 */
function makeChartPanZoom(spec: VegaLiteUnitSpec): VegaLiteUnitSpec {
  let mark: Mark | undefined;
  try {
    mark = Marks.getMarkType(spec.mark);
  } catch {
    // noop
  }

  // We don't do anything if the mark is geoshape
  if (mark === "geoshape") {
    return spec;
  }

  const params = spec.params || [];

  const alreadyHasScalesParam = params.some((param) => param.bind === "scales");
  if (alreadyHasScalesParam) {
    return spec;
  }

  return {
    ...spec,
    params: [...params, Params.panZoom()],
  };
}

/**
 * Makes a chart clickable and adds an opacity encoding to the chart.
 *
 * Not supported marks:
 * - text
 */
function makeChartInteractive<T extends GenericVegaSpec>(spec: T): T {
  const prevEncodings = "encoding" in spec ? spec.encoding : undefined;
  const params = spec.params || [];
  const paramNames = params.map((param) => param.name);

  if (params.length === 0) {
    return spec;
  }

  if (!Marks.isInteractive(spec.mark)) {
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
    case "arc":
    case "area":
      return ["point"];
    case "text":
    case "bar":
      return ["point", "interval"];
    // there is no best selection for line
    case "line":
      return undefined;
    default:
      return ["point", "interval"];
  }
}
