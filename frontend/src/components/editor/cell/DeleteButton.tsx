/* Copyright 2024 Marimo. All rights reserved. */
import { Trash2Icon } from "lucide-react";
import type { RuntimeState } from "@/core/network/types";
import { ToolbarItem } from "./toolbar";

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
    <ToolbarItem
      tooltip={tooltipMsg}
      onClick={onClick}
      data-testid="delete-button"
      disabled={appClosed || loading}
      variant="danger"
    >
      <Trash2Icon size={14} />
    </ToolbarItem>
  );
};
