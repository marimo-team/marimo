/* Copyright 2024 Marimo. All rights reserved. */
import {
  BanIcon,
  MoreHorizontalIcon,
  RefreshCwIcon,
  WorkflowIcon,
} from "lucide-react";
import { MultiIcon } from "@/components/icons/multi-icon";
import { Logger } from "@/utils/Logger";
import type { CellRuntimeState } from "../../../core/cells/types";
import { useElapsedTime } from "../../../hooks/useElapsedTime";
import { Tooltip } from "../../ui/tooltip";

import "./cell-status.css";
import { formatDistanceToNow } from "date-fns";
import { Time } from "@/utils/time";

export interface CellStatusComponentProps
  extends Pick<
    CellRuntimeState,
    "status" | "runStartTimestamp" | "interrupted" | "lastRunStartTimestamp"
  > {
  editing: boolean;
  edited: boolean;
  disabled: boolean;
  staleInputs: boolean;
  elapsedTime: number | null;
  uninstantiated: boolean;
}

// Looks like HH:MM:SS.SSS AM/PM
const timeFormatter = new Intl.DateTimeFormat("en-US", {
  hour: "numeric",
  minute: "numeric",
  second: "numeric",
  fractionalSecondDigits: 3,
  hour12: true,
});

// Looks like MM/DD HH:MM:SS.SSS AM/PM
const dateTimeFormatter = new Intl.DateTimeFormat("en-US", {
  month: "numeric",
  day: "numeric",
  hour: "numeric",
  minute: "numeric",
  second: "numeric",
  fractionalSecondDigits: 3,
  hour12: true,
});

