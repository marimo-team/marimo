/* Copyright 2024 Marimo. All rights reserved. */
import { HardDriveDownloadIcon, PlayIcon } from "lucide-react";
import type { JSX } from "react";
import type { CellConfig, RuntimeState } from "@/core/network/types";
import {
  getConnectionTooltip,
  isAppInteractionDisabled,
} from "@/core/websocket/connection-utils";
import type { WebSocketState } from "@/core/websocket/types";
import { renderShortcut } from "../../shortcuts/renderShortcut";
import { ToolbarItem } from "./toolbar";

function computeColor(
  connectionState: WebSocketState,
  needsRun: boolean,
  loading: boolean,
  inactive: boolean,
) {
  if (isAppInteractionDisabled(connectionState)) {
    return "disabled";
  }
  if (needsRun && !loading) {
    return "stale";
  }
  if (loading || inactive) {
    return "disabled";
  }
  return "green";
}

export const RunButton = (props: {
  edited: boolean;
  status: RuntimeState;
  needsRun: boolean;
  connectionState: WebSocketState;
  config: CellConfig;
  onClick?: () => void;
}): JSX.Element => {
  const { onClick, connectionState, needsRun, status, config, edited } = props;

  const blockedStatus = status === "disabled-transitively";
  const loading = status === "running" || status === "queued";
  const inactive =
    isAppInteractionDisabled(connectionState) ||
    loading ||
    (!config.disabled && blockedStatus && !edited);
  const variant = computeColor(connectionState, needsRun, loading, inactive);

  if (config.disabled) {
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
  if (!config.disabled && blockedStatus && !edited) {
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
  } else if (status === "queued") {
    tooltipMsg = "This cell is already queued to run";
  } else if (status === "running") {
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
