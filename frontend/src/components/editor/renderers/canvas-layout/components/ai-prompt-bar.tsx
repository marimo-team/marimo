/* Copyright 2024 Marimo. All rights reserved. */

import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { Loader2Icon, SendHorizontal, SparklesIcon, XIcon } from "lucide-react";
import React, { memo, useEffect, useRef } from "react";
import { AIModelDropdown } from "@/components/ai/ai-model-dropdown";
import { PromptInput } from "@/components/editor/ai/add-cell-with-ai";
import {
  CompletionActionsCellFooter,
  createAiCompletionOnKeydown,
} from "@/components/editor/ai/completion-handlers";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import { useCanvasAIPrompt } from "../hooks/useCanvasAIPrompt";

// Constants
const AUTO_FOCUS_DELAY_MS = 150;

/**
 * AI Prompt Bar component for canvas layout
 * Shows a button that expands into an AI prompt input with smooth animation
 */
const AIPromptBarComponent: React.FC = () => {
  const inputRef = useRef<ReactCodeMirrorRef>(null);
  const {
    aiPromptState,
    setPrompt,
    toggleOpen,
    submit,
    stop,
    isLoading,
    hasCompletion,
    multipleCompletions,
    handleAcceptCompletion,
    handleDeclineCompletion,
    handleClose,
  } = useCanvasAIPrompt();

  const isOpen = aiPromptState.isOpen;

  // Auto-focus the input when opening
  useEffect(() => {
    if (isOpen && inputRef.current?.view) {
      // Small delay to allow animation to start
      setTimeout(() => {
        inputRef.current?.view?.focus();
      }, AUTO_FOCUS_DELAY_MS);
    }
  }, [isOpen]);

  return (
    <div
      className={cn(
        "absolute top-4 left-1/2 -translate-x-1/2 z-50 pointer-events-none transition-all duration-300 ease-out px-4",
        isOpen ? "w-full max-w-3xl" : "w-content",
      )}
      data-keep-node-selection={true}
    >
      <div
        className={cn(
          "bg-background/95 backdrop-blur-sm border border-(--slate-7) rounded-lg shadow-lg pointer-events-auto transition-all duration-300 ease-out relative",
          !isOpen && "hover:border-(--blue-8)",
        )}
      >
        {/* Button state (collapsed) - always in DOM, but hidden when open */}
        <div
          className={cn(
            "transition-all duration-300 ease-out",
            isOpen
              ? "opacity-0 max-h-0 overflow-hidden pointer-events-none"
              : "opacity-100 max-h-20",
          )}
        >
          <Button
            variant="secondary"
            size="sm"
            onClick={toggleOpen}
            className="gap-2 border-0 shadow-none hover:bg-transparent"
            data-testid="canvas-ai-prompt-button"
            tabIndex={isOpen ? -1 : 0}
          >
            <SparklesIcon className="size-4 text-(--blue-11)" />
            Generate with AI
          </Button>
        </div>

        {/* Expanded input state - always in DOM, but hidden when closed */}
        <div
          className={cn(
            "transition-opacity duration-300 ease-out",
            isOpen
              ? "opacity-100 max-h-[500px]"
              : "opacity-0 max-h-0 overflow-hidden pointer-events-none w-36",
          )}
        >
          <div className="flex flex-col w-full gap-2 py-2">
            {/* Input row */}
            <div className="flex items-center px-3">
              <SparklesIcon className="size-4 text-(--blue-11) mr-2 shrink-0" />
              <PromptInput
                inputRef={inputRef}
                value={aiPromptState.prompt}
                onChange={setPrompt}
                onSubmit={submit}
                onClose={handleClose}
                onKeyDown={createAiCompletionOnKeydown({
                  handleAcceptCompletion,
                  handleDeclineCompletion,
                  isLoading,
                  hasCompletion,
                })}
                placeholder="Generate cells with AI..."
                maxHeight="200px"
              />
              {isLoading && (
                <Button
                  data-testid="stop-completion-button"
                  variant="text"
                  size="sm"
                  className="mb-0 shrink-0"
                  onClick={stop}
                  tabIndex={isOpen ? 0 : -1}
                >
                  <Loader2Icon className="animate-spin mr-1" size={14} />
                  Stop
                </Button>
              )}
              {!isLoading && (
                <Button
                  variant="text"
                  size="sm"
                  onClick={submit}
                  title="Submit"
                  disabled={!aiPromptState.prompt.trim()}
                  className="shrink-0"
                  tabIndex={isOpen ? 0 : -1}
                >
                  <SendHorizontal className="size-4" />
                </Button>
              )}
              <Button
                variant="text"
                size="sm"
                className="mb-0 px-1 shrink-0"
                onClick={handleClose}
                tabIndex={isOpen ? 0 : -1}
              >
                <XIcon className="size-4" />
              </Button>
            </div>

            {/* Actions row */}
            <div className="flex flex-row justify-between -mt-1 ml-1 mr-3">
              {!hasCompletion && (
                <span className="text-xs text-muted-foreground px-3 flex flex-col gap-1">
                  <span>
                    You can mention{" "}
                    <span className="text-(--cyan-11)">@dataframe</span> or{" "}
                    <span className="text-(--cyan-11)">@sql_table</span> to pull
                    additional context such as column names.
                  </span>
                  <span>Code from other cells is automatically included.</span>
                </span>
              )}
              {hasCompletion && (
                <CompletionActionsCellFooter
                  isLoading={isLoading}
                  onAccept={handleAcceptCompletion}
                  onDecline={handleDeclineCompletion}
                  size="sm"
                  multipleCompletions={multipleCompletions}
                />
              )}
              <div className="ml-auto flex items-center gap-1">
                <AIModelDropdown
                  triggerClassName="h-7 text-xs max-w-64"
                  iconSize="small"
                  forRole="edit"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export const AIPromptBar = memo(AIPromptBarComponent);
AIPromptBar.displayName = "AIPromptBar";
