/* Copyright 2024 Marimo. All rights reserved. */
import type { CellId } from "@/core/cells/ids";
import type { Field } from "@/plugins/impl/vega/types";
import type { TopLevelSpec } from "vega-lite";
import type { PositionDef } from "vega-lite/build/src/channeldef";

export const REACT_HOVERED_CELLID = "hoveredCellId";
export const VEGA_HOVER_SIGNAL = "cellHover";

export type ChartPosition = "sideBySide" | "above";
export interface ChartValues {
  cell: CellId;
  cellNum: number;
  startTimestamp: string;
  endTimestamp: string;
  elapsedTime: string;
}

export function createGanttBaseSpec(
  chartValues: ChartValues[],
  hiddenInputElementId: string,
  chartPosition: ChartPosition,
): TopLevelSpec {
  const yAxis: PositionDef<Field> | Partial<PositionDef<Field>> = {
    field: "cellNum",
    scale: { paddingInner: 0.2 },
    sort: { field: "cellNum" },
    title: "cell",
  };

  const hideYAxisLine = chartPosition === "sideBySide";
  if (hideYAxisLine) {
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
      {
        name: REACT_HOVERED_CELLID,
        bind: { element: `#${hiddenInputElementId}` },
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
        {
          field: "startTimestamp",
          type: "temporal",
          timeUnit: "dayhoursminutesseconds",
          title: "Start",
        },
        {
          field: "endTimestamp",
          type: "temporal",
          timeUnit: "dayhoursminutesseconds",
          title: "End",
        },
      ],
      size: {
        value: {
          expr: `${REACT_HOVERED_CELLID} == toString(datum.cell) ? 19.5 : 18`,
        },
      },
    },
    data: {
      values: chartValues,
    },
    config: {
      view: {
        stroke: "transparent",
      },
    },
  };
}