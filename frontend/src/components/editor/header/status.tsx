/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { HourglassIcon, LockIcon, UnlinkIcon } from "lucide-react";
import React from "react";
import { Tooltip } from "@/components/ui/tooltip";
import { notebookScrollToRunning } from "@/core/cells/actions";
import { onlyScratchpadIsRunningAtom } from "@/core/cells/cells";
import { viewStateAtom } from "@/core/mode";
import { type ConnectionStatus, WebSocketState } from "@/core/websocket/types";
import { cn } from "@/utils/cn";

export const StatusOverlay: React.FC<{
  connection: ConnectionStatus;
  isRunning: boolean;
  onReconnect?: () => void;
}> = ({ connection, isRunning, onReconnect }) => {
  const { mode } = useAtomValue(viewStateAtom);
  const isClosed = connection.state === WebSocketState.CLOSED;
  const isOpen = connection.state === WebSocketState.OPEN;

  return (
    <>
      {isClosed && !connection.canTakeover && <NoiseBackground />}
      <div
        className={cn(
          "z-50 top-4 left-4",
          mode === "read" ? "fixed" : "absolute",
        )}
      >
        {isOpen && isRunning && <RunningIcon />}
        {isClosed && !connection.canTakeover && (
          <DisconnectedIcon onReconnect={onReconnect} />
        )}
        {isClosed && connection.canTakeover && <LockedIcon />}
      </div>
    </>
  );
};

const topLeftStatus = "print:hidden pointer-events-auto hover:cursor-pointer";

const DisconnectedIcon: React.FC<{ onReconnect?: () => void }> = ({
  onReconnect,
}) => (
  <Tooltip
    content={
      onReconnect ? "App disconnected — click to reconnect" : "App disconnected"
    }
  >
    <button
      type="button"
      className={cn(topLeftStatus, "bg-transparent border-0 p-0")}
      aria-label={onReconnect ? "Reconnect to app" : "App disconnected"}
      data-testid="disconnected-indicator"
      onClick={onReconnect}
      disabled={!onReconnect}
    >
      <UnlinkIcon className="w-[25px] h-[25px] text-(--red-11)" />
    </button>
  </Tooltip>
);

const LockedIcon = () => (
  <Tooltip content="Notebook locked">
    <div className={topLeftStatus}>
      <LockIcon className="w-[25px] h-[25px] text-(--blue-11)" />
    </div>
  </Tooltip>
);

const RunningIcon = () => {
  const scratchpadOnly = useAtomValue(onlyScratchpadIsRunningAtom);
  const tooltip = scratchpadOnly
    ? "Scratchpad is running"
    : "Jump to running cell";

  return (
    <Tooltip content={tooltip} side="right">
      <div
        className={topLeftStatus}
        data-testid="loading-indicator"
        onClick={scratchpadOnly ? undefined : notebookScrollToRunning}
      >
        <HourglassIcon className="running-app-icon" size={30} strokeWidth={1} />
      </div>
    </Tooltip>
  );
};

const NoiseBackground = () => (
  <>
    <div className="noise" />
    <div className="disconnected-gradient" />
  </>
);
