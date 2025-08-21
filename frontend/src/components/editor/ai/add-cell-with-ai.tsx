/* Copyright 2024 Marimo. All rights reserved. */

import {
  autocompletion,
  type Completion,
  type CompletionContext,
  type CompletionSource,
} from "@codemirror/autocomplete";
import { markdown } from "@codemirror/lang-markdown";
import { sql } from "@codemirror/lang-sql";
import { Prec } from "@codemirror/state";
import ReactCodeMirror, {
  EditorView,
  keymap,
  minimalSetup,
  type ReactCodeMirrorRef,
} from "@uiw/react-codemirror";
import { useCompletion } from "ai/react";
import { useAtom, useAtomValue, useStore } from "jotai";
import { atomWithStorage } from "jotai/utils";
import {
  ChevronsUpDown,
  DatabaseIcon,
  Loader2Icon,
  SendHorizontal,
  SparklesIcon,
  XIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import useEvent from "react-use-event-hook";
import { AIModelDropdown } from "@/components/ai/ai-model-dropdown";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "@/components/ui/use-toast";
import { useModelChange } from "@/core/ai/config";
import { resourceExtension } from "@/core/codemirror/ai/resources";
import { customPythonLanguageSupport } from "@/core/codemirror/language/languages/python";
import { SQLLanguageAdapter } from "@/core/codemirror/language/languages/sql/sql";
import { aiAtom } from "@/core/config/config";
import { DEFAULT_AI_MODEL } from "@/core/config/config-schema";
import { useRuntimeManager } from "@/core/runtime/config";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { prettyError } from "@/utils/errors";
import { useCellActions } from "../../../core/cells/cells";
import { PythonIcon } from "../cell/code/icons";
import {
  CompletionActions,
  createAiCompletionOnKeydown,
} from "./completion-handlers";
import {
  getAICompletionBody,
  mentionsCompletionSource,
} from "./completion-utils";

const pythonExtensions = [
  customPythonLanguageSupport(),
  EditorView.lineWrapping,
];
const sqlExtensions = [sql(), EditorView.lineWrapping];

// Persist across sessions
const languageAtom = atomWithStorage<"python" | "sql">(
  "marimo:ai-language",
  "python",
);

/**
 * Add a cell with AI.
 */
export const AddCellWithAI: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  const { createNewCell } = useCellActions();
  const [completionBody, setCompletionBody] = useState<object>({});
  const [language, setLanguage] = useAtom(languageAtom);
  const { theme } = useTheme();
  const runtimeManager = useRuntimeManager();

  const ai = useAtomValue(aiAtom);
  const editModel = ai?.models?.edit_model || DEFAULT_AI_MODEL;
  const { saveModelChange } = useModelChange();

  const {
    completion,
    input,
    stop,
    isLoading,
    setCompletion,
    setInput,
    handleSubmit,
  } = useCompletion({
    api: runtimeManager.getAiURL("completion").toString(),
    headers: runtimeManager.headers(),
    streamProtocol: "text",
    // Throttle the messages and data updates to 100ms
    experimental_throttle: 100,
    body: {
      ...completionBody,
      language: language,
      code: "",
    },
    onError: (error) => {
      toast({
        title: "Generate with AI failed",
        description: prettyError(error),
      });
    },
    onFinish: (_prompt, completion) => {
      // Remove trailing new lines
      setCompletion(completion.trimEnd());
    },
  });

  const submit = () => {
    if (!isLoading) {
      handleSubmit();
    }
  };

  const pythonIcon = (
    <>
      <PythonIcon className="size-4 mr-2" />
      Python
    </>
  );

  const sqlIcon = (
    <>
      <DatabaseIcon className="size-4 mr-2" />
      SQL
    </>
  );

  const languageDropdown = (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild={true}>
        <Button
          variant="text"
          className="ml-2"
          size="xs"
          data-testid="language-button"
        >
          {language === "python" ? pythonIcon : sqlIcon}
          <ChevronsUpDown className="ml-1 h-3.5 w-3.5 text-muted-foreground/70" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="center">
        <div className="px-2 py-1 font-semibold">Select language</div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => setLanguage("python")}>
          {pythonIcon}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setLanguage("sql")}>
          {sqlIcon}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  const handleAcceptCompletion = () => {
    createNewCell({
      cellId: "__end__",
      before: false,
      code:
        language === "python"
          ? completion
          : SQLLanguageAdapter.fromQuery(completion),
    });
    setCompletion("");
    onClose();
  };

  const handleDeclineCompletion = () => {
    setCompletion("");
  };

  const inputComponent = (
    <div className="flex items-center px-3">
      <SparklesIcon className="size-4 text-(--blue-11) mr-2" />
      <PromptInput
        onClose={() => {
          setCompletion("");
          onClose();
        }}
        value={input}
        onChange={(newValue) => {
          setInput(newValue);
          setCompletionBody(getAICompletionBody({ input: newValue }));
        }}
        onSubmit={submit}
        onKeyDown={createAiCompletionOnKeydown({
          handleAcceptCompletion,
          handleDeclineCompletion,
          isLoading,
          completion,
        })}
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
      <Button variant="text" size="sm" onClick={submit} title="Submit">
        <SendHorizontal className="size-4" />
      </Button>
      <Button variant="text" size="sm" className="mb-0 px-1" onClick={onClose}>
        <XIcon className="size-4" />
      </Button>
    </div>
  );

  return (
    <div className={cn("flex flex-col w-full gap-2 py-2")}>
      {inputComponent}
      <div className="flex flex-row justify-between -mt-1 ml-1 mr-3">
        {!completion && (
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
        {completion && (
          <CompletionActions
            isLoading={isLoading}
            onAccept={handleAcceptCompletion}
            onDecline={handleDeclineCompletion}
            size="sm"
          />
        )}
        <div className="ml-auto flex items-center gap-1">
          {languageDropdown}
          <AIModelDropdown
            value={editModel}
            onSelect={(model) => {
              saveModelChange(model, "edit");
            }}
            triggerClassName="h-7 text-xs max-w-64"
            iconSize="small"
            forRole="edit"
          />
        </div>
      </div>

      {completion && (
        <ReactCodeMirror
          value={completion}
          className="cm border-t"
          onChange={setCompletion}
          theme={theme === "dark" ? "dark" : "light"}
          extensions={language === "python" ? pythonExtensions : sqlExtensions}
        />
      )}
    </div>
  );
};

export interface AdditionalCompletions {
  triggerCompletionRegex: RegExp;
  completions: Completion[];
}

interface PromptInputProps {
  inputRef?: React.RefObject<ReactCodeMirrorRef | null>;
  placeholder?: string;
  value: string;
  className?: string;
  onKeyDown?: (e: React.KeyboardEvent<HTMLDivElement>) => void;
  onClose: () => void;
  onChange: (value: string) => void;
  onSubmit: (e: KeyboardEvent | undefined, value: string) => void;
  additionalCompletions?: AdditionalCompletions;
  maxHeight?: string;
}

/**
 * CodeMirror-based input for the AI prompt.
 *
 * This is just text (no language support), but we use codemirror to get autocomplete
 * for @dataframe and @sql_table.
 */
export const PromptInput = ({
  value,
  placeholder,
  inputRef,
  className,
  onChange,
  onSubmit,
  onKeyDown,
  onClose,
  additionalCompletions,
  maxHeight,
}: PromptInputProps) => {
  const handleSubmit = onSubmit;
  const handleEscape = onClose;
  const store = useStore();
  const { theme } = useTheme();

  const additionalCompletionsSource: CompletionSource = useEvent(
    (context: CompletionContext) => {
      if (!additionalCompletions) {
        return null;
      }

      return mentionsCompletionSource(
        [additionalCompletions.triggerCompletionRegex],
        additionalCompletions.completions,
      )(context);
    },
  );

  // Changing extensions can be expensive, so
  // it is worth making sure this is memoized well.
  const extensions = useMemo(() => {
    const markdownLanguage = markdown();
    return [
      autocompletion({}),
      markdownLanguage,
      resourceExtension(markdownLanguage.language, store),
      markdownLanguage.language.data.of({
        autocomplete: additionalCompletionsSource,
      }),
      EditorView.lineWrapping,
      minimalSetup(),
      Prec.highest(
        keymap.of([
          {
            preventDefault: true,
            stopPropagation: true,
            any: (view, event) => {
              const pressedModOrShift =
                event.metaKey || event.ctrlKey || event.shiftKey;
              // If no mod key is pressed, submit
              if (event.key === "Enter" && !pressedModOrShift) {
                handleSubmit(event, view.state.doc.toString());
                event.preventDefault();
                event.stopPropagation();
                return true;
              }
              // Mod+Enter does add a new line already by codemirror
              // But Shift+Enter does not, so we need to handle it manually
              if (event.key === "Enter" && event.shiftKey) {
                const cursorPosition = view.state.selection.main.from;
                // Insert a new line
                view.dispatch({
                  changes: {
                    from: cursorPosition,
                    to: cursorPosition,
                    insert: "\n",
                  },
                  selection: {
                    anchor: cursorPosition + 1,
                    head: cursorPosition + 1,
                  },
                });
                event.preventDefault();
                event.stopPropagation();
                return true;
              }

              return false;
            },
          },
        ]),
      ),
      keymap.of([
        {
          key: "Escape",
          preventDefault: true,
          stopPropagation: true,
          run: () => {
            handleEscape();
            return true;
          },
        },
      ]),
      // Trap arrow up/down to prevent them from being used to navigate the editor
      keymap.of([
        {
          key: "ArrowUp",
          preventDefault: true,
          stopPropagation: true,
        },
      ]),
      keymap.of([
        {
          key: "ArrowDown",
          preventDefault: true,
          stopPropagation: true,
        },
      ]),
    ];
  }, [store, additionalCompletionsSource, handleSubmit, handleEscape]);

  return (
    <ReactCodeMirror
      ref={inputRef}
      className={cn("flex-1 font-sans overflow-auto my-1", className)}
      width="100%"
      maxHeight={maxHeight}
      value={value}
      basicSetup={false}
      extensions={extensions}
      onChange={onChange}
      onKeyDown={onKeyDown}
      theme={theme === "dark" ? "dark" : "light"}
      placeholder={placeholder || "Generate with AI"}
    />
  );
};
