/* Copyright 2024 Marimo. All rights reserved. */
import {
  BanIcon,
  MoreHorizontalIcon,
  WorkflowIcon,
  RefreshCwIcon,
} from "lucide-react";
import { Tooltip } from "../../ui/tooltip";
import { CellRuntimeState } from "../../../core/cells/types";
import { useElapsedTime } from "../../../hooks/useElapsedTime";
import { Logger } from "@/utils/Logger";
import { MultiIcon } from "@/components/icons/multi-icon";

import "./cell-status.css";
import { Time } from "@/utils/time";

export interface CellStatusComponentProps
  extends Pick<
    CellRuntimeState,
    "status" | "runStartTimestamp" | "interrupted"
  > {
  editing: boolean;
  edited: boolean;
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
  runStartTimestamp,
}) => {
  if (!editing) {
    return null;
  }

  // unexpected states
  if (disabled && status === "running") {
    Logger.error("CellStatusComponent: disabled and running");
    return null;
  }
  // stale and disabled by self
  if (disabled && status === "stale") {
    return (
      <Tooltip
        content={"This cell is stale, but it's disabled and can't be run"}
        usePortal={false}
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
      <Tooltip content={"This cell is disabled"} usePortal={false}>
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
  if (status === "disabled-transitively") {
    return (
      <Tooltip
        content={"An ancestor of this cell is disabled, so it can't be run"}
        usePortal={false}
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
  if (status === "stale") {
    return (
      <Tooltip
        content={
          "This cell is stale, but an ancestor is disabled so it can't be run"
        }
        usePortal={false}
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
      <Tooltip content={"This cell is running"} usePortal={false}>
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
      <Tooltip content={"This cell is queued to run"} usePortal={false}>
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

  // outdated
  if (edited || interrupted) {
    const elapsedTimeStr = formatElapsedTime(elapsedTime);
    const title = interrupted
      ? "This cell was interrupted when it was last run"
      : "This cell has been modified since it was last run";
    const timerTitle = interrupted
      ? `This cell ran for ${elapsedTimeStr} before being interrupted`
      : `This cell took ${elapsedTimeStr} to run`;
    return (
      <div className="cell-status-icon flex items-center gap-2">
        <Tooltip content={title} usePortal={false}>
          <div
            className="cell-status-stale"
            data-testid="cell-status"
            data-status="outdated"
          >
            <RefreshCwIcon className="h-5 w-5" strokeWidth={1.5} />
          </div>
        </Tooltip>
        {elapsedTimeStr && (
          <Tooltip content={timerTitle} usePortal={false}>
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
    return (
      <Tooltip
        content={`This cell took ${elapsedTimeStr} to run`}
        usePortal={false}
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

const CellTimer = (props: { startTime: Time }) => {
  const time = useElapsedTime(props.startTime.toMilliseconds());
  return <span>{formatElapsedTime(time)}</span>;
};
