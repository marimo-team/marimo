/* Copyright 2024 Marimo. All rights reserved. */
import { Trash2Icon } from "lucide-react";
import { Tooltip } from "../../ui/tooltip";
import { CellStatus } from "../../../core/cells/types";
import { Button } from "../../ui/button";
import { cn } from "../../../utils/cn";

export const DeleteButton = (props: {
  status: CellStatus;
  appClosed: boolean;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
}): JSX.Element => {
  const { status, appClosed, onClick } = props;

  const loading = status === "running" || status === "queued";

  let tooltipMsg = null;
  if (appClosed) {
    tooltipMsg = "App disconnected";
  } else if (status === "running") {
    tooltipMsg = "A cell can't be deleted when it's running";
  } else if (status === "queued") {
    tooltipMsg = "A cell can't be deleted when it's queued to run";
  } else {
    tooltipMsg = "Delete";
  }

  return (
    <Tooltip content={tooltipMsg} usePortal={false}>
      <Button
        variant="ghost"
        size="icon"
        onClick={onClick}
        data-testid="delete-button"
        className={cn(
          "hover:bg-transparent text-destructive/60 hover:text-destructive",
          {
            DeleteButton: true,
            "inactive-button": appClosed || loading,
            running: loading,
          },
        )}
        style={{
          boxShadow: "none",
        }}
      >
        <Trash2Icon size={14} />
      </Button>
    </Tooltip>
  );
};
