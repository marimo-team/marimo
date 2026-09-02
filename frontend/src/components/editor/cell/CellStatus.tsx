/* Copyright 2026 Marimo. All rights reserved. */
import { formatDistanceToNow } from "date-fns";
import {
  AlertCircleIcon,
  CircleStopIcon,
  ClockIcon,
  Link2OffIcon,
  Loader2Icon,
  PauseIcon,
  PlayIcon,
  RefreshCwIcon,
} from "lucide-react";
import { useDateFormatter } from "react-aria";
import { MultiIcon } from "@/components/icons/multi-icon";
import type {
  CellLastRunOutcome,
  CellSemanticState,
  CellStatusPresentation,
} from "@/core/cells/semantic-state";
import { presentCellStatus } from "@/core/cells/semantic-state";
import { useElapsedTime } from "@/hooks/useElapsedTime";
import { cn } from "@/utils/cn";
import { formatElapsedTime, type Milliseconds, Time } from "@/utils/time";
import { Tooltip } from "../../ui/tooltip";
import "./cell-status.css";

export interface CellStatusComponentProps {
  editing: boolean;
  state: CellSemanticState;
  display?: CellStatusDisplay;
}

export type CellStatusDisplay = "full" | "compact";

export const CellStatusComponent: React.FC<CellStatusComponentProps> = ({
  editing,
  state,
  display = "full",
}) => {
  if (!editing) {
    return null;
  }

  const lastRanTime = state.lastRunStartedAt ? (
    <LastRanTime lastRanTime={state.lastRunStartedAt} />
  ) : null;
  const status = presentCellStatus(state);

  if (
    status.primary === "current" &&
    state.lastRun.kind === "success" &&
    state.lastRun.elapsed !== null
  ) {
    const elapsed = formatElapsedTime(state.lastRun.elapsed);
    return (
      <Tooltip
        content={
          <StatusTooltip
            title={
              <span>
                This cell took <ElapsedTime elapsedTime={elapsed} /> to run
              </span>
            }
            detail={lastRanTime}
          />
        }
        usePortal={true}
      >
        <div
          className={cn(
            "cell-status-duration",
            display === "compact" ? "hover-action-stable" : "hover-action",
          )}
        >
          <span>{elapsed}</span>
        </div>
      </Tooltip>
    );
  }

  if (status.primary === "current") {
    return null;
  }

  const detail =
    status.primary === "running" && state.phase.kind === "running" ? (
      <CellTimer
        startTime={Time.fromSeconds(state.phase.startedAt) || Time.now()}
      />
    ) : status.modifiers.hasError ||
      status.primary === "interrupted" ||
      status.primary === "stopped" ? (
      elapsedDetail(state.lastRun, lastRanTime)
    ) : (
      lastRanTime
    );

  return (
    <StatusIndicator
      state={status.kind}
      label={status.label}
      tooltip={<StatusTooltip title={status.description} detail={detail} />}
      className={cn(`cell-status-${status.tone}`)}
      display={display}
      detail={status.primary === "running" ? detail : undefined}
    >
      <CellStatusIcon status={status} />
    </StatusIndicator>
  );
};

const primaryStatusIcon = (primary: CellStatusPresentation["primary"]) => {
  switch (primary) {
    case "running":
      return <Loader2Icon className="size-4 animate-spin" />;
    case "queued":
      return <ClockIcon className="size-4" />;
    case "paused":
      return <PauseIcon className="size-4" />;
    case "blocked":
      return <Link2OffIcon className="size-4" />;
    case "error":
      return <AlertCircleIcon className="size-4" />;
    case "interrupted":
    case "stopped":
      return <CircleStopIcon className="size-4" />;
    case "not-run":
      return <PlayIcon className="size-4" />;
    case "outdated":
      return <RefreshCwIcon className="size-4" />;
    case "current":
      return null;
  }
};

const CellStatusIcon = ({ status }: { status: CellStatusPresentation }) => {
  const primary = primaryStatusIcon(status.primary);
  const modifier =
    status.modifiers.hasError && status.primary !== "error" ? (
      <AlertCircleIcon className="size-2.5 bg-inherit" />
    ) : status.modifiers.outdated && status.primary !== "outdated" ? (
      <RefreshCwIcon className="size-2.5 bg-inherit" />
    ) : null;

  return modifier ? (
    <MultiIcon>
      {primary}
      {modifier}
    </MultiIcon>
  ) : (
    primary
  );
};

const StatusIndicator = ({
  state,
  label,
  tooltip,
  className,
  display,
  detail,
  children,
}: {
  state: string;
  label: string;
  tooltip: React.ReactNode;
  className: string;
  display: CellStatusDisplay;
  detail?: React.ReactNode;
  children: React.ReactNode;
}) => (
  <Tooltip content={tooltip} usePortal={true}>
    <div
      className={cn("cell-status-indicator", className)}
      data-testid="cell-status"
      data-status={state}
      data-display={display}
      aria-label={label}
      role="status"
      aria-atomic={true}
    >
      <span aria-hidden={true} className="contents">
        {children}
        <span className="cell-status-label">{label}</span>
        {detail}
      </span>
    </div>
  </Tooltip>
);

const StatusTooltip = ({
  title,
  detail,
}: {
  title: React.ReactNode;
  detail?: React.ReactNode;
}) => (
  <div className="flex flex-col gap-1">
    <span>{title}</span>
    {detail}
  </div>
);

function elapsedDetail(
  outcome: CellLastRunOutcome,
  lastRanTime: React.ReactNode,
) {
  if (outcome.kind === "none") {
    return lastRanTime;
  }
  const elapsed =
    outcome.elapsed === null ? null : formatElapsedTime(outcome.elapsed);
  return (
    <>
      {elapsed && (
        <span>
          Previous run took <ElapsedTime elapsedTime={elapsed} />
        </span>
      )}
      {lastRanTime}
    </>
  );
}

export const ElapsedTime = (props: { elapsedTime: string }) => (
  <span className="tracking-wide font-semibold">{props.elapsedTime}</span>
);

const LastRanTime = (props: { lastRanTime: number }) => {
  const date = new Date(props.lastRanTime * 1000);
  const today = new Date();
  const timeFormatter = useDateFormatter({
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    fractionalSecondDigits: 3,
    hour12: true,
  });
  const dateTimeFormatter = useDateFormatter({
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    fractionalSecondDigits: 3,
    hour12: true,
  });
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

const CellTimer = (props: { startTime: Time }) => {
  const time = useElapsedTime(props.startTime.toMilliseconds());
  return (
    <span className="cell-status-timer">{formatLiveElapsedTime(time)}</span>
  );
};

function formatLiveElapsedTime(milliseconds: Milliseconds): string {
  if (milliseconds < 1000) {
    return `${Math.floor(milliseconds / 100) * 100}ms`;
  }
  if (milliseconds < 60_000) {
    return `${(milliseconds / 1000).toFixed(1)}s`;
  }
  return formatElapsedTime(milliseconds);
}
