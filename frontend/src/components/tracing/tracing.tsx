/* Copyright 2024 Marimo. All rights reserved. */
import { FAVICONS } from "@/components/editor/dynamic-favicon";
import React, { useRef, useState } from "react";
import type { CellId } from "@/core/cells/ids";
import { ElapsedTime, formatElapsedTime } from "../editor/cell/CellStatus";
import { Tooltip } from "@/components/ui/tooltip";
import { compile } from "vega-lite";
import { ChevronRight, ChevronDown } from "lucide-react";
import type { SignalListeners, VisualizationSpec } from "react-vega";
import {
  type RunId,
  runsAtom,
  type CellRun,
  type Run,
  useRunsActions,
} from "@/core/cells/runs";
import { useAtomValue } from "jotai";
import { CellLink } from "../editor/links/cell-link";
import { formatLogTimestamp } from "@/core/cells/logs";
import { useCellIds } from "@/core/cells/cells";
import {
  type ChartPosition,
  type ChartValues,
  createGanttBaseSpec,
  VEGA_HOVER_SIGNAL,
} from "./tracing-spec";
import { ClearButton } from "../buttons/clear-button";
import { cn } from "@/utils/cn";

const LazyVega = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.Vega })),
);

export const Tracing: React.FC = () => {
  const { runIds: newestToOldestRunIds, runMap } = useAtomValue(runsAtom);
  const { clearRuns } = useRunsActions();

  const [chartPosition, setChartPosition] =
    useState<ChartPosition>("sideBySide");

  const toggleChartPosition = () => {
    if (chartPosition === "above") {
      setChartPosition("sideBySide");
    } else {
      setChartPosition("above");
    }
  };

  return (
    <div className="py-1 px-2 overflow-y-scroll">
      <div className="flex flex-row justify-end gap-3">
        <div className="flex flex-row gap-1 items-center">
          <label htmlFor="chartPosition" className="text-xs">
            Inline chart
          </label>
          <input
            type="checkbox"
            name="chartPosition"
            id="chartPosition"
            onClick={toggleChartPosition}
            defaultChecked={true}
            className="h-3"
          />
        </div>

        <ClearButton dataTestId="clear-traces-button" onClick={clearRuns} />
      </div>

      <div className="flex flex-col gap-3">
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

interface ChartProps {
  className?: string;
  width: number;
  height: number;
  vegaSpec: VisualizationSpec;
  signalListeners: SignalListeners;
}

const Chart: React.FC<ChartProps> = (props: ChartProps) => {
  return (
    <div className={props.className}>
      <LazyVega
        spec={props.vegaSpec}
        width={props.width}
        height={props.height}
        signalListeners={props.signalListeners}
      />
    </div>
  );
};

interface VegaHoverCellSignal {
  cell: string[];
  vlPoint: unknown;
}

const TraceBlock: React.FC<{
  run: Run;
  chartPosition: ChartPosition;
}> = ({ run, chartPosition }) => {
  const [collapsed, setCollapsed] = useState(false);
  const [hoveredCellId, setHoveredCellId] = useState<CellId | null>();

  // To send signals to Vega from React, we bind a hidden input element
  const hiddenInputRef = useRef<HTMLInputElement>(null);
  const dispatchHoverEvent = (cellId: CellId | null) => {
    // dispatch input event to trigger vega's param to update
    if (hiddenInputRef.current) {
      hiddenInputRef.current.value = String(cellId);
      hiddenInputRef.current.dispatchEvent(
        new Event("input", { bubbles: true }),
      );
    }
  };

  const handleVegaSignal = {
    [VEGA_HOVER_SIGNAL]: (name: string, value: unknown) => {
      const signalValue = value as VegaHoverCellSignal;
      const hoveredCell = signalValue.cell?.[0] as CellId | undefined;
      setHoveredCellId(hoveredCell ?? null);
    },
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

  const chartValues: ChartValues[] = run.cellRuns.map((cellRun) => {
    const elapsedTime = cellRun.elapsedTime ?? 0;
    return {
      cell: cellRun.cellId,
      cellNum: cellIds.inOrderIds.indexOf(cellRun.cellId),
      startTimestamp: formatChartTime(cellRun.startTime),
      endTimestamp: formatChartTime(cellRun.startTime + elapsedTime),
      elapsedTime: formatElapsedTime(elapsedTime * 1000),
    };
  });

  const hiddenInputElementId = `hiddenInputElement-${run.runId}`;
  const vegaSpec = compile(
    createGanttBaseSpec(chartValues, hiddenInputElementId, chartPosition),
  ).spec;

  const TraceRows = (
    <div className="text-xs mt-0.5 ml-3 flex flex-col gap-0.5">
      <input
        type="text"
        id={hiddenInputElementId}
        defaultValue={hoveredCellId || ""}
        hidden={true}
        ref={hiddenInputRef}
      />
      {run.cellRuns.map((cellRun) => (
        <TraceRow
          key={cellRun.cellId}
          cellRun={cellRun}
          hovered={cellRun.cellId === hoveredCellId}
          dispatchHoverEvent={dispatchHoverEvent}
        />
      ))}
    </div>
  );

  if (chartPosition === "above") {
    return (
      <div key={run.runId} className="flex flex-col">
        <pre className="font-mono font-semibold">
          {TraceTitle}
          {!collapsed && (
            <Chart
              vegaSpec={vegaSpec}
              width={320}
              height={120}
              signalListeners={handleVegaSignal}
            />
          )}
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
          signalListeners={handleVegaSignal}
        />
      )}
    </div>
  );
};

interface TraceRowProps {
  cellRun: CellRun;
  hovered: boolean;
  dispatchHoverEvent: (cellId: CellId | null) => void;
}

const TraceRow: React.FC<TraceRowProps> = ({
  cellRun,
  hovered,
  dispatchHoverEvent,
}: TraceRowProps) => {
  const elapsedTimeStr = cellRun.elapsedTime
    ? formatElapsedTime(cellRun.elapsedTime * 1000)
    : "-";

  const elapsedTimeTooltip = cellRun.elapsedTime ? (
    <span>
      This cell took <ElapsedTime elapsedTime={elapsedTimeStr} /> to run
    </span>
  ) : (
    <span>This cell has not been run</span>
  );

  const handleMouseEnter = () => {
    dispatchHoverEvent(cellRun.cellId);
  };

  const handleMouseLeave = () => {
    dispatchHoverEvent(null);
  };

  return (
    <div
      className={cn(
        "flex flex-row gap-2 py-1 px-1 opacity-70 hover:bg-[var(--gray-3)] hover:opacity-100",
        hovered && "bg-[var(--gray-3)] opacity-100",
      )}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
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

        {/* TODO: Shouldn't use favicon and need to add an image for 'queued' state. */}
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
