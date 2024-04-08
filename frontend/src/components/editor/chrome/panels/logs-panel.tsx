/* Copyright 2024 Marimo. All rights reserved. */
import { useCellActions, useCellLogs } from "@/core/cells/cells";
import { CellLog, formatLogTimestamp } from "@/core/cells/logs";
import { cn } from "@/utils/cn";
import React from "react";
import { FileTextIcon } from "lucide-react";
import { CellLink } from "../../links/cell-link";
import { PanelEmptyState } from "./empty-state";

interface Props {
  className?: string;
  logs: CellLog[];
}

export const LogsPanel: React.FC = () => {
  const logs = useCellLogs();
  const { clearLogs } = useCellActions();

  if (logs.length === 0) {
    return (
      <PanelEmptyState
        title="No logs"
        description={
          <span>
            <code className="border rounded px-1">stdout</code> and{" "}
            <code className="border rounded px-1">stderr</code> logs will appear
            here.
          </span>
        }
        icon={<FileTextIcon />}
      />
    );
  }

  return (
    <>
      <div className="flex flex-row justify-end px-2 py-1">
        <button
          data-testid="clear-logs-button"
          className="text-xs font-semibold text-accent-foreground"
          onClick={clearLogs}
        >
          Clear
        </button>
      </div>
      <div className="overflow-auto flex-1">
        <LogViewer logs={logs} className="min-w-[300px]" />
      </div>
    </>
  );
};

export const LogViewer: React.FC<Props> = ({ logs, className }) => {
  const hover =
    "opacity-70 group-hover:bg-[var(--gray-3)] group-hover:opacity-100";
  return (
    <div className={cn("flex flex-col", className)}>
      <pre className="grid text-xs font-mono gap-1 whitespace-break-spaces font-semibold align-left">
        <div
          className="grid grid-cols-[30px,1fr]"
          style={{ whiteSpace: "pre-wrap" }}
        >
          {logs.map((log, index) => (
            <div key={index} className="contents group">
              <span className={cn(hover, "text-right col-span-1 py-1 pr-1")}>
                {index + 1}
              </span>
              <span className={cn(hover, "px-2 flex gap-x-1.5 py-1 flex-wrap")}>
                {formatLog(log)}
              </span>
            </div>
          ))}
        </div>
      </pre>
    </div>
  );
};

function formatLog(log: CellLog) {
  const timestamp = formatLogTimestamp(log.timestamp);

  const color = levelColor[log.level];
  const level = log.level.toUpperCase();

  return (
    <>
      <span className="flex-shrink-0 text-[var(--gray-10)]">[{timestamp}]</span>
      <span className={cn("flex-shrink-0", color)}>{level}</span>
      <span className="flex-shrink-0 text-[var(--gray-10)]">
        (<CellLink cellId={log.cellId} />)
      </span>
      {log.message}
    </>
  );
}

const levelColor: Record<CellLog["level"], string> = {
  stdout: "text-[var(--grass-9)]",
  stderr: "text-[var(--red-9)]",
};
