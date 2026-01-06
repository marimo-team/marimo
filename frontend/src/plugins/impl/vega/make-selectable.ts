/* Copyright 2026 Marimo. All rights reserved. */

import type { TopLevelSpec } from "vega-lite";
import type { NonNormalizedSpec } from "vega-lite/types_unstable/spec/index.js";
import type { TopLevelParameter } from "vega-lite/types_unstable/spec/toplevel.js";

import { findEncodedFields, makeEncodingInteractive } from "./encodings";
import { Marks } from "./marks";
import { getBinnedFields, Params } from "./params";
import type {
  Field,
  GenericVegaSpec,
  LayerSpec,
  Mark,
  SelectionParameter,
  SelectionType,
  UnitSpec,
  VegaLiteSpec,
  VegaLiteUnitSpec,
} from "./types";

/**
 * Creates a unique signature for a param based on its select properties.
 * Params with the same signature are considered "common" candidates for hoisting.
 */
function getParamSignature(param: TParams): string {
  // For non-selection params, use the whole param as signature
  if (!("select" in param) || !param.select) {
    return JSON.stringify(param);
  }

  const select = param.select;

  // Handle string selections (type shortcuts)
  if (typeof select === "string") {
    return JSON.stringify({ type: select, bind: param.bind });
  }

  const signature = {
    type: select.type,
    encodings:
      "encodings" in select && select.encodings
        ? [...select.encodings].sort()
        : undefined,
    fields:
      "fields" in select && select.fields
        ? [...select.fields].sort()
        : undefined,
    bind: param.bind,
  };

  return JSON.stringify(signature);
}

/**
 * Recursively collects all params from nested specs and hoists ONLY common params to the top level.
 * Common params are those with the same select.type, select.encodings, select.fields, and bind
 * that appear in ALL unit specs.
 */
function hoistParamsAndApplyOpacity<T extends VegaLiteSpec>(spec: T): T {
  // Collect params from all unit specs
  const allUnitSpecParams = collectAllUnitSpecParams(spec);

  if (allUnitSpecParams.length === 0) {
    return spec;
  }

  // Find common params (params with same signature that appear in all unit specs)
  const commonParams = findCommonParams(allUnitSpecParams);

  if (commonParams.length === 0) {
    return spec;
  }

  // Remove only common params from nested specs
  const commonParamNames = new Set(commonParams.map((p) => p.name));
  const specWithoutCommonParams = removeSpecificParamsFromNestedSpecs(
    spec,
    commonParamNames,
  );

  // Apply opacity to all nested unit specs based on hoisted params
  const specWithOpacity = applyOpacityToNestedSpecs(
    specWithoutCommonParams,
    commonParams.map((p) => p.name),
  );

  // Add common params to top level
  return {
    ...specWithOpacity,
    params: [...(spec.params || []), ...commonParams],
  } as T;
}

type SpecWithParams =
  | TopLevelSpec
  | LayerSpec<Field>
  | UnitSpec<Field>
  | NonNormalizedSpec;

type TParams = SelectionParameter | TopLevelParameter;

/**
 * Collects params from all unit specs (not concat specs).
 * Returns array of { params } for each unit spec.
 */
function collectAllUnitSpecParams(spec: SpecWithParams): {
  params: TParams[];
}[] {
  const results: { params: TParams[] }[] = [];

  if ("vconcat" in spec && Array.isArray(spec.vconcat)) {
    for (const subSpec of spec.vconcat) {
      results.push(...collectAllUnitSpecParams(subSpec));
    }
  } else if ("hconcat" in spec && Array.isArray(spec.hconcat)) {
    for (const subSpec of spec.hconcat) {
      results.push(...collectAllUnitSpecParams(subSpec));
    }
  } else if ("layer" in spec) {
    // Don't collect from layers, as they handle their own params
    return [];
  } else if (
    "mark" in spec && // This is a unit spec
    "params" in spec &&
    spec.params &&
    spec.params.length > 0
  ) {
    results.push({ params: spec.params });
  }

  return results;
}

/**
 * Finds params that are common across all unit specs.
 * A param is common if it has the same signature and appears in all unit specs.
 */
