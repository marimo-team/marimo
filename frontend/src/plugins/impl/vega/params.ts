/* Copyright 2024 Marimo. All rights reserved. */
import { Marks } from "./marks";
import {
  Mark,
  SelectionParameter,
  SingleDefUnitChannel,
  VegaLiteSpec,
  VegaLiteUnitSpec,
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
  interval(spec: VegaLiteUnitSpec): SelectionParameter<"interval"> {
    return {
      name: `${ParamNames.SELECT}_interval`,
      select: {
        type: "interval",
        encodings: getEncodingAxisForMark(spec),
        mark: {
          fill: "#669EFF",
          fillOpacity: 0.07,
          stroke: "#669EFF",
          strokeOpacity: 0.4,
        },
      },
    };
  },
  point(spec: VegaLiteUnitSpec): SelectionParameter<"point"> {
    return {
      name: `${ParamNames.SELECT}_point`,
      select: {
        type: "point",
        encodings: getEncodingAxisForMark(spec),
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
