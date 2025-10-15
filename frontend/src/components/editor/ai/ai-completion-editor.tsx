/* Copyright 2024 Marimo. All rights reserved. */

import { useCompletion } from "@ai-sdk/react";
import { EditorView } from "@codemirror/view";
import { AtSignIcon, Loader2Icon, SparklesIcon, XIcon } from "lucide-react";
import React, { useCallback, useEffect, useId, useState } from "react";
import CodeMirrorMerge from "react-codemirror-merge";
import { Button } from "@/components/ui/button";
import { customPythonLanguageSupport } from "@/core/codemirror/language/languages/python";

import "./merge-editor.css";
import { storePrompt } from "@marimo-team/codemirror-ai";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { useAtom } from "jotai";
import { AIModelDropdown } from "@/components/ai/ai-model-dropdown";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { includeOtherCellsAtom } from "@/core/ai/state";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
import { selectAllText } from "@/core/codemirror/utils";
import { useRuntimeManager } from "@/core/runtime/config";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { prettyError } from "@/utils/errors";
import { retryWithTimeout } from "@/utils/timeout";
import { PromptInput } from "./add-cell-with-ai";
import {
  AcceptCompletionButton,
  CompletionActions,
  createAiCompletionOnKeydown,
  RejectCompletionButton,
} from "./completion-handlers";
import { addContextCompletion, getAICompletionBody } from "./completion-utils";

const Original = CodeMirrorMerge.Original;
const Modified = CodeMirrorMerge.Modified;

