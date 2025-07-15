/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtomValue, useSetAtom } from "jotai";
import {
  ActivityIcon,
  ChevronDown,
  ChevronRight,
  CircleCheck,
  CircleEllipsis,
  CirclePlayIcon,
  CircleX,
} from "lucide-react";
import React, { type JSX, Suspense, useRef, useState } from "react";
import type { SignalListeners, VisualizationSpec } from "react-vega";
import useResizeObserver from "use-resize-observer";
import { compile } from "vega-lite";
import { Tooltip } from "@/components/ui/tooltip";
import { useCellIds } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { formatLogTimestamp } from "@/core/cells/logs";
import {
  type CellRun,
  type Run,
  type RunId,
  runsAtom,
  useRunsActions,
} from "@/core/cells/runs";
import { type ResolvedTheme, useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { ClearButton } from "../buttons/clear-button";
import { ElapsedTime, formatElapsedTime } from "../editor/cell/CellStatus";
import { PanelEmptyState } from "../editor/chrome/panels/empty-state";
import { CellLink } from "../editor/links/cell-link";
import {
  type ChartPosition,
  type ChartValues,
  createGanttBaseSpec,
  VEGA_HOVER_SIGNAL,
} from "./tracing-spec";

const expandedRunsAtom = atom<Map<RunId, boolean>>(new Map<RunId, boolean>());

export const Tracing: React.FC = () => {
  const { runIds: newestToOldestRunIds, runMap } = useAtomValue(runsAtom);
  const expandedRuns = useAtomValue(expandedRunsAtom);
  const { clearRuns } = useRunsActions();

  const { theme } = useTheme();
  const [chartPosition, setChartPosition] = useState<ChartPosition>("above");

  const toggleChartPosition = () => {
    if (chartPosition === "above") {
      setChartPosition("sideBySide");
    } else {
      setChartPosition("above");
    }
  };

  if (newestToOldestRunIds.length === 0) {
    return (
      <PanelEmptyState
        title="No traces"
        description={<span>Cells that have ran will appear here.</span>}
        icon={<ActivityIcon />}
      />
    );
  }

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
            data-testid="chartPosition"
            onClick={toggleChartPosition}
            defaultChecked={chartPosition === "sideBySide"}
            className="h-3 cursor-pointer"
          />
        </div>

        <ClearButton dataTestId="clear-traces-button" onClick={clearRuns} />
      </div>

      <div className="flex flex-col gap-3">
        {newestToOldestRunIds.map((runId: RunId, index: number) => {
          const run = runMap.get(runId);
          if (run) {
            return (
              <TraceBlock
                key={run.runId}
                run={run}
                isExpanded={expandedRuns.get(run.runId)}
                isMostRecentRun={index === 0}
                chartPosition={chartPosition}
                theme={theme}
              />
            );
          }
        })}
      </div>
    </div>
  );
};

// Using vega instead of vegaLite as some parts of the spec get interpreted as vega & will throw warnings
const LazyVega = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.Vega })),
);
interface ChartProps {
  className?: string;
  height: number;
  vegaSpec: VisualizationSpec;
  signalListeners: SignalListeners;
  theme: ResolvedTheme;
}

const Chart: React.FC<ChartProps> = (props: ChartProps) => {
  const { ref, width = 300 } = useResizeObserver<HTMLDivElement>();
  return (
    <div className={props.className} ref={ref}>
      <Suspense>
        <LazyVega
          spec={props.vegaSpec}
          theme={props.theme === "dark" ? "dark" : undefined}
          width={width - 50}
          height={props.height}
          signalListeners={props.signalListeners}
          actions={false}
        />
      </Suspense>
    </div>
  );
};

interface VegaHoverCellSignal {
  cell: string[];
  vlPoint: unknown;
}

const TraceBlock: React.FC<{
  run: Run;
  /**
   * undefined means the user hasn't clicked on this run yet
   */
  isExpanded: boolean | undefined;
  isMostRecentRun: boolean;
  chartPosition: ChartPosition;
  theme: ResolvedTheme;
}> = ({ run, isMostRecentRun, chartPosition, isExpanded, theme }) => {
  const setExpandedRuns = useSetAtom(expandedRunsAtom);
  // We prefer the user's last click, but if they haven't clicked on this run,
  // we expand the most recent run by default, otherwise we collapse it.
  isExpanded = isExpanded ?? isMostRecentRun;

  const onToggleExpanded = () => {
    setExpandedRuns((prev) => {
      const newMap = new Map(prev);
      newMap.set(run.runId, !isExpanded);
      return newMap;
    });
  };

  const Icon = isExpanded ? ChevronDown : ChevronRight;
  const chevron = <Icon height={16} className="inline" />;

  const traceTitle = (
    <span className="text-sm cursor-pointer" onClick={onToggleExpanded}>
      Run - {formatLogTimestamp(run.runStartTime)}
      {chevron}
    </span>
  );

  if (!isExpanded) {
    return (
      <div key={run.runId} className="flex flex-col">
        <pre className="font-mono font-semibold">{traceTitle}</pre>
      </div>
    );
  }

  return (
    <TraceBlockBody
      key={run.runId}
      run={run}
      chartPosition={chartPosition}
      theme={theme}
      title={traceTitle}
    />
  );
};

