/* Copyright 2026 Marimo. All rights reserved. */

import { uniq } from "lodash-es";
import type { TopLevelSpec } from "vega-lite";
import type { NonNormalizedSpec } from "vega-lite/types_unstable/spec/index.js";
import { Marks } from "./marks";
import {
  type Field,
  type LayerSpec,
  Mark,
  type SelectionParameter,
  type SingleDefUnitChannel,
  type UnitSpec,
  type VegaLiteUnitSpec,
} from "./types";

export const ParamNames = {
  point(layerNum: number | undefined) {
    return layerNum == null ? "select_point" : `select_point_${layerNum}`;
  },
  interval(layerNum: number | undefined) {
    return layerNum == null ? "select_interval" : `select_interval_${layerNum}`;
  },
  legendSelection(field: string) {
    return `legend_selection_${field}`;
  },
  /**
   * Special param for binned charts that controls opacity/coloring.
   * This param is used for visual feedback only and does NOT send signals to the backend.
   * The actual selection param (point/interval) handles backend filtering.
   */
  binColoring(layerNum: number | undefined) {
    return layerNum == null ? "bin_coloring" : `bin_coloring_${layerNum}`;
  },
  HIGHLIGHT: "highlight",
  PAN_ZOOM: "pan_zoom",
  hasPoint(names: string[]) {
    return names.some((name) => name.startsWith("select_point"));
  },
  hasInterval(names: string[]) {
    return names.some((name) => name.startsWith("select_interval"));
  },
  hasLegend(names: string[]) {
    return names.some((name) => name.startsWith("legend_selection"));
  },
  hasPanZoom(names: string[]) {
    return names.some((name) => name.startsWith("pan_zoom"));
  },
  isBinColoring(name: string) {
    return name.startsWith("bin_coloring");
  },
};

export const Params = {
  highlight() {
    return {
      name: ParamNames.HIGHLIGHT,
      select: { type: "point", on: "mouseover" },
    };
  },
  interval(
    spec: VegaLiteUnitSpec,
    layerNum: number | undefined,
  ): SelectionParameter<"interval"> {
    return {
      name: ParamNames.interval(layerNum),
      select: {
        type: "interval",
        encodings: getEncodingAxisForMark(spec),
        mark: {
          fill: "#669EFF",
          fillOpacity: 0.07,
          stroke: "#669EFF",
          strokeOpacity: 0.4,
        },
        // So this does not conflict with pan/zoom via metaKey
        on: "[mousedown[!event.metaKey], mouseup] > mousemove[!event.metaKey]",
        translate:
          "[mousedown[!event.metaKey], mouseup] > mousemove[!event.metaKey]",
      },
    };
  },
  point(
    spec: VegaLiteUnitSpec,
    layerNum: number | undefined,
  ): SelectionParameter<"point"> {
    return {
      name: ParamNames.point(layerNum),
      select: {
        type: "point",
        encodings: getEncodingAxisForMark(spec),
        on: "click[!event.metaKey]",
      },
    };
  },
  /**
   * Creates a param for binned charts that controls opacity/coloring only.
   * This param does NOT send signals to the backend - it's purely for visual feedback.
   * The regular selection param (point/interval) handles backend filtering.
   */
  binColoring(layerNum: number | undefined): SelectionParameter<"point"> {
    return {
      name: ParamNames.binColoring(layerNum),
      select: {
        type: "point",
        on: "click[!event.metaKey]",
      },
    };
  },
  legend(field: string): SelectionParameter<"point"> {
    return {
      name: ParamNames.legendSelection(field),
      select: {
        type: "point",
        fields: [field],
      },
      bind: "legend",
    };
  },
  panZoom(): SelectionParameter<"interval"> {
    return {
      name: ParamNames.PAN_ZOOM,
      bind: "scales",
      select: {
        type: "interval",
        on: "[mousedown[event.metaKey], window:mouseup] > window:mousemove!",
        translate:
          "[mousedown[event.metaKey], window:mouseup] > window:mousemove!",
        zoom: "wheel![event.metaKey]",
      },
    };
  },
};

export function getEncodingAxisForMark(
  spec: VegaLiteUnitSpec,
): SingleDefUnitChannel[] | undefined {
  const mark = Marks.getMarkType(spec.mark);
  switch (mark) {
    case Mark.image:
    case Mark.trail:
      return undefined;
    case Mark.area:
    case Mark.arc:
      return ["color"];
    case Mark.bar: {
      const direction = getDirectionOfBar(spec);
      return direction === "horizontal"
        ? ["y"]
        : direction === "vertical"
          ? ["x"]
          : undefined;
    }
    case Mark.circle:
    case Mark.geoshape:
    case Mark.line:
    case Mark.point:
    case Mark.rect:
    case Mark.rule:
    case Mark.square:
    case Mark.text:
    case Mark.tick:
      return ["x", "y"];
  }
}

export function getSelectionParamNames(
  spec: TopLevelSpec | LayerSpec<Field> | UnitSpec<Field> | NonNormalizedSpec,
): string[] {
  if ("params" in spec && spec.params && spec.params.length > 0) {
    const params = spec.params;
    const paramNames = params
      // @ts-expect-error TS doesn't know that `param` is an object
      .filter((param) => {
        if (param == null) {
          return false;
        }
        // @ts-expect-error TS doesn't know that `param` is an object
        return "select" in param && param.select !== undefined;
      })
      .map((param) => param.name);
    return uniq(paramNames);
  }
  if ("layer" in spec) {
    return uniq(spec.layer.flatMap(getSelectionParamNames));
  }
  if ("vconcat" in spec) {
    return uniq(spec.vconcat.flatMap(getSelectionParamNames));
  }
  if ("hconcat" in spec) {
    return uniq(spec.hconcat.flatMap(getSelectionParamNames));
  }
  return [];
}

/**
 * Returns the direction of the bar chart.
 */
export function getDirectionOfBar(
  spec: VegaLiteUnitSpec,
): "horizontal" | "vertical" | undefined {
  if (!spec || !("mark" in spec)) {
    return undefined;
  }

  const xEncoding = spec.encoding?.x;
  const yEncoding = spec.encoding?.y;

  if (xEncoding && "type" in xEncoding && xEncoding.type === "nominal") {
    return "vertical";
  }

  if (yEncoding && "type" in yEncoding && yEncoding.type === "nominal") {
    return "horizontal";
  }

  if (xEncoding && "aggregate" in xEncoding) {
    return "horizontal";
  }

  if (yEncoding && "aggregate" in yEncoding) {
    return "vertical";
  }

  return undefined;
}

/**
 * Returns the binned field names from the spec.
 * For binned charts, selections need to use fields instead of encodings.
 */
export function getBinnedFields(spec: VegaLiteUnitSpec): string[] {
  if (!spec.encoding) {
    return [];
  }

  const fields: string[] = [];

  for (const channel of Object.values(spec.encoding)) {
    // Check for binning
    if (
      channel &&
      typeof channel === "object" &&
      "bin" in channel &&
      channel.bin &&
      "field" in channel &&
      typeof channel.field === "string"
    ) {
      fields.push(channel.field);
    }
  }

  return fields;
}