function findCommonParams(
  allUnitSpecParams: { params: TParams[] }[],
): TParams[] {
  if (allUnitSpecParams.length === 0) {
    return [];
  }

  // Count occurrences of each param signature
  const signatureCounts = new Map<string, { count: number; param: TParams }>();
  const totalUnitSpecs = allUnitSpecParams.length;

  for (const { params } of allUnitSpecParams) {
    const seenSignatures = new Set<string>();

    for (const param of params) {
      const signature = getParamSignature(param);

      // Only count once per unit spec (avoid duplicates within same spec)
      if (!seenSignatures.has(signature)) {
        seenSignatures.add(signature);

        if (!signatureCounts.has(signature)) {
          signatureCounts.set(signature, { count: 0, param });
        }
        // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
        signatureCounts.get(signature)!.count++;
      }
    }
  }

  // Return params that appear in ALL unit specs
  const commonParams: TParams[] = [];
  for (const [, { count, param }] of signatureCounts) {
    if (count === totalUnitSpecs) {
      commonParams.push(param);
    }
  }

  return commonParams;
}

/**
 * Recursively removes specific params (by name) from nested specs.
 */
function removeSpecificParamsFromNestedSpecs(
  spec: SpecWithParams,
  paramNamesToRemove: Set<string>,
): SpecWithParams {
  if ("vconcat" in spec && Array.isArray(spec.vconcat)) {
    return {
      ...spec,
      vconcat: spec.vconcat.map((subSpec) =>
        removeSpecificParamsFromNestedSpecs(subSpec, paramNamesToRemove),
      ),
    } as SpecWithParams;
  }

  if ("hconcat" in spec && Array.isArray(spec.hconcat)) {
    return {
      ...spec,
      hconcat: spec.hconcat.map((subSpec) =>
        removeSpecificParamsFromNestedSpecs(subSpec, paramNamesToRemove),
      ),
    } as SpecWithParams;
  }

  if ("mark" in spec && "params" in spec && spec.params) {
    // This is a unit spec, filter out params that should be hoisted
    const currentParams = spec.params;
    const filteredParams: TParams[] = [];

    for (const param of currentParams) {
      if (!param || typeof param !== "object" || !("name" in param)) {
        filteredParams.push(param);
        continue;
      }
      if (!paramNamesToRemove.has(param.name)) {
        filteredParams.push(param);
      }
    }

    if (filteredParams.length === 0) {
      const { params, ...rest } = spec;
      return rest as SpecWithParams;
    }

    return {
      ...spec,
      params: filteredParams,
    } as SpecWithParams;
  }

  return spec;
}

/**
 * Recursively applies opacity encoding to all unit specs based on param names.
 */
function applyOpacityToNestedSpecs<T extends SpecWithParams>(
  spec: T,
  paramNames: string[],
): T {
  if ("vconcat" in spec && Array.isArray(spec.vconcat)) {
    return {
      ...spec,
      vconcat: spec.vconcat.map((subSpec) =>
        applyOpacityToNestedSpecs(subSpec, paramNames),
      ),
    };
  }

  if ("hconcat" in spec && Array.isArray(spec.hconcat)) {
    return {
      ...spec,
      hconcat: spec.hconcat.map((subSpec) =>
        applyOpacityToNestedSpecs(subSpec, paramNames),
      ),
    };
  }

  if ("layer" in spec) {
    // Don't apply to layers, they handle their own opacity
    return spec;
  }

  if ("mark" in spec && Marks.isInteractive(spec.mark)) {
    // This is a unit spec, apply opacity
    return {
      ...spec,
      mark: Marks.makeClickable(spec.mark),
      encoding: makeEncodingInteractive(
        "opacity",
        spec.encoding || {},
        paramNames,
        spec.mark,
      ),
    };
  }

  return spec;
}

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

  // For vconcat/hconcat with existing chart params, return unchanged.
  // This preserves cross-view interactions (e.g., brush selections in
  // concatenated charts). See issue #7668.
  const isCompoundSpec = "vconcat" in spec || "hconcat" in spec;
  if (hasChartParam && isCompoundSpec) {
    return spec;
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
    // Hoist params to top level and apply opacity to all nested specs
    return hoistParamsAndApplyOpacity({ ...spec, vconcat: subSpecs });
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
    // Hoist params to top level and apply opacity to all nested specs
    return hoistParamsAndApplyOpacity({ ...spec, hconcat: subSpecs });
  }

  if ("layer" in spec) {
    // Check if has top-level params already (not just legend). If so, we don't add any more as it
    // will cause conflicts.
    const hasTopLevelParams = spec.params && spec.params.length > 0;
    const shouldAddLegendSelection =
      fieldSelection !== false && !hasTopLevelParams;

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

      // Only add legend params to first
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
  if (binnedFields.length > 0 && resolvedChartSelection.includes("point")) {
    nextParams.push(Params.binColoring(layerNum));
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
