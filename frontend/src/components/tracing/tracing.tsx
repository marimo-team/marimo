/* Copyright 2024 Marimo. All rights reserved. */
import { FAVICONS } from "@/components/editor/dynamic-favicon";
import React, { useRef, useState } from "react";
import type { CellId } from "@/core/cells/ids";
import { ElapsedTime, formatElapsedTime } from "../editor/cell/CellStatus";
import { Tooltip } from "@/components/ui/tooltip";
import { type Config, type TopLevelSpec, compile } from "vega-lite";
import { ChevronRight, ChevronDown, SettingsIcon } from "lucide-react";
import type { VisualizationSpec } from "react-vega";
import {
  type RunId,
  runsAtom,
  type CellRun,
  type Run,
} from "@/core/cells/runs";
import { useAtomValue } from "jotai";
import { CellLink } from "../editor/links/cell-link";
import { formatLogTimestamp } from "@/core/cells/logs";
import { useCellIds } from "@/core/cells/cells";

// TODO: There are a few components like this in the codebase, maybe remove the redundancy
const LazyVegaLite = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaLite })),
);

interface Values {
  cell: CellId;
  cellNum: number;
  startTimestamp: string;
  endTimestamp: string;
  elapsedTime: string;
}

export interface Data {
  values: Values[];
}

const sampleData: Data = {
  values: [
    {
      cell: 1,
      startTimestamp: "2024-12-01 11:00:00.000",
      endTimestamp: "2024-12-01 11:00:00.230",
      elapsedTime: "23ms",
    },
    {
      cell: 2,
      startTimestamp: "2024-12-01 11:00:00.230",
      endTimestamp: "2024-12-01 11:00:00.466",
      elapsedTime: "46ms",
    },
    {
      cell: 3,
      startTimestamp: "2024-12-01 11:00:00.466",
      endTimestamp: "2024-12-01 11:00:00.636",
      elapsedTime: "46ms",
    },
  ],
};

const baseSpec: TopLevelSpec = {
  $schema: "https://vega.github.io/schema/vega-lite/v5.json",
  mark: {
    type: "bar",
    cornerRadius: 2,
    fill: "#37BE5F", // same colour as chrome's network tab
  },
  height: { step: 23 },
  params: [
    {
      name: "zoomAndPan",
      select: "interval",
      bind: "scales",
    },
    {
      name: "hoveredCellID",
      bind: { element: "#hiddenInputElement" },
    },
    {
      name: "cursor",
      value: "grab",
    },
  ],
  encoding: {
    y: {
      field: "cell",
      axis: null,
      scale: { paddingInner: 0.2 },
    },
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
      value: { expr: "hoveredCellID == toString(datum.cell) ? 25 : 20" },
    },
  },
};

function createGanttVegaLiteSpec(data: Data): TopLevelSpec {
  return {
    ...baseSpec,
    data,
  };
}

const config: Config = {
  view: {
    stroke: "transparent",
  },
};

export const Tracing: React.FC = () => {
  const { runIds: newestToOldestRunIds, runMap } = useAtomValue(runsAtom);

  const [chartPosition, setChartPosition] =
    useState<ChartPosition>("sideBySide");

  const toggleConfig = () => {
    if (chartPosition === "above") {
      setChartPosition("sideBySide");
    } else {
      setChartPosition("above");
    }
  };

  return (
    <div className="relative">
      <Tooltip content="Configuration">
        <button
          className="absolute right-0 pr-2 pt-2"
          type="button"
          onClick={toggleConfig}
        >
          <SettingsIcon className="h-6" strokeWidth={1.2} />
        </button>
      </Tooltip>

      <div className="pl-2 mt-7 flex flex-col gap-2">
        {newestToOldestRunIds.map((runId: RunId) => {
          const run = runMap.get(runId);
          if (run) {
            return (
              <TraceBlock
                key={run.runId}
                run={run}
                chartPosition={chartPosition}
              />
            );
          }
        })}
      </div>
    </div>
  );
};

type ChartPosition = "sideBySide" | "above";

interface ChartProps {
  className?: string;
  width: number;
  height: number;
  vegaSpec: VisualizationSpec;
}

const Chart: React.FC<ChartProps> = (props: ChartProps) => {
  return (
    <div className={props.className}>
      <LazyVegaLite
        spec={props.vegaSpec}
        width={props.width}
        height={props.height}
      />
    </div>
  );
};

