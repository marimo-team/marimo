/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { HourglassIcon, LockIcon, UnlinkIcon } from "lucide-react";
import React from "react";
import { Tooltip } from "@/components/ui/tooltip";
import { notebookScrollToRunning } from "@/core/cells/actions";
import { viewStateAtom } from "@/core/mode";
import { type ConnectionStatus, WebSocketState } from "@/core/websocket/types";
import { cn } from "@/utils/cn";

export const StatusOverlay: React.FC<{
  connection: ConnectionStatus;
  isRunning: boolean;
}> = ({ connection, isRunning }) => {
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
        {isClosed && !connection.canTakeover && <DisconnectedIcon />}
        {isClosed && connection.canTakeover && <LockedIcon />}
      </div>
    </>
  );
};

const topLeftStatus = "no-print pointer-events-auto hover:cursor-pointer";

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
  <Tooltip content="Jump to running cell" side="right">
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