export const CellStatusComponent: React.FC<CellStatusComponentProps> = ({
  editing,
  status,
  disabled,
  staleInputs,
  edited,
  interrupted,
  elapsedTime,
  runStartTimestamp,
  lastRunStartTimestamp,
  uninstantiated,
}) => {
  if (!editing) {
    return null;
  }

  const start = runStartTimestamp ?? lastRunStartTimestamp;
  const lastRanTime = start ? <LastRanTime lastRanTime={start} /> : null;

  // unexpected states
  if (disabled && status === "running") {
    Logger.error("CellStatusComponent: disabled and running");
    return null;
  }

  // stale and disabled by self
  if (disabled && staleInputs) {
    return (
      <Tooltip
        content={
          <div className="flex flex-col gap-1">
            <span>This cell is stale, but it's disabled and can't be run</span>
            {lastRanTime}
          </div>
        }
        usePortal={true}
      >
        <div
          className="cell-status-icon cell-status-stale"
          data-testid="cell-status"
          data-status="stale"
        >
          <MultiIcon>
            <BanIcon className="h-5 w-5" strokeWidth={1.5} />
            <RefreshCwIcon className="h-3 w-3" strokeWidth={2.5} />
          </MultiIcon>
        </div>
      </Tooltip>
    );
  }

  // disabled, but not stale
  if (disabled) {
    return (
      <Tooltip
        content={
          <div className="flex flex-col gap-1">
            <span>This cell is disabled</span>
            {lastRanTime}
          </div>
        }
        usePortal={true}
      >
        <div
          className="cell-status-icon cell-status-disabled"
          data-testid="cell-status"
          data-status="disabled"
        >
          <BanIcon className="h-5 w-5" strokeWidth={1.5} />
        </div>
      </Tooltip>
    );
  }

  // disabled from parent
  if (!staleInputs && status === "disabled-transitively") {
    return (
      <Tooltip
        content={
          <div className="flex flex-col gap-1">
            <span>
              An ancestor of this cell is disabled, so it can't be run
            </span>
            {lastRanTime}
          </div>
        }
        usePortal={true}
      >
        <div
          className="cell-status-icon cell-status-stale"
          data-testid="cell-status"
          data-status="disabled-transitively"
        >
          <MultiIcon layerTop={true}>
            <WorkflowIcon className="h-5 w-5" strokeWidth={1.5} />
            <BanIcon className="h-3 w-3" strokeWidth={2.5} />
          </MultiIcon>
        </div>
      </Tooltip>
    );
  }

  // stale from parent being disabled
  if (staleInputs && status === "disabled-transitively") {
    return (
      <Tooltip
        content={
          <div className="flex flex-col gap-1">
            <span>
              This cell is stale, but an ancestor is disabled so it can't be run
            </span>
            {lastRanTime}
          </div>
        }
        usePortal={true}
      >
        <div
          className="cell-status-icon cell-status-stale"
          data-testid="cell-status"
          data-status="stale"
        >
          <MultiIcon>
            <RefreshCwIcon className="h-5 w-5" strokeWidth={1} />
            <BanIcon className="h-3 w-3" strokeWidth={2.5} />
          </MultiIcon>
        </div>
      </Tooltip>
    );
  }

  // running & queued icons get priority over edited/interrupted
  if (status === "running") {
    return (
      <Tooltip
        content={
          <div className="flex flex-col gap-1">
            <span>This cell is running</span>
            {lastRanTime}
          </div>
        }
        usePortal={true}
      >
        <div
          className={"cell-status-icon elapsed-time running"}
          data-testid="cell-status"
          data-status="running"
        >
          <CellTimer
            startTime={Time.fromSeconds(runStartTimestamp) || Time.now()}
          />
        </div>
      </Tooltip>
    );
  }

  // queued
  if (status === "queued") {
    return (
      <Tooltip
        content={
          <div className="flex flex-col gap-1">
            <span>This cell is queued to run</span>
            {lastRanTime}
          </div>
        }
        usePortal={true}
      >
        <div
          className="cell-status-icon cell-status-queued"
          data-testid="cell-status"
          data-status="queued"
        >
          <MoreHorizontalIcon className="h-5 w-5" strokeWidth={1.5} />
        </div>
      </Tooltip>
    );
  }

  // outdated: cell needs to be re-run
  if (edited || interrupted || staleInputs || uninstantiated) {
    const elapsedTimeStr = formatElapsedTime(elapsedTime);
    const elapsedTimeComponent = elapsedTime ? (
      <ElapsedTime elapsedTime={elapsedTimeStr} />
    ) : null;

    // Customize tooltips based on why the cell needs to be re-run
    let title = "";
    let timerTitle: React.ReactNode = "";

    if (uninstantiated) {
      title = "This cell has not yet been run";
    } else if (interrupted) {
      title = "This cell was interrupted when it was last run";
      timerTitle = (
        <span>
          This cell ran for {elapsedTimeComponent} before being interrupted
        </span>
      );
    } else if (edited) {
      title = "This cell has been modified since it was last run";
      timerTitle = <span>This cell took {elapsedTimeComponent} to run</span>;
    } else {
      // staleInputs
      title = "This cell has not been run with the latest inputs";
      timerTitle = <span>This cell took {elapsedTimeComponent} to run</span>;
    }

    return (
      <div className="cell-status-icon flex items-center gap-2">
        <Tooltip content={title} usePortal={true}>
          <div
            className="cell-status-stale"
            data-testid="cell-status"
            data-status="outdated"
          >
            <RefreshCwIcon className="h-5 w-5" strokeWidth={1.5} />
          </div>
        </Tooltip>
        {elapsedTime && (
          <Tooltip
            content={
              <div className="flex flex-col gap-1">
                {timerTitle}
                {lastRanTime}
              </div>
            }
            usePortal={true}
          >
            <div
              className={"elapsed-time hover-action"}
              data-testid="cell-status"
              data-status="outdated"
            >
              <span>{elapsedTimeStr}</span>
            </div>
          </Tooltip>
        )}
      </div>
    );
  }

  // either running or finished
  if (elapsedTime !== null) {
    const elapsedTimeStr = formatElapsedTime(elapsedTime);
    const elapsedTimeComponent = elapsedTime ? (
      <ElapsedTime elapsedTime={elapsedTimeStr} />
    ) : null;

    return (
      <Tooltip
        content={
          <div className="flex flex-col gap-1">
            <span>This cell took {elapsedTimeComponent} to run</span>
            {lastRanTime}
          </div>
        }
        usePortal={true}
      >
        <div
          className={"cell-status-icon elapsed-time hover-action"}
          data-testid="cell-status"
          data-status="idle"
        >
          <span>{elapsedTimeStr}</span>
        </div>
      </Tooltip>
    );
  }

  // default
  return null;
};

export const ElapsedTime = (props: { elapsedTime: string }) => {
  return (
    <span className="tracking-wide font-semibold">{props.elapsedTime}</span>
  );
};
const LastRanTime = (props: { lastRanTime: number }) => {
  const date = new Date(props.lastRanTime * 1000);
  const today = new Date();
  const formatter =
    date.toDateString() === today.toDateString()
      ? timeFormatter
      : dateTimeFormatter;
  return (
    <span>
      Ran at{" "}
      <strong className="tracking-wide font-semibold">
        {formatter.format(date)}
      </strong>{" "}
      <span className="text-muted-foreground">
        ({formatDistanceToNow(date)} ago)
      </span>
    </span>
  );
};

export function formatElapsedTime(elapsedTime: number | null) {
  if (elapsedTime === null) {
    return "";
  }

  const milliseconds = elapsedTime;
  const seconds = milliseconds / 1000;

  if (seconds >= 60) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes}m${remainingSeconds}s`;
  }
  if (seconds >= 1) {
    return `${seconds.toFixed(2).toString()}s`;
  }
  return `${milliseconds.toFixed(0).toString()}ms`;
}

const CellTimer = (props: { startTime: Time }) => {
  const time = useElapsedTime(props.startTime.toMilliseconds());
  return <span>{formatElapsedTime(time)}</span>;
};