const TraceBlock: React.FC<{ run: Run; chartPosition: ChartPosition }> = ({
  run,
  chartPosition,
}) => {
  // TODO: Initial one should be false, all the others are true
  const [collapsed, setCollapsed] = useState(false);

  // Used to sync Vega charts and React components
  // Note that this will only work for the first chart for now, until we create unique input elements
  const [hoveredCellId, setHoveredCellId] = useState<CellId>();
  const hiddenInputRef = useRef<HTMLInputElement>(null);

  const hoverOnCell = (cellId: CellId) => {
    setHoveredCellId(cellId);
    // dispatch input event to trigger vega's param to update
    if (hiddenInputRef.current) {
      hiddenInputRef.current.value = String(cellId);
      hiddenInputRef.current.dispatchEvent(
        new Event("input", { bubbles: true }),
      );
    }
  };

  const ChevronComponent = () => {
    const Icon = collapsed ? ChevronRight : ChevronDown;
    return <Icon height={16} className="inline" />;
  };

  const TraceTitle = (
    <span
      className="text-sm cursor-pointer"
      onClick={() => setCollapsed(!collapsed)}
    >
      Run - {formatLogTimestamp(run.runStartTime)}
      <ChevronComponent />
    </span>
  );

  const cellIds = useCellIds();

  const data: Data = {
    values: run.cellRuns.map((cellRun) => {
      return {
        cell: cellRun.cellId,
        cellNum: cellIds.inOrderIds.indexOf(cellRun.cellId),
        startTimestamp: formatChartTime(cellRun.startTime),
        endTimestamp: formatChartTime(cellRun.startTime + cellRun.elapsedTime),
        elapsedTime: formatElapsedTime(cellRun.elapsedTime * 1000),
      };
    }),
  };

  const vegaSpec = compile(createGanttVegaLiteSpec(data), {
    config,
  }).spec;

  const TraceRows = (
    <div className="text-xs mt-0.5 ml-3 flex flex-col gap-0.5">
      <input
        type="text"
        id="hiddenInputElement"
        defaultValue={hoveredCellId}
        hidden={true}
        ref={hiddenInputRef}
      />
      {run.cellRuns.map((cellRun) => (
        <TraceRow
          key={cellRun.cellId}
          cellRun={cellRun}
          hoverOnCell={hoverOnCell}
        />
      ))}
    </div>
  );

  if (chartPosition === "above") {
    return (
      <div key={run.runId} className="flex flex-col">
        <pre className="font-mono font-semibold">
          {TraceTitle}
          {!collapsed && <Chart vegaSpec={vegaSpec} width={350} height={120} />}
          {!collapsed && TraceRows}
        </pre>
      </div>
    );
  }

  return (
    <div key={run.runId} className="flex flex-row">
      <pre className="font-mono font-semibold">
        {TraceTitle}
        {!collapsed && TraceRows}
      </pre>
      {!collapsed && (
        <Chart
          className="-mt-0.5"
          vegaSpec={vegaSpec}
          width={240}
          height={100}
        />
      )}
    </div>
  );
};

interface TraceRowProps {
  cellRun: CellRun;
  hoverOnCell: (cellId: CellId) => void;
}

const TraceRow: React.FC<TraceRowProps> = ({
  cellRun,
  hoverOnCell,
}: TraceRowProps) => {
  const elapsedTimeStr = formatElapsedTime(cellRun.elapsedTime * 1000);
  const elapsedTimeTooltip = (
    <span>
      This cell took <ElapsedTime elapsedTime={elapsedTimeStr} /> to run
    </span>
  );

  const handleMouseEnter = () => {
    hoverOnCell(cellRun.cellId);
  };

  return (
    <div
      className="flex flex-row gap-2 py-1 px-1 opacity-70 hover:bg-[var(--gray-3)] hover:opacity-100"
      onMouseEnter={handleMouseEnter}
    >
      <span className="text-[var(--gray-10)]">
        [{formatLogTimestamp(cellRun.startTime)}]
      </span>
      <span className="text-[var(--gray-10)]">
        (<CellLink cellId={cellRun.cellId} />)
      </span>
      <span className="w-40 truncate">{cellRun.code}</span>

      <div className="flex flex-row gap-1 basis-12 justify-end">
        <Tooltip content={elapsedTimeTooltip}>
          <span className="text-[var(--gray-10)]">{elapsedTimeStr}</span>
        </Tooltip>

        {/* TODO: Shouldn't use favicon. */}
        <Tooltip content={cellRun.status}>
          <img
            className="w-4"
            src={FAVICONS[cellRun.status]}
            alt={`${cellRun.status} icon`}
          />
        </Tooltip>
      </div>
    </div>
  );
};

export function formatChartTime(timestamp: number): string {
  try {
    // Multiply by 1000 to convert seconds to milliseconds
    const date = new Date(timestamp * 1000);

    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0"); // getMonth() is 0-indexed
    const day = String(date.getDate()).padStart(2, "0");

    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    const seconds = String(date.getSeconds()).padStart(2, "0");

    const milliseconds = String(date.getMilliseconds()).padStart(3, "0");

    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}.${milliseconds}`;
  } catch {
    return "";
  }
}
