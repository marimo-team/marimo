/* Copyright 2024 Marimo. All rights reserved. */

import { PlayIcon } from "lucide-react";
import React from "react";
import { MinimalHotkeys } from "@/components/shortcuts/renderShortcut";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
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
      <AcceptCompletionButton
        isLoading={isLoading}
        onAccept={onAccept}
        size="xs"
      />
      <RejectCompletionButton onDecline={onDecline} size="xs" />
    </>
  );
};

export const AcceptCompletionButton: React.FC<{
  isLoading: boolean;
  onAccept: () => void;
  size?: "xs" | "sm";
  buttonStyles?: string;
  playButtonStyles?: string;
  acceptShortcut?: string;
  runCell?: () => void;
}> = ({
  isLoading,
  onAccept,
  size = "sm",
  buttonStyles,
  acceptShortcut,
  runCell,
  playButtonStyles,
}) => {
  const handleAcceptAndRun = () => {
    onAccept();
    if (runCell) {
      runCell();
    }
  };

  const baseClasses = `h-6 text-(--grass-11) bg-(--grass-3)/60
    hover:bg-(--grass-3) dark:bg-(--grass-4)/80 dark:hover:bg-(--grass-3) font-semibold
    active:bg-(--grass-5) dark:active:bg-(--grass-4)
    border-(--green-6) border hover:shadow-xs`;

  if (runCell) {
    return (
      <div className="flex">
        <Button
          variant="text"
          size={size}
          disabled={isLoading}
          onClick={onAccept}
          className={`${baseClasses} rounded-r-none ${buttonStyles}`}
        >
          Accept
          {acceptShortcut && (
            <MinimalHotkeys className="ml-1 inline" shortcut={acceptShortcut} />
          )}
        </Button>
        <Tooltip content="Accept and run cell">
          <Button
            variant="text"
            size={size}
            disabled={isLoading}
            onClick={handleAcceptAndRun}
            className={`${baseClasses} rounded-l-none px-1.5 ${playButtonStyles}`}
          >
            <PlayIcon className="h-2.5 w-2.5 mt-0.5" />
          </Button>
        </Tooltip>
      </div>
    );
  }

  return (
    <Button
      variant="text"
      size={size}
      disabled={isLoading}
      onClick={onAccept}
      className={`${baseClasses} rounded px-3 ${buttonStyles}`}
    >
      Accept
      {acceptShortcut && (
        <MinimalHotkeys className="ml-1 inline" shortcut={acceptShortcut} />
      )}
    </Button>
  );
};

export const RejectCompletionButton: React.FC<{
  onDecline: () => void;
  size?: "xs" | "sm";
  className?: string;
  declineShortcut?: string;
}> = ({ onDecline, size = "sm", className, declineShortcut }) => {
  return (
    <Button
      variant="text"
      size={size}
      onClick={onDecline}
      className={`h-6 text-(--red-10) bg-(--red-3)/60 hover:bg-(--red-3)
    dark:bg-(--red-4)/80 dark:hover:bg-(--red-3) rounded px-3 font-semibold
    active:bg-(--red-5) dark:active:bg-(--red-4)
    border-(--red-6) border hover:shadow-xs ${className}`}
    >
      Reject
      {declineShortcut && (
        <MinimalHotkeys className="ml-1 inline" shortcut={declineShortcut} />
      )}
    </Button>
  );
};
