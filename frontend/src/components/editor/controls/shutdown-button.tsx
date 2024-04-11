/* Copyright 2024 Marimo. All rights reserved. */

import { AlertDialogDestructiveAction } from "../../ui/alert-dialog";
import { Button } from "../inputs/Inputs";
import { Tooltip } from "../../ui/tooltip";
import { useImperativeModal } from "../../modal/ImperativeModal";
import { XIcon } from "lucide-react";
import { sendShutdown } from "@/core/network/requests";

export const ShutdownButton: React.FC<{ description: string }> = (props) => {
  const { openConfirm, closeModal } = useImperativeModal();
  const handleShutdown = () => {
    sendShutdown();
    // Let the shutdown process start before closing the window.
    setTimeout(() => {
      window.close();
    }, 200);
  };

  return (
    <Tooltip content="Shutdown">
      <Button
        aria-label="Shutdown"
        data-testid="shutdown-button"
        shape="circle"
        size="small"
        color="red"
        className="h-[27px] w-[27px]"
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
