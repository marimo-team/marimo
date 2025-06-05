/* Copyright 2024 Marimo. All rights reserved. */
import { useCellActions } from "../../../core/cells/cells";
import { cn } from "@/utils/cn";
import { Button } from "@/components/ui/button";
import { ChevronsUpDown, Loader2Icon, SparklesIcon, XIcon } from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { prettyError } from "@/utils/errors";
import { useCompletion } from "ai/react";
import ReactCodeMirror, {
  EditorView,
  keymap,
  minimalSetup,
  type ReactCodeMirrorRef,
} from "@uiw/react-codemirror";
import { Prec } from "@codemirror/state";
import { customPythonLanguageSupport } from "@/core/codemirror/language/languages/python";
import { useMemo, useState } from "react";
import { useAtom, useAtomValue } from "jotai";
import {
  autocompletion,
  type Completion,
  type CompletionContext,
  type CompletionSource,
} from "@codemirror/autocomplete";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { sql } from "@codemirror/lang-sql";
import { SQLLanguageAdapter } from "@/core/codemirror/language/languages/sql";
import { atomWithStorage } from "jotai/utils";
import { type ResolvedTheme, useTheme } from "@/theme/useTheme";
import {
  getAICompletionBody,
  mentionsCompletionSource,
} from "./completion-utils";
import { allTablesAtom } from "@/core/datasets/data-source-connections";
import { variablesAtom } from "@/core/variables/state";
import {
  getTableMentionCompletions,
  getVariableMentionCompletions,
} from "./completions";
import useEvent from "react-use-event-hook";
import { useRuntimeManager } from "@/core/runtime/config";

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

  const inputComponent = (
    <div className="flex items-center px-3">
      <SparklesIcon className="size-4 text-[var(--blue-11)]" />
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild={true}>
          <Button
            variant="text"
            className="ml-2"
            size="xs"
            data-testid="language-button"
          >
            {language === "python" ? "Python" : "SQL"}
            <ChevronsUpDown className="ml-1 h-3.5 w-3.5 text-muted-foreground/70" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="center">
          <DropdownMenuItem onClick={() => setLanguage("python")}>
            Python
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setLanguage("sql")}>
            SQL
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <PromptInput
        theme={theme}
        onClose={() => {
          setCompletion("");
          onClose();
        }}
        value={input}
        onChange={(newValue) => {
          setInput(newValue);
          setCompletionBody(getAICompletionBody({ input: newValue }));
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
              code:
                language === "python"
                  ? completion
                  : SQLLanguageAdapter.fromQuery(completion),
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
    <div className={cn("flex flex-col w-full gap-2 py-2")}>
      {inputComponent}
      {!completion && (
        <span className="text-xs text-muted-foreground px-3 flex flex-col gap-1">
          <span>
            You can mention{" "}
            <span className="text-[var(--cyan-11)]">@dataframe</span> or{" "}
            <span className="text-[var(--cyan-11)]">@sql_table</span> to pull
            additional context such as column names.
          </span>
          <span>Code from other cells is automatically included.</span>
        </span>
      )}
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
  inputRef?: React.RefObject<ReactCodeMirrorRef>;
  placeholder?: string;
  value: string;
  className?: string;
  onClose: () => void;
  onChange: (value: string) => void;
  onSubmit: (e: KeyboardEvent | undefined, value: string) => void;
  additionalCompletions?: AdditionalCompletions;
  theme: ResolvedTheme;
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
  onClose,
  additionalCompletions,
  theme,
  maxHeight,
}: PromptInputProps) => {
  const handleSubmit = onSubmit;
  const handleEscape = onClose;
  const tablesMap = useAtomValue(allTablesAtom);
  const variables = useAtomValue(variablesAtom);

  // TablesMap and variable change a lot,
  // so we use useEvent to memoize the completion source
  const completionSource: CompletionSource = useEvent(
    (context: CompletionContext) => {
      const completions = [
        ...getTableMentionCompletions(tablesMap),
        ...getVariableMentionCompletions(variables, tablesMap),
      ];

      // Trigger autocompletion for text that begins with @, can contain dots
      const matchBeforeRegexes = [/@([\w.]+)?/];
      if (additionalCompletions) {
        matchBeforeRegexes.push(additionalCompletions.triggerCompletionRegex);
        completions.push(...additionalCompletions.completions);
      }

      return mentionsCompletionSource(matchBeforeRegexes, completions)(context);
    },
  );

  // Changing extensions can be expensive, so
  // it is worth making sure this is memoized well.
  const extensions = useMemo(() => {
    return [
      autocompletion({
        override: [completionSource],
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
  }, [completionSource, handleSubmit, handleEscape]);

  return (
    <ReactCodeMirror
      ref={inputRef}
      className={cn("flex-1 font-sans overflow-auto my-1", className)}
      autoFocus={true}
      width="100%"
      maxHeight={maxHeight}
      value={value}
      basicSetup={false}
      extensions={extensions}
      onChange={onChange}
      theme={theme === "dark" ? "dark" : "light"}
      placeholder={placeholder || "Generate with AI"}
    />
  );
};
