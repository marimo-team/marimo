/* Copyright 2024 Marimo. All rights reserved. */
import { XIcon } from "lucide-react";

import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogDestructiveAction,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "../ui/alert-dialog";
import { Button } from "./inputs/Inputs";
import { Tooltip } from "../ui/tooltip";

interface ShutdownButtonProps {
  onShutdown: (e: React.MouseEvent<HTMLButtonElement>) => void;
}

export const ShutdownButton = ({
  onShutdown,
}: ShutdownButtonProps): JSX.Element => {
  return (
    <AlertDialog>
      <Tooltip content="Shutdown">
        <AlertDialogTrigger asChild={true}>
          <Button
            aria-label="Shutdown"
            shape="circle"
            size="small"
            color="red"
            className="h-[27px] w-[27px]"
          >
            <XIcon strokeWidth={1} />
          </Button>
        </AlertDialogTrigger>
      </Tooltip>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="text-destructive">
            Shutdown?
          </AlertDialogTitle>
          <AlertDialogDescription>
            This will terminate the Python kernel. You'll lose all data that's
            in memory.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogDestructiveAction
            onClick={onShutdown}
            aria-label="Confirm Shutdown"
          >
            Shutdown
          </AlertDialogDestructiveAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
