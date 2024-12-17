/* Copyright 2024 Marimo. All rights reserved. */
import React, { useEffect, useState } from "react";
import CodeMirrorMerge from "react-codemirror-merge";
import { useCompletion } from "ai/react";
import { API } from "@/core/network/api";
import { EditorView } from "@codemirror/view";
import { customPythonLanguageSupport } from "@/core/codemirror/language/python";
import { Button } from "@/components/ui/button";
import { Loader2Icon, SparklesIcon, XIcon } from "lucide-react";

import "./merge-editor.css";
import { cn } from "@/utils/cn";
import { toast } from "@/components/ui/use-toast";
import { prettyError } from "@/utils/errors";
import { Label } from "@/components/ui/label";
import { Tooltip } from "@/components/ui/tooltip";
import { useAtom } from "jotai";
import { includeOtherCellsAtom } from "@/core/ai/state";
import { Checkbox } from "@/components/ui/checkbox";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { useTheme } from "@/theme/useTheme";
import { asURL } from "@/utils/url";
import type { LanguageAdapterType } from "@/core/codemirror/language/types";
import { PromptInput } from "./add-cell-with-ai";
import { getAICompletionBody } from "./completion-utils";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { selectAllText } from "@/core/codemirror/utils";

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
  children,
}) => {
  const [completionBody, setCompletionBody] = useState<object>({});

  const [includeOtherCells, setIncludeOtherCells] = useAtom(
    includeOtherCellsAtom,
  );

  const {
    completion,
    input,
    stop,
    isLoading,
    setCompletion,
    setInput,
    handleSubmit,
  } = useCompletion({
    api: asURL("api/ai/completion").toString(),
    headers: API.headers(),
    initialInput: initialPrompt,
    streamMode: "text",
    body: {
      ...completionBody,
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
  });

  const inputRef = React.useRef<ReactCodeMirrorRef>(null);

  // Focus the input
  useEffect(() => {
    const input = inputRef.current;
    if (enabled && input) {
      requestAnimationFrame(() => {
        input.view?.focus();
      });
      selectAllText(inputRef.current.view);
    }
  }, [enabled]);

  // Reset the input when the prompt changes
  useEffect(() => {
    if (enabled) {
      setInput(initialPrompt || "");
    }
  }, [enabled, initialPrompt, setInput]);

  const { theme } = useTheme();

  return (
    <div
      className={cn(
        "flex flex-col w-full rounded-[inherit] overflow-hidden",
        className,
      )}
    >
      <div
        className={cn(
          "flex items-center gap-2 border-b px-3 transition-all rounded-[inherit] rounded-b-none duration-300 overflow-hidden",
          enabled && "max-h-[400px] min-h-11 visible",
          !enabled && "max-h-0 min-h-0 invisible",
        )}
      >
        {enabled && (
          <>
            <SparklesIcon
              className="text-[var(--blue-10)] flex-shrink-0"
              size={16}
            />
            <PromptInput
              inputRef={inputRef}
              theme={theme}
              onClose={() => {
                declineChange();
                setCompletion("");
              }}
              value={input}
              onChange={(newValue) => {
                setInput(newValue);
                setCompletionBody(getAICompletionBody(newValue));
              }}
              onSubmit={() => {
                if (!isLoading) {
                  handleSubmit();
                }
              }}
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
            {!isLoading && completion && (
              <Button
                data-testid="accept-completion-button"
                variant="text"
                size="xs"
                className="mb-0"
                disabled={isLoading}
                onClick={() => {
                  acceptChange(completion);
                  setCompletion("");
                }}
              >
                <span className="text-[var(--grass-11)] opacity-100">
                  Accept
                </span>
              </Button>
            )}
            <div className="h-full w-px bg-border mx-2" />
            <Tooltip content="Include code from other cells">
              <div className="flex flex-row items-start gap-1 overflow-hidden">
                <Checkbox
                  data-testid="include-other-cells-checkbox"
                  id="include-other-cells"
                  checked={includeOtherCells}
                  onCheckedChange={(checked) =>
                    setIncludeOtherCells(Boolean(checked))
                  }
                />
                <Label
                  htmlFor="include-other-cells"
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
              <XIcon className="text-[var(--red-10)]" size={16} />
            </Button>
          </>
        )}
      </div>
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
    </div>
  );
};
