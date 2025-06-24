/* Copyright 2024 Marimo. All rights reserved. */

import { XIcon } from "lucide-react";
import { sendShutdown } from "@/core/network/requests";
import { isWasm } from "@/core/wasm/utils";
import { useImperativeModal } from "../../modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "../../ui/alert-dialog";
import { Tooltip } from "../../ui/tooltip";
import { Button } from "../inputs/Inputs";
import {
  getConnectionTooltip,
  isAppInteractionDisabled,
} from "@/core/websocket/connection-utils";
import { WebSocketState } from "@/core/websocket/types";

export const ShutdownButton: React.FC<{
  description: string;
  connectionState: WebSocketState;
}> = (props) => {
  const { openConfirm, closeModal } = useImperativeModal();
  const handleShutdown = () => {
    sendShutdown();
    // Let the shutdown process start before closing the window.
    setTimeout(() => {
      window.close();
    }, 200);
  };

  if (isWasm()) {
    return null;
  }

  const isDisabled = isAppInteractionDisabled(connectionState);
  const tooltipContent = isDisabled ? getConnectionTooltip(connectionState) : "Shutdown";

  return (
    <Tooltip content={tooltipContent}>
      <Button
        aria-label="Shutdown"
        data-testid="shutdown-button"
        shape="circle"
        size="small"
        color={isDisabled ? "disabled" : "red"}
        className="h-[27px] w-[27px]"
        disabled={isDisabled}
        onClick={(e) => {
          e.stopPropagation();
          openConfirm({
            title: "Shutdown",
            description: props.description,
            variant: "destructive",
            confirmAction: (
              <AlertDialogDestructiveAction
                onClick={(e) => {
                  handleShutdown();
                  closeModal();
                }}
                aria-label="Confirm Shutdown"
              >
                Shutdown
              </AlertDialogDestructiveAction>
            ),
          });
        }}
      >
        <XIcon strokeWidth={1} />
      </Button>
    </Tooltip>
  );
};
