/* Copyright 2024 Marimo. All rights reserved. */
import { Tooltip } from "@/components/ui/tooltip";
import { notebookScrollToRunning } from "@/core/cells/actions";
import { WebSocketState } from "@/core/websocket/types";
import { UnlinkIcon, HourglassIcon } from "lucide-react";
import React from "react";

export const StatusOverlay: React.FC<{
  state: WebSocketState;
  isRunning: boolean;
}> = ({ state, isRunning }) => {
  return (
    <>
      {state === WebSocketState.OPEN && isRunning && <RunningIcon />}
      {state === WebSocketState.CLOSED && <NoiseBackground />}
      {state === WebSocketState.CLOSED && <DisconnectedIcon />}
    </>
  );
};

const topLeftStatus =
  "absolute top-4 left-4 m-0 ml-8 flex items-center space-x-3 min-h-[28px] no-print pointer-events-auto z-50";

const DisconnectedIcon = () => (
  <Tooltip content="App disconnected">
    <div className={topLeftStatus}>
      <UnlinkIcon className="closed-app-icon" />
    </div>
  </Tooltip>
);

// TODO: click cursor on hover, tooltip about going to running cell
const RunningIcon = () => (
  <div
    className={topLeftStatus}
    data-testid="loading-indicator"
    title={"Marimo is busy computing. Hang tight!"}
    onClick={notebookScrollToRunning}
  >
    <HourglassIcon className="running-app-icon" size={30} strokeWidth={1} />
  </div>
);

const NoiseBackground = () => (
  <>
    <div className="noise" />
    <div className="disconnected-gradient" />
  </>
);
