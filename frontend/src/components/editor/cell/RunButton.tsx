/* Copyright 2024 Marimo. All rights reserved. */
import { HardDriveDownloadIcon, PlayIcon } from "lucide-react";
import { renderShortcut } from "../../shortcuts/renderShortcut";
import type { RuntimeState, CellConfig } from "@/core/network/types";
import { ToolbarItem } from "./toolbar";

import type { JSX } from "react";

function computeColor(
  appClosed: boolean,
  needsRun: boolean,
  loading: boolean,
  inactive: boolean,
) {
  if (appClosed) {
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
  appClosed: boolean;
  config: CellConfig;
  onClick?: () => void;
}): JSX.Element => {
  const { onClick, appClosed, needsRun, status, config, edited } = props;

  const blockedStatus = status === "disabled-transitively";
  const loading = status === "running" || status === "queued";
  const inactive =
    appClosed || loading || (!config.disabled && blockedStatus && !edited);
  const variant = computeColor(appClosed, needsRun, loading, inactive);

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
  if (appClosed) {
    tooltipMsg = "App disconnected";
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
