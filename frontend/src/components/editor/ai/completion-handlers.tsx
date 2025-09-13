/* Copyright 2024 Marimo. All rights reserved. */

import React from "react";
import { MinimalHotkeys } from "@/components/shortcuts/renderShortcut";
import { Button } from "@/components/ui/button";
import { isPlatformMac } from "@/core/hotkeys/shortcuts";

/**
 * Common keyboard shortcut handlers for AI completions
 */
export const createAiCompletionOnKeydown = (opts: {
  handleAcceptCompletion: () => void;
  handleDeclineCompletion: () => void;
  isLoading: boolean;
  hasCompletion: boolean;
}) => {
  const {
    handleAcceptCompletion,
    handleDeclineCompletion,
    isLoading,
    hasCompletion,
  } = opts;

  return (e: React.KeyboardEvent<HTMLDivElement>) => {
    const metaKey = isPlatformMac() ? e.metaKey : e.ctrlKey;

    // Mod+Enter should accept the completion, if there is one
    if (metaKey && e.key === "Enter" && !isLoading && hasCompletion) {
      handleAcceptCompletion();
    }

    // Mod+Shift+Delete should decline the completion
    const deleteKey = e.key === "Delete" || e.key === "Backspace";
    if (deleteKey && metaKey && e.shiftKey) {
      handleDeclineCompletion();
      e.preventDefault();
      e.stopPropagation();
    }
  };
};

/**
 * Common completion action buttons with keyboard shortcuts
 */
export const CompletionActions: React.FC<{
  isLoading: boolean;
  onAccept: () => void;
  onDecline: () => void;
  size?: "xs" | "sm";
  acceptShortcut?: string;
  declineShortcut?: string;
  multipleCompletions?: boolean;
}> = ({
  isLoading,
  onAccept,
  onDecline,
  size = "sm",
  acceptShortcut = "Mod-↵",
  declineShortcut = "Shift-Mod-Delete",
  multipleCompletions = false,
}) => {
  return (
    <>
      <Button
        data-testid="accept-completion-button"
        variant="text"
        size={size}
        className="mb-0"
        disabled={isLoading}
        onClick={onAccept}
      >
        <span className="text-(--grass-11) opacity-100">
          Accept{multipleCompletions && " all"}{" "}
          <MinimalHotkeys className="ml-1 inline" shortcut={acceptShortcut} />
        </span>
      </Button>
      <Button
        data-testid="decline-completion-button"
        variant="text"
        size={size}
        className="mb-0 pl-1 pr-0"
        onClick={onDecline}
      >
        <span className="text-(--red-10)">
          Reject{multipleCompletions && " all"}{" "}
          <MinimalHotkeys className="ml-1 inline" shortcut={declineShortcut} />
        </span>
      </Button>
    </>
  );
};

export const CompletionActionsCellFooter: React.FC<{
  isLoading: boolean;
  onAccept: () => void;
  onDecline: () => void;
  size?: "xs" | "sm";
  multipleCompletions?: boolean;
}> = ({ isLoading, onAccept, onDecline }) => {
  return (
    <>
      <Button
        variant="text"
        size="xs"
        disabled={isLoading}
        onClick={onAccept}
        className="text-white bg-(--grass-11) hover:bg-(--grass-10) 
        dark:bg-(--grass-6) dark:hover:bg-(--grass-5) h-6 rounded-sm px-3 font-medium"
      >
        Accept
      </Button>
      <Button
        variant="text"
        size="xs"
        onClick={onDecline}
        className="text-white bg-(--red-11) hover:bg-(--red-10) 
        dark:bg-(--red-7) dark:hover:bg-(--red-6) h-6 rounded-sm px-3 font-medium"
      >
        Reject
      </Button>
    </>
  );
};
