/* Copyright 2023 Marimo. All rights reserved. */
import { MoreHorizontalIcon, RefreshCwIcon } from "lucide-react";
import { Tooltip } from "../../components/ui/tooltip";
import { CellStatus } from "../../core/model/cells";
import { useElapsedTime } from "../../hooks/useElapsedTime";

interface Props {
  editing: boolean;
  status: CellStatus;
  edited: boolean;
  interrupted: boolean;
  elapsedTime: number | null;
}

export const CellStatusComponent: React.FC<Props> = ({
  editing,
  status,
  edited,
  interrupted,
  elapsedTime,
}) => {
  if (!editing) {
    return null;
  }

  // Styling: CellStatusIcon visible if queued, running, or needs run.
  //
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
  } else if (status === "queued" && elapsedTime) {
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
          <MoreHorizontalIcon strokeWidth={1.5} />
        </div>
      </Tooltip>
    );
  } else if (edited || interrupted) {
    const title = interrupted
      ? "This cell was interrupted when it was last run"
      : "This cell has been modified since it was last run";
    return (
      <Tooltip content={title} usePortal={false}>
        <div
          className="cell-status-icon cell-status-stale"
          data-testid="cell-status"
        >
          <RefreshCwIcon strokeWidth={1.5} />
        </div>
      </Tooltip>
    );
  } else if (elapsedTime !== null) {
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

const CellTimer = () => {
  const time = useElapsedTime();
  return <span>{formatElapsedTime(time)}</span>;
};
