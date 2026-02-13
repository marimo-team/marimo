/* Copyright 2026 Marimo. All rights reserved. */
import React from "react";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { CopyIcon } from "lucide-react";
import { toast } from "@/components/ui/use-toast";

interface TracebackModalProps {
  isOpen: boolean;
  onClose: () => void;
  traceback: string;
  errorMessage: string;
}

export const TracebackModal: React.FC<TracebackModalProps> = ({
  isOpen,
  onClose,
  traceback,
  errorMessage,
}) => {
  const handleCopy = async () => {
    // Strip HTML tags for clipboard
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = traceback;
    const textContent = tempDiv.textContent || tempDiv.innerText || "";

    try {
      await navigator.clipboard.writeText(textContent);
      toast({
        title: "Copied to clipboard",
        description: "Traceback has been copied to your clipboard.",
      });
    } catch {
      toast({
        title: "Failed to copy",
        description: "Could not copy to clipboard.",
        variant: "danger",
      });
    }
  };

  return (
    <AlertDialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent className="max-w-4xl max-h-[80vh]">
        <AlertDialogHeader>
          <AlertDialogTitle className="text-destructive">
            {errorMessage}
          </AlertDialogTitle>
          <AlertDialogDescription>
            Click the traceback to select and copy.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="my-4 overflow-auto">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-muted-foreground">
              Traceback
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
          <div
            className="font-code text-sm p-4 bg-muted rounded border overflow-auto max-h-[50vh] cursor-text select-text"
            dangerouslySetInnerHTML={{ __html: traceback }}
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogAction onClick={onClose}>Close</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
