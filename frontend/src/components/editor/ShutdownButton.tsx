/* Copyright 2024 Marimo. All rights reserved. */

import { AlertDialogDestructiveAction } from "../ui/alert-dialog";
import { Button } from "./inputs/Inputs";
import { Tooltip } from "../ui/tooltip";
import { useImperativeModal } from "../modal/ImperativeModal";
import { XIcon } from "lucide-react";

interface ShutdownButtonProps {
  onShutdown: (e: React.MouseEvent<HTMLButtonElement>) => void;
}

export const ShutdownButton = ({
  onShutdown,
}: ShutdownButtonProps): JSX.Element => {
  const { openConfirm, closeModal } = useImperativeModal();

  return (
    <Tooltip content="Shutdown">
      <Button
        aria-label="Shutdown"
        shape="circle"
        size="small"
        color="red"
        className="h-[27px] w-[27px]"
        onClick={(e) => {
          e.stopPropagation();
          openConfirm({
            title: "Shutdown",
            description:
              "This will terminate the Python kernel. You'll lose all data that's in memory.",
            variant: "destructive",
            confirmAction: (
              <AlertDialogDestructiveAction
                onClick={(e) => {
                  onShutdown(e);
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
