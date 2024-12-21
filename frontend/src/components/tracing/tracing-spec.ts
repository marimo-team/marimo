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

const cellNumField = "cellNum" satisfies keyof ChartValues;
const cellField = "cell" satisfies keyof ChartValues;
const startTimestampField = "startTimestamp" satisfies keyof ChartValues;
const endTimestampField = "endTimestamp" satisfies keyof ChartValues;
const statusField = "status" satisfies keyof ChartValues;

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
          on: "mouseover",
          fields: [cellField],
          clear: "mouseout",
        },
      },
    ],
    height: { step: 23 },
    encoding: {
      y: {
        field: cellNumField,
        scale: { paddingInner: 0.2 },
        sort: { field: cellNumField },
        title: "cell",
        axis: chartPosition === "sideBySide" ? null : undefined,
      },
      x: {
        field: startTimestampField,
        type: "temporal",
        axis: { orient: "top", title: null },
      },
      x2: {
        field: endTimestampField,
        type: "temporal",
      },
      tooltip: [
        {
          field: startTimestampField,
          type: "temporal",
          timeUnit: "dayhoursminutesseconds",
          title: "Start",
        },
        {
          field: endTimestampField,
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
        field: statusField,
        scale: { domain: ["success", "error"], range: ["#37BE5F", "red"] },
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
