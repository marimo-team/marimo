/* Copyright 2023 Marimo. All rights reserved. */
import { prettyError } from "@/utils/errors";
import { useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/utils/cn";

export const ErrorBanner = ({
  error,
  className,
}: {
  error: Error | string;
  className?: string;
}) => {
  const [open, setOpen] = useState(false);

  if (!error) {
    return null;
  }

  const message = prettyError(error);

  return (
    <>
      <div
        className={cn(
          "text-error border-[var(--red-6)] bg-[var(--red-2)] text-sm p-2 border cursor-pointer hover:bg-[var(--red-3)] whitespace-pre-wrap",
          className
        )}
        onClick={() => setOpen(true)}
      >
        <span className="line-clamp-4">{message}</span>
      </div>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent className="max-w-[80%]">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-error">Error</AlertDialogTitle>
          </AlertDialogHeader>
          <div className="text-error text-sm p-2 font-mono">{message}</div>
          <AlertDialogFooter>
            <AlertDialogAction autoFocus={true} onClick={() => setOpen(false)}>
              Ok
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
