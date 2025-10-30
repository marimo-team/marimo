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
import React, { type JSX, Suspense, useEffect, useRef, useState } from "react";
import { useVegaEmbed } from "react-vega";
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
import type { SignalListener } from "../charts/types";
import { ElapsedTime, formatElapsedTime } from "../editor/cell/CellStatus";
import { PanelEmptyState } from "../editor/chrome/panels/empty-state";
import { CellLink } from "../editor/links/cell-link";
import {
  type ChartPosition,
  type ChartValues,
  createGanttBaseSpec,
  VEGA_HOVER_SIGNAL,
} from "./tracing-spec";
import { formatChartTime } from "./utils";

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
          return null;
        })}
      </div>
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
  const vegaRef = useRef<HTMLDivElement>(null);
  const { ref, width = 300 } = useResizeObserver<HTMLDivElement>();

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

  const embed = useVegaEmbed({
    ref: vegaRef,
    spec: vegaSpec,
    options: {
      theme: theme === "dark" ? "dark" : undefined,
      width: width - 50,
      height: chartPosition === "above" ? 120 : 100,
      actions: false,
      // Using vega instead of vegaLite as some parts of the spec get interpreted as vega & will throw warnings
      mode: "vega",
      renderer: "canvas",
    },
  });

  useEffect(() => {
    const signalListeners: SignalListener[] = [
      {
        signalName: VEGA_HOVER_SIGNAL,
        handler: (_name: string, value: unknown) => {
          const signalValue = value as VegaHoverCellSignal;
          const hoveredCell = signalValue.cell?.[0] as CellId | undefined;
          setHoveredCellId(hoveredCell ?? null);
        },
      },
    ];

    signalListeners.forEach(({ signalName, handler }) => {
      embed?.view.addSignalListener(signalName, handler);
    });

    return () => {
      signalListeners.forEach(({ signalName, handler }) => {
        embed?.view.removeSignalListener(signalName, handler);
      });
    };
  }, [embed]);

  const traceRows = (
    <TraceRows
      run={run}
      hoveredCellId={hoveredCellId}
      hiddenInputElementId={hiddenInputElementId}
    />
  );

  const chartElement = (
    <div
      className={chartPosition === "sideBySide" ? "-mt-0.5 flex-1" : ""}
      ref={ref}
    >
      <Suspense>
        <div ref={vegaRef} />
      </Suspense>
    </div>
  );

  if (chartPosition === "above") {
    return (
      <div key={run.runId} className="flex flex-col">
        <pre className="font-mono font-semibold">
          {title}
          {chartElement}
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
      {chartElement}
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
        "flex flex-row gap-2 py-1 px-1 opacity-70 hover:bg-(--gray-3) hover:opacity-100",
        hovered && "bg-(--gray-3) opacity-100",
      )}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <span className="text-(--gray-10) dark:text-(--gray-11)">
        [{formatLogTimestamp(cellRun.startTime)}]
      </span>
      <span className="text-(--gray-10) w-16">
        (<CellLink cellId={cellRun.cellId} />)
      </span>
      <span className="w-40 truncate -ml-1">{cellRun.code}</span>

      <div className="flex flex-row gap-1 w-16 justify-end -ml-2">
        <Tooltip content={elapsedTimeTooltip}>
          <span className="text-(--gray-10) dark:text-(--gray-11)">
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
