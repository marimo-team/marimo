/* Copyright 2023 Marimo. All rights reserved. */
import {
  Mark,
  SelectionParameter,
  SingleDefUnitChannel,
  VegaLiteSpec,
} from "./types";

const ParamNames = {
  LEGEND_SELECTION: "legend_selection",
  SELECT: "select",
  HIGHLIGHT: "highlight",
};

export const Params = {
  highlight() {
    return {
      name: ParamNames.HIGHLIGHT,
      select: { type: "point", on: "mouseover" },
    };
  },
  interval(mark: Mark): SelectionParameter<"interval"> {
    return {
      name: `${ParamNames.SELECT}_interval`,
      select: {
        type: "interval",
        encodings: ENCODING_AXIS_FOR_MARK[mark],
        mark: {
          fill: "#669EFF",
          fillOpacity: 0.07,
          stroke: "#669EFF",
          strokeOpacity: 0.4,
        },
      },
    };
  },
  point(mark: Mark): SelectionParameter<"point"> {
    return {
      name: `${ParamNames.SELECT}_point`,
      select: {
        type: "point",
        encodings: ENCODING_AXIS_FOR_MARK[mark],
      },
    };
  },
  legend(field: string): SelectionParameter<"point"> {
    return {
      name: `${ParamNames.LEGEND_SELECTION}_${field}`,
      select: {
        type: "point",
        fields: [field],
      },
      bind: "legend",
    };
  },
};

const ENCODING_AXIS_FOR_MARK: Record<Mark, SingleDefUnitChannel[] | undefined> =
  {
    arc: ["color"],
    image: undefined,
    trail: undefined,
    area: ["color"],
    bar: ["x"],
    circle: ["x", "y"],
    geoshape: ["x", "y"],
    line: ["x", "y"],
    point: ["x", "y"],
    rect: ["x", "y"],
    rule: ["x", "y"],
    square: ["x", "y"],
    text: ["x", "y"],
    tick: ["x", "y"],
  };

export function getSelectionParamNames(spec: VegaLiteSpec): string[] {
  const params = spec.params;
  if (params && params.length > 0) {
    return params
      .filter((param) => {
        return "select" in param && param.select !== undefined;
      })
      .map((param) => {
        return param.name;
      });
  }
  return [];
}
