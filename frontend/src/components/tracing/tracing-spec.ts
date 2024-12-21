/* Copyright 2024 Marimo. All rights reserved. */
import type { CellId } from "@/core/cells/ids";
import type { CellRun } from "@/core/cells/runs";
import type { ResolvedTheme } from "@/theme/useTheme";
import type { TopLevelSpec } from "vega-lite";

export const REACT_HOVERED_CELLID = "hoveredCellId";
export const VEGA_HOVER_SIGNAL = "cellHover";

export type ChartPosition = "sideBySide" | "above";
export interface ChartValues {
  cell: CellId;
  cellNum: number;
  startTimestamp: string;
  endTimestamp: string;
  elapsedTime: string;
  status: CellRun["status"];
}

export function createGanttBaseSpec(
  chartValues: ChartValues[],
  hiddenInputElementId: string,
  chartPosition: ChartPosition,
  theme: ResolvedTheme,
): TopLevelSpec {
  return {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    background: theme === "dark" ? "black" : undefined,
    mark: {
      type: "bar",
      cornerRadius: 2,
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
      y: {
        field: "cellNum",
        scale: { paddingInner: 0.2 },
        sort: { field: "cellNum" },
        title: "cell",
        axis: chartPosition === "sideBySide" ? null : undefined,
      },
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
      color: {
        field: "status",
        scale: { domain: ["success", "error"], range: ["#37BE5F", "red"] }, // green is the same colour as chrome's network tab
        legend: null,
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
