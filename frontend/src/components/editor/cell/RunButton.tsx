/* Copyright 2026 Marimo. All rights reserved. */
import { HardDriveDownloadIcon, PlayIcon } from "lucide-react";
import type { JSX } from "react";
import type { CellSemanticState } from "@/core/cells/semantic-state";
import {
  getConnectionTooltip,
  isAppInteractionDisabled,
} from "@/core/websocket/connection-utils";
import type { WebSocketState } from "@/core/websocket/types";
import { renderShortcut } from "../../shortcuts/renderShortcut";
import { ToolbarItem } from "./toolbar";

function computeColor({
  connectionState,
  needsRun,
  loading,
  inactive,
}: {
  connectionState: WebSocketState;
  needsRun: boolean;
  loading: boolean;
  inactive: boolean;
}) {
  if (isAppInteractionDisabled(connectionState)) {
    return "disabled";
  }
  if (needsRun && !loading) {
    return "active";
  }
  if (loading || inactive) {
    return "disabled";
  }
  return "green";
}

export const RunButton = (props: {
  state: CellSemanticState;
  connectionState: WebSocketState;
  onClick?: () => void;
}): JSX.Element => {
  const { onClick, connectionState, state } = props;

  const blocked = state.availability.kind === "blocked";
  const paused = state.availability.kind === "paused";
  const loading =
    state.phase.kind === "running" || state.phase.kind === "queued";
  const inactive =
    isAppInteractionDisabled(connectionState) ||
    loading ||
    (blocked && !state.codeEdited);
  const variant = computeColor({
    connectionState,
    needsRun: state.needsRun,
    loading,
    inactive,
  });

  if (paused) {
    return (
      <ToolbarItem
        tooltip="Add code to notebook"
        disabled={inactive}
        onClick={onClick}
        variant={variant}
        data-testid="run-button"
      >
        <HardDriveDownloadIcon />
      </ToolbarItem>
    );
  }
  if (blocked) {
    return (
      <ToolbarItem
        disabled={inactive}
        tooltip="This cell can't be run because it has a disabled ancestor"
        onClick={onClick}
        variant={variant}
        data-testid="run-button"
      >
        <PlayIcon strokeWidth={1.2} />
      </ToolbarItem>
    );
  }

  let tooltipMsg: React.ReactNode = "";

  if (isAppInteractionDisabled(connectionState)) {
    tooltipMsg = getConnectionTooltip(connectionState);
  } else if (state.phase.kind === "queued") {
    tooltipMsg = "This cell is already queued to run";
  } else if (state.phase.kind === "running") {
    tooltipMsg = "This cell is already running.";
  } else {
    tooltipMsg = renderShortcut("cell.run");
  }

  return (
    <ToolbarItem
      tooltip={tooltipMsg}
      disabled={inactive}
      onClick={onClick}
      variant={variant}
      data-testid="run-button"
    >
      <PlayIcon strokeWidth={1.2} />
    </ToolbarItem>
  );
};
