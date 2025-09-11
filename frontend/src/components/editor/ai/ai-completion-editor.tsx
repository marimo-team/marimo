/* Copyright 2024 Marimo. All rights reserved. */

import { useChat } from "@ai-sdk/react";
import { EditorView } from "@codemirror/view";
import { AtSignIcon, Loader2Icon, SparklesIcon, XIcon } from "lucide-react";
import React, { useEffect, useId, useMemo, useState } from "react";
import CodeMirrorMerge from "react-codemirror-merge";
import { Button } from "@/components/ui/button";
import { customPythonLanguageSupport } from "@/core/codemirror/language/languages/python";

import "./merge-editor.css";
import { storePrompt } from "@marimo-team/codemirror-ai";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { DefaultChatTransport, type UIMessage } from "ai";
import { useAtom } from "jotai";
import { AIModelDropdown } from "@/components/ai/ai-model-dropdown";
import {
  buildCompletionRequestBody,
  handleToolCall,
} from "@/components/chat/chat-utils";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { includeOtherCellsAtom } from "@/core/ai/state";
import { useCellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
import { selectAllText } from "@/core/codemirror/utils";
import { useRequestClient } from "@/core/network/requests";
import type { AiCompletionRequest } from "@/core/network/types";
import { useRuntimeManager } from "@/core/runtime/config";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { prettyError } from "@/utils/errors";
import { retryWithTimeout } from "@/utils/timeout";
import { PromptInput } from "./add-cell-with-ai";
import { CompletionCellPreview } from "./completion-cells";
import {
  CompletionActions,
  createAiCompletionOnKeydown,
} from "./completion-handlers";
import {
  type AiCompletion,
  addContextCompletion,
  UIMessageToCodeCells,
} from "./completion-utils";

const Original = CodeMirrorMerge.Original;
const Modified = CodeMirrorMerge.Modified;

interface Props {
  cellId: string;
  className?: string;
  currentCode: string;
  currentLanguageAdapter: LanguageAdapterType | undefined;
  initialPrompt: string | undefined;
  onChange: (code: string) => void;
  declineChange: () => void;
  acceptChange: (rightHandCode: string) => void;
  enabled: boolean;
  /**
   * Children shown when there is no completion
   */
  children: React.ReactNode;
}

const baseExtensions = [customPythonLanguageSupport(), EditorView.lineWrapping];

/**
 * Editor for AI completions that goes above a cell to modify it.
 *
 * This shows a left/right split with the original and modified code.
 */
export const AiCompletionEditor: React.FC<Props> = ({
  cellId,
  className,
  onChange,
  initialPrompt,
  currentLanguageAdapter,
  currentCode,
  declineChange,
  acceptChange,
  enabled,
  children,
}) => {
  const [input, setInput] = useState("");
  const [completionCells, setCompletionCells] = useState<AiCompletion[]>([]);

  const [includeOtherCells, setIncludeOtherCells] = useAtom(
    includeOtherCellsAtom,
  );
  const includeOtherCellsCheckboxId = useId();
  const runtimeManager = useRuntimeManager();
  const { createNewCell } = useCellActions();
  const { invokeAiTool } = useRequestClient();

  const initialMessages: UIMessage[] = useMemo(() => {
    if (initialPrompt) {
      return [
        {
          id: "system",
          role: "system",
          parts: [{ type: "text", text: initialPrompt }],
        },
      ];
    }
    return [];
  }, [initialPrompt]);

  const { sendMessage, stop, status, addToolResult } = useChat({
    // Throttle the messages and data updates to 100ms
    experimental_throttle: 100,
    messages: initialMessages,
    transport: new DefaultChatTransport({
      api: runtimeManager.getAiURL("completion").toString(),
      headers: runtimeManager.headers(),
      prepareSendMessagesRequest: async (options) => {
        const completionBody = await buildCompletionRequestBody(
          options.messages,
        );
        const body: AiCompletionRequest = {
          ...options,
          ...completionBody,
          code: currentCode,
          prompt: "", // Don't need prompt since we are using messages
          language: currentLanguageAdapter,
        };

        return {
          body: body,
        };
      },
    }),
    onToolCall: async ({ toolCall }) => {
      await handleToolCall({
        invokeAiTool,
        addToolResult,
        toolCall: {
          toolName: toolCall.toolName,
          toolCallId: toolCall.toolCallId,
          input: toolCall.input as Record<string, never>,
        },
      });
    },
    onError: (error) => {
      toast({
        title: "Completion failed",
        description: prettyError(error),
      });
    },
    onFinish: ({ message }) => {
      // Take the last message (response from assistant) and get the text parts
      setCompletionCells(UIMessageToCodeCells(message));
    },
  });

  const multipleCompletions = completionCells.length > 1;

  const isLoading = status === "streaming" || status === "submitted";
  const inputRef = React.useRef<ReactCodeMirrorRef>(null);

  // Focus the input
  useEffect(() => {
    if (enabled) {
      retryWithTimeout(
        () => {
          const input = inputRef.current;
          if (input?.view) {
            input.view.focus();
            return true;
          }
          return false;
        },
        { retries: 3, delay: 100, initialDelay: 100 },
      ); // Wait for animation to complete

      selectAllText(inputRef.current?.view);
    }
  }, [enabled]);

  // Reset the input when the prompt changes
  useEffect(() => {
    if (enabled) {
      setInput(initialPrompt || "");
    }
  }, [enabled, initialPrompt, setInput]);

  const { theme } = useTheme();

  const hasCompletion = completionCells.length > 0;
  const handleAcceptCompletion = () => {
    // Accept first cell
    acceptChange(completionCells[0].code);

    // Create new cells if there are multiple completions
    if (multipleCompletions) {
      for (const cell of completionCells.slice(1)) {
        createNewCell({
          cellId: cellId as CellId,
          code: cell.code,
          before: false,
        });
      }
    }
    setCompletionCells([]);
  };

  const handleDeclineCompletion = () => {
    setCompletionCells([]);
  };

  const handleAcceptNewCell = (completionIndex: number) => {
    const code = completionCells[completionIndex].code;
    createNewCell({
      cellId: cellId as CellId,
      code: code,
      before: false,
    });
    setCompletionCells((prev) =>
      prev.filter((_, index) => index !== completionIndex),
    );
  };

  const handleRejectNewCell = (completionIndex: number) => {
    setCompletionCells((prev) =>
      prev.filter((_, index) => index !== completionIndex),
    );
  };

  const renderCompletionCells = () => {
    if (completionCells.length === 0) {
      return null;
    }

    // First completion will replace the current code
    // Subsequent completions will create new cells
    const firstCompletion = completionCells[0];
    const newCompletions = completionCells.slice(1);

    const isCurrentCodeEmpty = currentCode.trim() === "";

    return (
      <>
        {isCurrentCodeEmpty ? (
          <CompletionCellPreview
            code={firstCompletion.code}
            language={firstCompletion.language}
            onAccept={() => handleAcceptNewCell(0)}
            onDecline={() => handleRejectNewCell(0)}
            theme={theme}
            displayActions={multipleCompletions}
          />
        ) : (
          <CodeMirrorMerge className="cm" theme={theme}>
            <Original
              onChange={onChange}
              value={currentCode}
              extensions={baseExtensions}
            />
            <Modified
              value={firstCompletion.code}
              editable={false}
              readOnly={true}
              extensions={baseExtensions}
            />
          </CodeMirrorMerge>
        )}
        {newCompletions.map((cell, index) => (
          <CompletionCellPreview
            key={index}
            code={cell.code}
            language={cell.language}
            // Add 1 to index since newCells starts from index 1 of completionCells
            onAccept={() => handleAcceptNewCell(index + 1)}
            onDecline={() => handleRejectNewCell(index + 1)}
            theme={theme}
            className="border-t"
          />
        ))}
      </>
    );
  };

  return (
    <div className={cn("flex flex-col w-full rounded-[inherit]", className)}>
      <div
        className={cn(
          "flex items-center gap-2 border-b px-3 transition-all rounded-[inherit] rounded-b-none duration-300",
          enabled && "max-h-[400px] min-h-11 visible",
          !enabled && "max-h-0 min-h-0 invisible",
        )}
      >
        {enabled && (
          <>
            <SparklesIcon className="text-(--blue-10) shrink-0" size={16} />
            <PromptInput
              inputRef={inputRef}
              className="h-full my-0 py-2"
              onClose={() => {
                declineChange();
                setCompletionCells([]);
              }}
              value={input}
              onChange={(newValue) => {
                setInput(newValue);
              }}
              onSubmit={() => {
                if (!isLoading) {
                  if (inputRef.current?.view) {
                    storePrompt(inputRef.current.view);
                  }
                  sendMessage({
                    text: input,
                  });
                }
              }}
              onKeyDown={createAiCompletionOnKeydown({
                handleAcceptCompletion,
                handleDeclineCompletion,
                isLoading,
                hasCompletion,
              })}
            />
            {isLoading && (
              <Button
                data-testid="stop-completion-button"
                variant="text"
                size="xs"
                className="mb-0"
                onClick={stop}
              >
                <Loader2Icon className="animate-spin mr-1" size={14} />
                Stop
              </Button>
            )}
            <div className="-mr-1.5 py-1.5">
              <div className="flex flex-row items-center justify-end gap-0.5">
                <Tooltip content="Add context">
                  <Button
                    variant="text"
                    size="icon"
                    onClick={() => addContextCompletion(inputRef)}
                  >
                    <AtSignIcon className="h-3 w-3" />
                  </Button>
                </Tooltip>
                <AIModelDropdown
                  triggerClassName="h-7 text-xs w-24"
                  iconSize="small"
                  forRole="edit"
                />
              </div>
              {hasCompletion && (
                <div className="-mb-1.5">
                  <CompletionActions
                    isLoading={isLoading}
                    onAccept={handleAcceptCompletion}
                    onDecline={handleDeclineCompletion}
                    size="xs"
                    multipleCompletions={multipleCompletions}
                  />
                </div>
              )}
            </div>

            <div className="h-full w-px bg-border mx-2" />
            <Tooltip content="Include code from other cells">
              <div className="flex flex-row items-start gap-1 overflow-hidden">
                <Checkbox
                  data-testid="include-other-cells-checkbox"
                  id={includeOtherCellsCheckboxId}
                  checked={includeOtherCells}
                  onCheckedChange={(checked) =>
                    setIncludeOtherCells(Boolean(checked))
                  }
                />
                <Label
                  htmlFor={includeOtherCellsCheckboxId}
                  className="text-muted-foreground text-xs whitespace-nowrap ellipsis"
                >
                  Include all code
                </Label>
              </div>
            </Tooltip>
            <Button
              data-testid="decline-completion-button"
              variant="text"
              size="icon"
              disabled={isLoading}
              onClick={() => {
                stop();
                declineChange();
                setCompletionCells([]);
              }}
            >
              <XIcon className="text-(--red-10)" size={16} />
            </Button>
          </>
        )}
      </div>

      {hasCompletion && enabled && renderCompletionCells()}
      {(!hasCompletion || !enabled) && children}
    </div>
  );
};
