/* Copyright 2024 Marimo. All rights reserved. */
import { Tooltip } from "@/components/ui/tooltip";
import { notebookScrollToRunning } from "@/core/cells/actions";
import { type ConnectionStatus, WebSocketState } from "@/core/websocket/types";
import { UnlinkIcon, HourglassIcon, LockIcon } from "lucide-react";
import React from "react";

export const StatusOverlay: React.FC<{
  connection: ConnectionStatus;
  isRunning: boolean;
}> = ({ connection, isRunning }) => {
  return (
    <>
      {connection.state === WebSocketState.OPEN && isRunning && <RunningIcon />}
      {connection.state === WebSocketState.CLOSED &&
        !connection.canTakeover && <NoiseBackground />}
      {connection.state === WebSocketState.CLOSED &&
        !connection.canTakeover && <DisconnectedIcon />}
      {connection.state === WebSocketState.CLOSED && connection.canTakeover && (
        <LockedIcon />
      )}
    </>
  );
};

const topLeftStatus =
  "fixed top-8 left-8 ml-4 flex items-center space-x-3 min-h-[28px] no-print pointer-events-auto z-50 hover:cursor-pointer";

const DisconnectedIcon = () => (
  <Tooltip content="App disconnected">
    <div className={topLeftStatus}>
      <UnlinkIcon className="w-[25px] h-[25px] text-[var(--red-11)]" />
    </div>
  </Tooltip>
);

const LockedIcon = () => (
  <Tooltip content="Notebook locked">
    <div className={topLeftStatus}>
      <LockIcon className="w-[25px] h-[25px] text-[var(--blue-11)]" />
    </div>
  </Tooltip>
);

const RunningIcon = () => (
  <Tooltip content={"Jump to running cell"} side="right">
    <div
      className={topLeftStatus}
      data-testid="loading-indicator"
      onClick={notebookScrollToRunning}
    >
      <HourglassIcon className="running-app-icon" size={30} strokeWidth={1} />
    </div>
  </Tooltip>
);

const NoiseBackground = () => (
  <>
    <div className="noise" />
    <div className="disconnected-gradient" />
  </>
);
