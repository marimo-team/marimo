/* Copyright 2024 Marimo. All rights reserved. */
import { Tooltip } from "@/components/ui/tooltip";
import { notebookScrollToRunning } from "@/core/cells/actions";
import { type AppMode, viewStateAtom } from "@/core/mode";
import { type ConnectionStatus, WebSocketState } from "@/core/websocket/types";
import { cn } from "@/utils/cn";
import { useAtomValue } from "jotai";
import { UnlinkIcon, HourglassIcon, LockIcon } from "lucide-react";
import React from "react";

export const StatusOverlay: React.FC<{
  connection: ConnectionStatus;
  isRunning: boolean;
}> = ({ connection, isRunning }) => {
  const { mode } = useAtomValue(viewStateAtom);
  return (
    <>
      {connection.state === WebSocketState.OPEN && isRunning && (
        <RunningIcon mode={mode} />
      )}
      {connection.state === WebSocketState.CLOSED &&
        !connection.canTakeover && <NoiseBackground />}
      {connection.state === WebSocketState.CLOSED &&
        !connection.canTakeover && <DisconnectedIcon mode={mode} />}
      {connection.state === WebSocketState.CLOSED && connection.canTakeover && (
        <LockedIcon mode={mode} />
      )}
    </>
  );
};

const topLeftStatus = (mode: AppMode) =>
  cn(
    "flex items-center space-x-3 min-h-[28px] no-print pointer-events-auto z-50 hover:cursor-pointer",
    mode === "edit" ? "absolute top-4 left-4 m-0" : "fixed top-8 left-8 ml-4",
  );

const DisconnectedIcon = ({ mode }: { mode: AppMode }) => (
  <Tooltip content="App disconnected">
    <div className={topLeftStatus(mode)}>
      <UnlinkIcon className="w-[25px] h-[25px] text-[var(--red-11)]" />
    </div>
  </Tooltip>
);

const LockedIcon = ({ mode }: { mode: AppMode }) => (
  <Tooltip content="Notebook locked">
    <div className={topLeftStatus(mode)}>
      <LockIcon className="w-[25px] h-[25px] text-[var(--blue-11)]" />
    </div>
  </Tooltip>
);

const RunningIcon = ({ mode }: { mode: AppMode }) => (
  <Tooltip content={"Jump to running cell"} side="right">
    <div
      className={topLeftStatus(mode)}
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
