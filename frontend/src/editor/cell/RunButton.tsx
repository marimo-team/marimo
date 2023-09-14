/* Copyright 2023 Marimo. All rights reserved. */
import { HardDriveDownloadIcon, PlayIcon } from "lucide-react";
import { Button } from "@/editor/inputs/Inputs";
import { Tooltip } from "../../components/ui/tooltip";
import { renderShortcut } from "../../components/shortcuts/renderShortcut";
import { cn } from "../../lib/utils";
import { CellConfig, CellStatus } from "../../core/model/cells";

function computeColor(appClosed: boolean, needsRun: boolean, loading: boolean) {
  if (appClosed) {
    return "disabled";
  } else if (needsRun && !loading) {
    return "yellow";
  } else if (loading) {
    return "disabled";
  } else {
    return "hint-green";
  }
}
export const RunButton = (props: {
  edited: boolean;
  status: CellStatus;
  needsRun: boolean;
  appClosed: boolean;
  config: CellConfig;
  onClick?: () => void;
}): JSX.Element => {
  const { onClick, appClosed, needsRun, status, config, edited } = props;

  const loading = status === "running" || status === "queued";
  const inactive = appClosed || loading;
  const color = computeColor(appClosed, needsRun, loading);


  if (config.disabled || (status === "stale" && !edited)) {
    return <Tooltip content="Add code to notebook" usePortal={false}>
      <Button
        className={cn(
          !needsRun && "hover-action",
          inactive && "inactive-button",
        )}
        onClick={onClick}
        color={color}
        shape="circle"
        size="small"
        data-testid="run-button"
      >
        <HardDriveDownloadIcon strokeWidth={1.8} />
      </Button>
    </Tooltip>
  }

  let tooltipMsg: React.ReactNode = "";
  if (appClosed) {
    tooltipMsg = "App disconnected";
  } else if (status === "running") {
    tooltipMsg = "This cell is already running";
  } else if (status === "queued") {
    tooltipMsg = "This cell is already queued to run";
  } else {
    tooltipMsg = renderShortcut("cell.run");
  }

  return (
    <Tooltip content={tooltipMsg} usePortal={false}>
      <Button
        className={cn(
          !needsRun && "hover-action",
          inactive && "inactive-button",
          loading && "running"
        )}
        onClick={onClick}
        color={color}
        shape="circle"
        size="small"
        data-testid="run-button"
      >
        <PlayIcon strokeWidth={1.8} />
      </Button>
    </Tooltip>
  );
};
