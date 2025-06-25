/* Copyright 2025 Marimo. All rights reserved. */

import { XIcon } from "lucide-react";
import { sendShutdown } from "@/core/network/requests";
import { isWasm } from "@/core/wasm/utils";
import { useImperativeModal } from "../../modal/ImperativeModal";
import { AlertDialogDestructiveAction } from "../../ui/alert-dialog";
import { Tooltip } from "../../ui/tooltip";
import { Button } from "../inputs/Inputs";

interface Props {
  description: string;
  disabled?: boolean;
  tooltip?: string;
}

export const ShutdownButton: React.FC<Props> = ({
  description,
  disabled = false,
  tooltip = "Shutdown",
}) => {
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

  return (
    <Tooltip content={tooltip}>
      <Button
        aria-label="Shutdown"
        data-testid="shutdown-button"
        shape="circle"
        size="small"
        color={disabled ? "disabled" : "red"}
        className="h-[27px] w-[27px]"
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          openConfirm({
            title: "Shutdown",
            description: description,
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
