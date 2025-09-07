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
  completion: string;
}) => {
  const {
    handleAcceptCompletion,
    handleDeclineCompletion,
    isLoading,
    completion,
  } = opts;

  return (e: React.KeyboardEvent<HTMLDivElement>) => {
    const metaKey = isPlatformMac() ? e.metaKey : e.ctrlKey;

    // Mod+Enter should accept the completion, if there is one
    if (metaKey && e.key === "Enter" && !isLoading && completion) {
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
}> = ({
  isLoading,
  onAccept,
  onDecline,
  size = "sm",
  acceptShortcut = "Mod-↵",
  declineShortcut = "Shift-Mod-Delete",
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
          Accept{" "}
          <MinimalHotkeys className="ml-1 inline" shortcut={acceptShortcut} />
        </span>
      </Button>
      <Button
        data-testid="decline-completion-button"
        variant="text"
        size={size}
        className="mb-0 pl-1"
        onClick={onDecline}
      >
        <span className="text-(--red-10)">
          Reject{" "}
          <MinimalHotkeys className="ml-1 inline" shortcut={declineShortcut} />
        </span>
      </Button>
    </>
  );
};
