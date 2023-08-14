/* Copyright 2023 Marimo. All rights reserved. */
import { PlayIcon } from "lucide-react";
import { Button } from "@/editor/inputs/Inputs";
import { Tooltip } from "../../components/ui/tooltip";
import { renderShortcut } from "../../components/shortcuts/renderShortcut";
import { cn } from "../../lib/utils";
import { CellStatus } from "../../core/model/cells";

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
  status: CellStatus;
  needsRun: boolean;
  appClosed: boolean;
  onClick?: () => void;
}): JSX.Element => {
  const { onClick, appClosed, needsRun, status } = props;
  const loading = status === "running" || status === "queued";
  const color = computeColor(appClosed, needsRun, loading);

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
          "RunButton",
          !needsRun && "hover-action",
          (appClosed || loading) && "inactive-button",
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
