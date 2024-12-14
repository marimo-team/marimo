/* Copyright 2024 Marimo. All rights reserved. */
import { FAVICONS } from "@/components/editor/dynamic-favicon";
import React, { useRef, useState } from "react";
import type { CellId } from "@/core/cells/ids";
import { ElapsedTime, formatElapsedTime } from "../editor/cell/CellStatus";
import { Tooltip } from "@/components/ui/tooltip";
import { type Config, type TopLevelSpec, compile } from "vega-lite";
import { ChevronRight, ChevronDown, SettingsIcon } from "lucide-react";
import type { VisualizationSpec } from "react-vega";

const LazyVegaLite = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaLite })),
);

interface CellRun {
  cellID: string;
  code: string;
  elapsedTime: number;
  status: RunStatus;
}

export interface Run {
  runId: string;
  cellRuns: CellRun[];
  runStartTime: string;
}

// assumes the cellRuns are ordered correctly
const mockRuns: Run[] = [
  {
    runId: "7",
    cellRuns: [
      {
        cellID: "1",
        code: "import marimo as mo",
        elapsedTime: 23_000,
        status: "success",
      },
      {
        cellID: "2",
        code: "def generate_some()",
        elapsedTime: 46,
        status: "success",
      },
      {
        cellID: "3",
        code: "def generate_some()",
        elapsedTime: 46,
        status: "success",
      },
    ],
    runStartTime: "Dec 7 2.03pm",
  },
  {
    runId: "8",
    cellRuns: [
      {
        cellID: "1",
        code: "import marimo as mo",
        elapsedTime: 25,
        status: "success",
      },
      {
        cellID: "2",
        code: "def generate_some()",
        elapsedTime: 100,
        status: "success",
      },
      {
        cellID: "3",
        code: "def generate_some()",
        elapsedTime: 4600,
        status: "error",
      },
      {
        cellID: "4",
        code: "[print(i) for i in range(1, 100)]",
        elapsedTime: 8,
        status: "error", // should be disabled?
      },
    ],
    runStartTime: "Dec 7 2.01pm",
  },
];

interface Values {
  cell: number;
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
      { field: "cell", title: "Cell" },
      {
        field: "startTimestamp",
        type: "temporal",
        timeUnit: "monthdatehoursminutessecondsmilliseconds",
        title: "Start",
      },
      {
        field: "endTimestamp",
        type: "temporal",
        timeUnit: "monthdatehoursminutessecondsmilliseconds",
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
  // TODO: Either we get the runs of cells from FE side or BE side

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
        {mockRuns.map((run) => (
          <TraceBlock key={run.runId} run={run} chartPosition={chartPosition} />
        ))}
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
  const [hoveredCellID, setHoveredCellID] = useState<number>();
  const hiddenInputRef = useRef<HTMLInputElement>(null);

  const hoverOnCell = (cellID: number) => {
    setHoveredCellID(cellID);
    // dispatch input event to trigger vega's param to update
    if (hiddenInputRef.current) {
      hiddenInputRef.current.value = String(cellID);
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
      Run - {run.runStartTime}
      <ChevronComponent />
    </span>
  );

  const vegaSpec = compile(createGanttVegaLiteSpec(sampleData), {
    config,
  }).spec;

  const TraceRows = (
    <div className="text-xs mt-0.5 ml-3 flex flex-col gap-0.5">
      <input
        type="text"
        id="hiddenInputElement"
        defaultValue={hoveredCellID}
        hidden={true}
        ref={hiddenInputRef}
      />
      {run.cellRuns.map((cellRun) => (
        <TraceRow
          key={cellRun.cellID}
          timestamp="11:00:00 AM"
          cellID={cellRun.cellID}
          code={cellRun.code}
          elapsedTime={cellRun.elapsedTime}
          status={cellRun.status}
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

type RunStatus = "success" | "running" | "error";

interface TraceRowProps {
  timestamp: string;
  cellID: CellId;
  code: string;
  elapsedTime: number;
  status: RunStatus;
  hoverOnCell: (cellID: number) => void;
}

const TraceRow: React.FC<TraceRowProps> = (props: TraceRowProps) => {
  const elapsedTimeStr = formatElapsedTime(props.elapsedTime);
  const elapsedTimeTooltip = (
    <span>
      This cell took <ElapsedTime elapsedTime={elapsedTimeStr} /> to run
    </span>
  );

  const handleMouseEnter = () => {
    props.hoverOnCell(props.cellID);
  };

  return (
    <div
      className="flex flex-row gap-2 py-1 px-1 opacity-70 hover:bg-[var(--gray-3)] hover:opacity-100"
      onMouseEnter={handleMouseEnter}
    >
      <span className="text-[var(--gray-10)]">[{props.timestamp}]</span>
      <span className="text-[var(--gray-10)]">
        {/* (<CellLink cellId={props.cellID} />) */}
        (cell-1)
      </span>
      <span className="w-40 truncate">{props.code}</span>

      <div className="flex flex-row gap-1 basis-12 justify-end">
        <Tooltip content={elapsedTimeTooltip}>
          <span className="text-[var(--gray-10)]">{elapsedTimeStr}</span>
        </Tooltip>

        {/* TODO: Shouldn't use favicon. */}
        <Tooltip content={props.status}>
          <img
            className="w-4"
            src={FAVICONS[props.status]}
            alt={`${props.status} icon`}
          />
        </Tooltip>
      </div>
    </div>
  );
};