interface Props {
  className?: string;
  currentCode: string;
  currentLanguageAdapter: LanguageAdapterType | undefined;
  initialPrompt: string | undefined;
  onChange: (code: string) => void;
  declineChange: () => void;
  acceptChange: (rightHandCode: string) => void;
  enabled: boolean;
  triggerImmediately?: boolean;
  runCell: () => void;
  outputArea?: "above" | "below";
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
  className,
  onChange,
  initialPrompt,
  currentLanguageAdapter,
  currentCode,
  declineChange,
  acceptChange,
  enabled,
  triggerImmediately,
  runCell,
  outputArea,
  children,
}) => {
  const [showInputPrompt, setShowInputPrompt] = useState(false);
  const [completionBody, setCompletionBody] = useState<object>({});

  const [includeOtherCells, setIncludeOtherCells] = useAtom(
    includeOtherCellsAtom,
  );
  const includeOtherCellsCheckboxId = useId();

  const runtimeManager = useRuntimeManager();

  const {
    completion: untrimmedCompletion,
    input,
    stop,
    isLoading,
    setCompletion,
    setInput,
    handleSubmit,
    complete,
  } = useCompletion({
    api: runtimeManager.getAiURL("completion").toString(),
    headers: runtimeManager.headers(),
    initialInput: initialPrompt,
    streamProtocol: "text",
    // Throttle the messages and data updates to 100ms
    experimental_throttle: 100,
    body: {
      ...(Object.keys(completionBody).length > 0
        ? completionBody
        : initialPrompt
          ? getAICompletionBody({ input: initialPrompt })
          : {}),
      includeOtherCode: includeOtherCells ? getCodes(currentCode) : "",
      code: currentCode,
      language: currentLanguageAdapter,
    },
    onError: (error) => {
      toast({
        title: "Completion failed",
        description: prettyError(error),
      });
    },
    onFinish: (_prompt, completion) => {
      // Remove trailing new lines
      setCompletion(completion.trimEnd());
    },
  });

  const inputRef = React.useRef<ReactCodeMirrorRef>(null);
  const completion = untrimmedCompletion.trimEnd();

  const initialSubmit = useCallback(() => {
    if (triggerImmediately && !isLoading && initialPrompt) {
      // Use complete to pass the prompt directly, else input might be empty
      complete(initialPrompt);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerImmediately]);

  // Focus the input
  useEffect(() => {
    if (enabled) {
      retryWithTimeout(
        () => {
          const input = inputRef.current;
          if (input?.view) {
            input.view.focus();
            initialSubmit();
            return true;
          }
          return false;
        },
        { retries: 3, delay: 100, initialDelay: 100 },
      ); // Wait for animation to complete

      selectAllText(inputRef.current?.view);
    }
  }, [enabled, initialSubmit]);

  // Reset the input when the prompt changes
  useEffect(() => {
    if (enabled) {
      setInput(initialPrompt || "");
    }
  }, [enabled, initialPrompt, setInput]);

  const { theme } = useTheme();

  const handleAcceptCompletion = () => {
    acceptChange(completion);
    setCompletion("");
  };

  const handleDeclineCompletion = () => {
    declineChange();
    setCompletion("");
  };

  const showCompletionBanner =
    enabled && triggerImmediately && (completion || isLoading);

  const showInput = enabled && (!triggerImmediately || showInputPrompt);

  const completionBanner = (
    <div
      className={cn(
        "w-full bg-(--cm-background) flex justify-center transition-all duration-300 ease-in-out overflow-hidden",
        showCompletionBanner
          ? "max-h-20 opacity-100 translate-y-0"
          : "max-h-0 opacity-0 -translate-y-2",
      )}
    >
      <CompletionBanner
        status={isLoading ? "loading" : "generated"}
        onAccept={handleAcceptCompletion}
        onReject={handleDeclineCompletion}
        showInputPrompt={showInputPrompt}
        setShowInputPrompt={setShowInputPrompt}
        runCell={runCell}
        className="mt-4 mb-3 w-128"
      />
    </div>
  );

  return (
    <div className={cn("flex flex-col w-full rounded-[inherit]", className)}>
      <div
        className={cn(
          "flex items-center gap-2 border-b px-3 transition-all rounded-[inherit] rounded-b-none duration-300",
          showInput && "max-h-[400px] min-h-11 visible",
          !showInput && "max-h-0 min-h-0 invisible",
        )}
      >
        {enabled && (
          <>
            <SparklesIcon className="text-(--blue-10) shrink-0" size={16} />
            <PromptInput
              inputRef={inputRef}
              className="h-full my-0 py-2 flex items-center"
              onClose={() => {
                declineChange();
                setCompletion("");
              }}
              value={input}
              onChange={(newValue) => {
                setInput(newValue);
                setCompletionBody(getAICompletionBody({ input: newValue }));
              }}
              onSubmit={() => {
                if (!isLoading) {
                  if (inputRef.current?.view) {
                    storePrompt(inputRef.current.view);
                  }
                  handleSubmit();
                }
              }}
              onKeyDown={createAiCompletionOnKeydown({
                handleAcceptCompletion,
                handleDeclineCompletion,
                isLoading,
                hasCompletion: completion.trim().length > 0,
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
              {completion && (
                <div className="-mb-1.5">
                  <CompletionActions
                    isLoading={isLoading}
                    onAccept={handleAcceptCompletion}
                    onDecline={handleDeclineCompletion}
                    size="xs"
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
                setCompletion("");
              }}
            >
              <XIcon className="text-(--red-10)" size={16} />
            </Button>
          </>
        )}
      </div>
      {outputArea === "above" && completionBanner}
      {completion && enabled && (
        <CodeMirrorMerge className="cm" theme={theme}>
          <Original
            onChange={onChange}
            value={currentCode}
            extensions={baseExtensions}
          />
          <Modified
            value={completion}
            editable={false}
            readOnly={true}
            extensions={baseExtensions}
          />
        </CodeMirrorMerge>
      )}
      {(!completion || !enabled) && children}
      {/* By default, show the completion banner below the code */}
      {(outputArea === "below" || !outputArea) && completionBanner}
    </div>
  );
};

interface CompletionBannerProps {
  status: "loading" | "generated";
  onAccept: () => void;
  onReject: () => void;
  showInputPrompt: boolean;
  setShowInputPrompt: (show: boolean) => void;
  runCell: () => void;
  className?: string;
}

const CompletionBanner: React.FC<CompletionBannerProps> = ({
  status,
  onAccept,
  onReject,
  className,
  showInputPrompt,
  setShowInputPrompt,
  runCell,
}) => {
  const isLoading = status === "loading";

  return (
    <div
      className={cn(
        "flex flex-row items-center gap-6 rounded-md py-2 px-2.5 text-sm border border-border",
        "shadow-[0_0_6px_1px_rgba(34,197,94,0.15)]",
        className,
      )}
    >
      <div className="flex flex-row items-center gap-2">
        <div
          className={cn(
            "w-2 h-2 rounded-full",
            status === "loading" ? "bg-blue-500 animate-pulse" : "bg-green-500",
          )}
        />
        <p className="transition-opacity duration-200 text-muted-foreground">
          {isLoading ? "Generating fix..." : "Showing fix"}
        </p>
      </div>

      <div className="flex flex-row items-center gap-1">
        <Label
          htmlFor="show-input-prompt"
          className="text-muted-foreground text-xs whitespace-nowrap ellipsis"
        >
          Show prompt
        </Label>
        <Switch
          checked={showInputPrompt}
          onCheckedChange={setShowInputPrompt}
          size="xs"
        />
      </div>

      <div className="flex flex-row items-center gap-2 ml-auto">
        <AcceptCompletionButton
          isLoading={isLoading}
          onAccept={onAccept}
          size="xs"
          buttonStyles="border-none rounded-md rounded-r-none"
          playButtonStyles="border-0 border-l-1 rounded-md rounded-l-none"
          runCell={runCell}
          // acceptShortcut="Mod-↵"
        />
        <RejectCompletionButton
          onDecline={onReject}
          size="xs"
          className="border-none rounded-md"
          // declineShortcut="Shift-Mod-Delete"
        />
      </div>
    </div>
  );
};