const TraceBlockBody: React.FC<{
  run: Run;
  chartPosition: ChartPosition;
  theme: ResolvedTheme;
  title: React.ReactNode;
}> = ({ run, chartPosition, theme, title }) => {
  const [hoveredCellId, setHoveredCellId] = useState<CellId | null>();

  const handleVegaSignal = {
    [VEGA_HOVER_SIGNAL]: (_name: string, value: unknown) => {
      const signalValue = value as VegaHoverCellSignal;
      const hoveredCell = signalValue.cell?.[0] as CellId | undefined;
      setHoveredCellId(hoveredCell ?? null);
    },
  };

  const cellIds = useCellIds();

  const chartValues: ChartValues[] = [...run.cellRuns.values()].map(
    (cellRun) => {
      const elapsedTime = cellRun.elapsedTime ?? 0;
      return {
        cell: cellRun.cellId,
        cellNum: cellIds.inOrderIds.indexOf(cellRun.cellId),
        startTimestamp: formatChartTime(cellRun.startTime),
        endTimestamp: formatChartTime(cellRun.startTime + elapsedTime),
        elapsedTime: formatElapsedTime(elapsedTime * 1000),
        status: cellRun.status,
      };
    },
  );

  const hiddenInputElementId = `hiddenInputElement-${run.runId}`;
  const vegaSpec = compile(
    createGanttBaseSpec(
      chartValues,
      hiddenInputElementId,
      chartPosition,
      theme,
    ),
  ).spec;

  const traceRows = (
    <TraceRows
      run={run}
      hoveredCellId={hoveredCellId}
      hiddenInputElementId={hiddenInputElementId}
    />
  );

  if (chartPosition === "above") {
    return (
      <div key={run.runId} className="flex flex-col">
        <pre className="font-mono font-semibold">
          {title}
          <Chart
            vegaSpec={vegaSpec}
            height={120}
            signalListeners={handleVegaSignal}
            theme={theme}
          />
          {traceRows}
        </pre>
      </div>
    );
  }

  return (
    <div key={run.runId} className="flex flex-row">
      <pre className="font-mono font-semibold">
        {title}
        {traceRows}
      </pre>
      <Chart
        className="-mt-0.5 flex-1"
        vegaSpec={vegaSpec}
        height={100}
        signalListeners={handleVegaSignal}
        theme={theme}
      />
    </div>
  );
};

const TraceRows = (props: {
  run: Run;
  hoveredCellId: CellId | null | undefined;
  hiddenInputElementId: string;
}) => {
  const { run, hoveredCellId, hiddenInputElementId } = props;

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

  return (
    <div className="text-xs mt-0.5 ml-3 flex flex-col gap-0.5">
      <input
        type="text"
        id={hiddenInputElementId}
        defaultValue={hoveredCellId || ""}
        hidden={true}
        ref={hiddenInputRef}
      />
      {[...run.cellRuns.values()].map((cellRun) => (
        <TraceRow
          key={cellRun.cellId}
          cellRun={cellRun}
          hovered={cellRun.cellId === hoveredCellId}
          dispatchHoverEvent={dispatchHoverEvent}
        />
      ))}
    </div>
  );
};

const StatusIcons: Record<CellRun["status"], JSX.Element> = {
  success: <CircleCheck color="green" size={14} />,
  running: <CirclePlayIcon color="var(--blue-10)" size={14} />,
  error: <CircleX color="red" size={14} />,
  queued: <CircleEllipsis color="grey" size={14} />,
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
      <span className="text-[var(--gray-10)] dark:text-[var(--gray-11)]">
        [{formatLogTimestamp(cellRun.startTime)}]
      </span>
      <span className="text-[var(--gray-10)] w-16">
        (<CellLink cellId={cellRun.cellId} />)
      </span>
      <span className="w-40 truncate -ml-1">{cellRun.code}</span>

      <div className="flex flex-row gap-1 w-16 justify-end -ml-2">
        <Tooltip content={elapsedTimeTooltip}>
          <span className="text-[var(--gray-10)] dark:text-[var(--gray-11)]">
            {elapsedTimeStr}
          </span>
        </Tooltip>

        <Tooltip content={cellRun.status}>
          {StatusIcons[cellRun.status]}
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
