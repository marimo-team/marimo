/* Copyright 2024 Marimo. All rights reserved. */
import { Trash2Icon } from "lucide-react";
import type { RuntimeState } from "@/core/network/types";
import { Tooltip } from "../../ui/tooltip";
import { Button } from "../../ui/button";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";

import type { JSX } from "react";

export const DeleteButton = (props: {
  status: RuntimeState;
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
        // Prevent stealing focus
        // This is needed to delete cells when the cell editor
        // is shown temporarily (e.g. when set to `hidden`)
        onMouseDown={Events.preventFocus}
        className={cn(
          "hover:bg-transparent text-destructive/60 hover:text-destructive",
          (appClosed || loading) && "inactive-button",
        )}
        style={{ boxShadow: "none" }}
      >
        <Trash2Icon size={14} />
      </Button>
    </Tooltip>
  );
};
