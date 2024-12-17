/* Copyright 2024 Marimo. All rights reserved. */
import type { Field } from "@/plugins/impl/vega/types";
import type { TopLevelSpec } from "vega-lite";
import type { PositionDef } from "vega-lite/build/src/channeldef";
import type { TopLevelParameter } from "vega-lite/build/src/spec/toplevel";

export const REACT_HOVERED_CELLID = "hoveredCellId";
export const VEGA_HOVER_SIGNAL = "cellHover";

export function createBaseSpec(
  showYAxis: boolean,
  ...additionalParams: TopLevelParameter[]
): TopLevelSpec {
  const yAxis: PositionDef<Field> | Partial<PositionDef<Field>> = {
    field: "cellNum",
    scale: { paddingInner: 0.2 },
    sort: { field: "cellNum" },
    title: "cell",
  };
  if (!showYAxis) {
    yAxis.axis = null;
  }

  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    mark: {
      type: "bar",
      cornerRadius: 2,
      fill: "#37BE5F", // same colour as chrome's network tab
    },
    params: [
      ...additionalParams,
      {
        name: "zoomAndPan",
        select: "interval",
        bind: "scales",
      },
      {
        name: "cursor",
        value: "grab",
      },
      {
        name: VEGA_HOVER_SIGNAL,
        select: {
          type: "point",
          on: "pointerover",
          fields: ["cell"],
        },
      },
    ],
    height: { step: 23 },
    encoding: {
      y: yAxis,
      x: {
        field: "startTimestamp",
        type: "temporal",
        axis: { orient: "top", title: null },
      },
      x2: { field: "endTimestamp", type: "temporal" },
      tooltip: [
        { field: "cellNum", title: "Cell" },
        {
          field: "startTimestamp",
          type: "temporal",
          timeUnit: "hoursminutessecondsmilliseconds",
          title: "Start",
        },
        {
          field: "endTimestamp",
          type: "temporal",
          timeUnit: "hoursminutessecondsmilliseconds",
          title: "End",
        },
      ],
      size: {
        value: {
          expr: `${REACT_HOVERED_CELLID} == toString(datum.cell) ? 20 : 18`,
        },
      },
    },
    config: {
      view: {
        stroke: "transparent",
      },
    },
  };
}
