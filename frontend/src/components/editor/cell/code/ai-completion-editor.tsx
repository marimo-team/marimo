/* Copyright 2024 Marimo. All rights reserved. */
import React, { useEffect } from "react";
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

const Original = CodeMirrorMerge.Original;
const Modified = CodeMirrorMerge.Modified;

interface Props {
  currentCode: string;
  onChange: (code: string) => void;
  declineChange: () => void;
  acceptChange: (rightHandCode: string) => void;
  enabled: boolean;
  /**
   * Children shown when there is no completion
   */
  children: React.ReactNode;
}

export const AiCompletionEditor: React.FC<Props> = ({
  onChange,
  currentCode,
  declineChange,
  acceptChange,
  enabled,
  children,
}) => {
  const [includeOtherCells, setIncludeOtherCells] = useAtom(
    includeOtherCellsAtom,
  );

  const {
    completion,
    input,
    stop,
    isLoading,
    setCompletion,
    handleInputChange,
    handleSubmit,
  } = useCompletion({
    api: "/api/ai/completion",
    headers: API.headers(),
    body: {
      includeOtherCode: includeOtherCells ? getCodes(currentCode) : "",
      code: currentCode,
    },
    onError: (error) => {
      toast({
        title: "Completion failed",
        description: prettyError(error),
      });
    },
  });

  const inputRef = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (enabled && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [enabled]);

  const baseExtensions = [
    customPythonLanguageSupport(),
    EditorView.lineWrapping,
  ];

  return (
    <div className="flex flex-col w-full rounded-[inherit]">
      <div
        className={cn(
          "flex items-center gap-2 border-b px-3 transition-[height] rounded-[inherit] rounded-b-none duration-300 overflow-hidden",
          enabled && "h-10 visible",
          !enabled && "h-0 invisible",
        )}
      >
        <SparklesIcon className="text-[var(--blue-10)]" size={16} />
        <input
          className="h-8 outline-none px-2 focus-visible:shadow-none flex-1 rounded-none border-none focus:border-none"
          value={input}
          ref={inputRef}
          onChange={handleInputChange}
          placeholder="Type for completion"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              handleSubmit(e as unknown as React.FormEvent<HTMLFormElement>);
            }
            if (e.key === "Escape") {
              e.preventDefault();
              declineChange();
              setCompletion("");
            }
          }}
        />
        {isLoading && (
          <Button variant="text" size="xs" className="mb-0" onClick={stop}>
            <Loader2Icon className="animate-spin mr-1" size={14} />
            Stop
          </Button>
        )}
        {!isLoading && completion && (
          <Button
            variant="text"
            size="xs"
            className="mb-0"
            disabled={isLoading}
            onClick={() => {
              acceptChange(completion);
              setCompletion("");
            }}
          >
            <span className="text-[var(--grass-11)] opacity-100">Accept</span>
          </Button>
        )}
        <div className="h-full w-px bg-border mx-2" />
        <Tooltip content="Include code from other cells">
          <div className="flex flex-row items-start gap-1">
            <Checkbox
              id="include-other-cells"
              checked={includeOtherCells}
              onCheckedChange={(checked) =>
                setIncludeOtherCells(Boolean(checked))
              }
            />
            <Label
              htmlFor="include-other-cells"
              className="text-muted-foreground text-xs"
            >
              Include all code
            </Label>
          </div>
        </Tooltip>
        <Button
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
      </div>
      {completion && enabled && (
        <CodeMirrorMerge className="cm">
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
