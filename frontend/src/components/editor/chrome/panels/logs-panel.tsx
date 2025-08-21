/* Copyright 2024 Marimo. All rights reserved. */

import { FileTextIcon } from "lucide-react";
import React from "react";
import { ClearButton } from "@/components/buttons/clear-button";
import { useCellActions, useCellLogs } from "@/core/cells/cells";
import { type CellLog, formatLogTimestamp } from "@/core/cells/logs";
import { cn } from "@/utils/cn";
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
        <ClearButton dataTestId="clear-logs-button" onClick={clearLogs} />
      </div>
      <div className="overflow-auto flex-1">
        <LogViewer logs={logs} className="min-w-[300px]" />
      </div>
    </>
  );
};

export const LogViewer: React.FC<Props> = ({ logs, className }) => {
  const hover = "opacity-70 group-hover:bg-(--gray-3) group-hover:opacity-100";
  return (
    <div className={cn("flex flex-col", className)}>
      <pre className="grid text-xs font-mono gap-1 whitespace-break-spaces font-semibold align-left">
        <div
          className="grid grid-cols-[30px_1fr]"
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
      <span className="shrink-0 text-(--gray-10) dark:text-(--gray-11)">
        [{timestamp}]
      </span>
      <span className={cn("shrink-0", color)}>{level}</span>
      <span className="shrink-0 text-(--gray-10)">
        (<CellLink cellId={log.cellId} />)
      </span>
      {log.message}
    </>
  );
}

const levelColor: Record<CellLog["level"], string> = {
  stdout: "text-(--grass-9)",
  stderr: "text-(--red-9)",
};
