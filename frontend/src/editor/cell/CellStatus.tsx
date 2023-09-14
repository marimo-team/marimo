/* Copyright 2023 Marimo. All rights reserved. */
import { BanIcon, MoreHorizontalIcon, RefreshCwIcon } from "lucide-react";
import { Tooltip } from "../../components/ui/tooltip";
import { CellStatus } from "../../core/model/cells";
import { useElapsedTime } from "../../hooks/useElapsedTime";
import { Logger } from "@/utils/Logger";
import { MultiIcon } from "@/components/icons/multi-icon";

import "./cell-status.css";

export interface CellStatusComponentProps {
  editing: boolean;
  status: CellStatus;
  edited: boolean;
  interrupted: boolean;
  disabled: boolean;
  elapsedTime: number | null;
}

export const CellStatusComponent: React.FC<CellStatusComponentProps> = ({
  editing,
  status,
  disabled,
  edited,
  interrupted,
  elapsedTime,
}) => {
  if (!editing) {
    return null;
  }

  // unexpected states
  if (disabled && status === "running") {
    Logger.error("CellStatusComponent: disabled and running");
    return null;
  }

  // Styling: CellStatusIcon visible if queued, running, or needs run.
  const maybeRenderRunningStatus = () => {

    // don't show previous timer if disabled
    if (disabled || status === 'stale') {
      return null;
    }

    // running & queued icons get priority over edited/interrupted
    if (status === "running") {
      return (
        <Tooltip content={"This cell is running"} usePortal={false}>
          <div
            className={"cell-status-icon elapsed-time running"}
            data-testid="cell-status"
          >
            <CellTimer />
          </div>
        </Tooltip>
      );
    }

    // queued
    if (status === "queued" && elapsedTime) {
      // If elapsed time < 16ms (60fps), don't show the elapsed time,
      // otherwise it will flicker.
      if (elapsedTime < 16) {
        return null;
      }
      return (
        <Tooltip content={"This cell is queued to run"} usePortal={false}>
          <div
            className="cell-status-icon cell-status-queued"
            data-testid="cell-status"
          >
            <MoreHorizontalIcon
              className="h-4 w-4"
              strokeWidth={1.5} />
          </div>
        </Tooltip>
      );
    }

    // outdated
    if (edited || interrupted) {
      const title = interrupted
        ? "This cell was interrupted when it was last run"
        : "This cell has been modified since it was last run";
      return (
        <Tooltip content={title} usePortal={false}>
          <div
            className="cell-status-icon cell-status-stale"
            data-testid="cell-status"
          >
            <RefreshCwIcon
              className="h-4 w-4"
              strokeWidth={1.5} />
          </div>
        </Tooltip>
      );
    }

    // either running or finished
    if (elapsedTime !== null) {
      const elapsedTimeStr = formatElapsedTime(elapsedTime);
      return (
        <Tooltip
          content={`This cell took ${elapsedTimeStr} to run`}
          usePortal={false}
        >
          <div
            className={"cell-status-icon elapsed-time hover-action"}
            data-testid="cell-status"
          >
            <span>{elapsedTimeStr}</span>
          </div>
        </Tooltip>
      );
    }
  }

  const maybeRenderDisabledStatus = () => {
    // disabled, but not stale
    if (disabled) {
      return (
        <Tooltip content={"This cell is disabled"} usePortal={false}>
          <div
            className="cell-status-icon cell-status-disabled"
            data-testid="cell-status"
          >
            <BanIcon
              className="h-4 w-4"
              strokeWidth={1.5} />
          </div>
        </Tooltip>
      );
    }


    // stale and disabled from self (not reached, case maybe added later)
    if (disabled && status === "stale") {
      return (
        <Tooltip content={"This cell is disabled and has received new inputs since it's last run"} usePortal={false}>
          <div
            className="cell-status-icon cell-status-stale"
            data-testid="cell-status"
          >
            <MultiIcon>
              <RefreshCwIcon
                className="h-4 w-4"
                stroke="var(--amber-11)"
                strokeWidth={1.5} />
              <BanIcon
                className="h-2 w-2"
                stroke="var(--amber-11)"
                strokeWidth={2.5} />
            </MultiIcon>
          </div>
        </Tooltip>
      );
    }

    // stale from parent being disabled
    if (status === "stale") {
      return (
        <Tooltip content={"This cell is stale. One or more parents are disabled so this has not been run"} usePortal={false}>
          <div
            className="cell-status-icon cell-status-stale"
            data-testid="cell-status"
          >
            <MultiIcon>
              <RefreshCwIcon
                className="h-4 w-4"
                strokeWidth={1.5} />
              <BanIcon
                className="h-2 w-2"
                strokeWidth={2.5} />
            </MultiIcon>
          </div>
        </Tooltip>
      );
    }

    return null;
  }


  return <div className="flex flex-col gap-1">
    {maybeRenderDisabledStatus()}
    {maybeRenderRunningStatus()}
  </div>;
};

function formatElapsedTime(elapsedTime: number | null) {
  if (elapsedTime === null) {
    return "";
  }

  if (elapsedTime > 1000 * 60) {
    const minutes = (elapsedTime / (1000 * 60)).toFixed(0);
    const seconds = ((elapsedTime % (1000 * 60)) / 1000).toFixed(0);
    return `${minutes.toString()}m${seconds.toString()}s`;
  } else if (elapsedTime > 1000) {
    return `${(elapsedTime / 1000).toFixed(2).toString()}s`;
  } else {
    return `${elapsedTime.toFixed(0).toString()}ms`;
  }
}

const CellTimer = () => {
  const time = useElapsedTime();
  return <span>{formatElapsedTime(time)}</span>;
};
