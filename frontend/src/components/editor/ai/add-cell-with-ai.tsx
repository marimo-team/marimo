/* Copyright 2024 Marimo. All rights reserved. */
import { useCellActions } from "../../../core/cells/cells";
import { cn } from "@/utils/cn";
import { Button } from "@/components/ui/button";
import { Loader2Icon, SparklesIcon, XIcon } from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { API } from "@/core/network/api";
import { prettyError } from "@/utils/errors";
import { useCompletion } from "ai/react";
import ReactCodeMirror, { EditorView } from "@uiw/react-codemirror";
import { customPythonLanguageSupport } from "@/core/codemirror/language/python";
import { asURL } from "@/utils/url";

const extensions = [customPythonLanguageSupport(), EditorView.lineWrapping];

/**
 * Add a cell with AI.
 */
export const AddCellWithAI: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  const { createNewCell } = useCellActions();

  const {
    completion,
    input,
    stop,
    isLoading,
    setCompletion,
    handleInputChange,
    handleSubmit,
  } = useCompletion({
    api: asURL("api/ai/completion").toString(),
    headers: API.headers(),
    streamMode: "text",
    body: {
      includeOtherCode: getCodes(""),
      code: "",
    },
    onError: (error) => {
      toast({
        title: "Generate with AI failed",
        description: prettyError(error),
      });
    },
  });

  const inputComponent = (
    <div className="flex items-center gap-3 px-3 py-2">
      <SparklesIcon className="size-4 text-[var(--blue-11)]" />
      <input
        className="h-8 outline-none text-base focus-visible:shadow-none flex-1 rounded-none border-none focus:border-none"
        autoFocus={true}
        value={input}
        onChange={handleInputChange}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            handleSubmit(e as unknown as React.FormEvent<HTMLFormElement>);
          }
          if (e.key === "Escape") {
            e.preventDefault();
            setCompletion("");
            onClose();
          }
        }}
        placeholder="Generate with AI"
      />
      {isLoading && (
        <Button
          data-testid="stop-completion-button"
          variant="text"
          size="sm"
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
          size="sm"
          className="mb-0"
          disabled={isLoading}
          onClick={() => {
            createNewCell({
              cellId: "__end__",
              before: false,
              code: completion,
            });
            setCompletion("");
            onClose();
          }}
        >
          <span className="text-[var(--grass-11)] opacity-100">Accept</span>
        </Button>
      )}
      <Button variant="text" size="sm" className="mb-0" onClick={onClose}>
        <XIcon className="size-4" />
      </Button>
    </div>
  );

  return (
    <div className={cn("flex flex-col w-full")}>
      {inputComponent}
      {completion && (
        <ReactCodeMirror
          value={completion}
          className="cm border-t"
          onChange={setCompletion}
          extensions={extensions}
        />
      )}
    </div>
  );
};
