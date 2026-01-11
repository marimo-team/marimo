/* Copyright 2026 Marimo. All rights reserved. */

import { useAtom } from "jotai";
import { CopyIcon, HomeIcon, XCircleIcon } from "lucide-react";
import { kernelStartupErrorAtom } from "@/core/errors/state";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../ui/alert-dialog";
import { Button } from "../ui/button";
import { toast } from "../ui/use-toast";

/**
 * Modal that displays kernel startup errors.
 * Shows when the kernel fails to start in sandbox mode,
 * displaying the stderr output so users can diagnose the issue.
 */
export const KernelStartupErrorModal: React.FC = () => {
  const [error, setError] = useAtom(kernelStartupErrorAtom);

  if (error === null) {
    return null;
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(error);
      toast({
        title: "Copied to clipboard",
        description: "Error details have been copied to your clipboard.",
      });
    } catch {
      toast({
        title: "Failed to copy",
        description: "Could not copy to clipboard.",
        variant: "danger",
      });
    }
  };

  const handleClose = () => {
    setError(null);
  };

  const handleReturnHome = () => {
    const withoutSearch = document.baseURI.split("?")[0];
    window.open(withoutSearch, "_self");
  };

  return (
    <AlertDialog open={true} onOpenChange={(open) => !open && handleClose()}>
      <AlertDialogContent className="max-w-2xl">
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2 text-destructive">
            <XCircleIcon className="h-5 w-5" />
            Kernel Startup Failed
          </AlertDialogTitle>
          <AlertDialogDescription>
            The kernel failed to start. This usually happens when the package
            manager can't install your notebook's dependencies.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="my-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-muted-foreground">
              Error Details
            </span>
            <Button
              variant="outline"
              size="xs"
              onClick={handleCopy}
              className="flex items-center gap-1"
            >
              <CopyIcon className="h-3 w-3" />
              Copy
            </Button>
          </div>
          <pre className="bg-muted p-4 rounded-md text-sm font-mono overflow-auto max-h-80 whitespace-pre-wrap break-words">
            {error}
          </pre>
        </div>
        <AlertDialogFooter>
          <Button
            variant="outline"
            onClick={handleReturnHome}
            className="flex items-center gap-2"
          >
            <HomeIcon className="h-4 w-4" />
            Return to Home
          </Button>
          <AlertDialogAction onClick={handleClose}>Dismiss</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
