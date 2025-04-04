/* Copyright 2024 Marimo. All rights reserved. */
import { useCellActions } from "../../../core/cells/cells";
import { cn } from "@/utils/cn";
import { Button } from "@/components/ui/button";
import { ChevronsUpDown, Loader2Icon, SparklesIcon, XIcon } from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { API } from "@/core/network/api";
import { prettyError } from "@/utils/errors";
import { useCompletion } from "ai/react";
import ReactCodeMirror, {
  EditorView,
  keymap,
  minimalSetup,
  type ReactCodeMirrorRef,
} from "@uiw/react-codemirror";
import { Prec } from "@codemirror/state";
import { customPythonLanguageSupport } from "@/core/codemirror/language/python";
import { asURL } from "@/utils/url";
import { useMemo, useState } from "react";
import { useAtom, useAtomValue } from "jotai";
import type { Completion } from "@codemirror/autocomplete";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import { sql } from "@codemirror/lang-sql";
import { SQLLanguageAdapter } from "@/core/codemirror/language/sql";
import { atomWithStorage } from "jotai/utils";
import { type ResolvedTheme, useTheme } from "@/theme/useTheme";
import { getAICompletionBody, mentions } from "./completion-utils";
import { allTablesAtom } from "@/core/datasets/data-source-connections";
import type { DataTable } from "@/core/kernel/messages";

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

  const extensions = useMemo(() => {
    const completions = [...tablesMap.entries()].map(
      ([tableName, table]): Completion => ({
        label: `@${tableName}`,
        detail: table.source,
        boost: table.source_type === "local" ? 5 : 0,
        info: () => {
          const shape = [
            table.num_rows == null ? undefined : `${table.num_rows} rows`,
            table.num_columns == null
              ? undefined
              : `${table.num_columns} columns`,
          ]
            .filter(Boolean)
            .join(", ");

          const infoContainer = document.createElement("div");
          infoContainer.classList.add("prose", "prose-sm", "dark:prose-invert");

          if (shape) {
            const shapeElement = document.createElement("div");
            shapeElement.textContent = shape;
            shapeElement.style.fontWeight = "bold";
            infoContainer.append(shapeElement);
          }

          if (table.source) {
            const sourceElement = document.createElement("figcaption");
            sourceElement.textContent = `Source: ${table.source}`;
            infoContainer.append(sourceElement);
          }

          if (table.columns) {
            const columnsTable = document.createElement("table");
            const headerRow = columnsTable.insertRow();
            const nameHeader = headerRow.insertCell();
            nameHeader.textContent = "Column";
            nameHeader.style.fontWeight = "bold";
            const typeHeader = headerRow.insertCell();
            typeHeader.textContent = "Type";
            typeHeader.style.fontWeight = "bold";

            table.columns.forEach((column) => {
              const row = columnsTable.insertRow();
              const nameCell = row.insertCell();

              nameCell.textContent = column.name;
              const itemMetadata = getItemMetadata(table, column);
              if (itemMetadata) {
                nameCell.append(itemMetadata);
              }

              const typeCell = row.insertCell();
              typeCell.textContent = column.type;
            });

            infoContainer.append(columnsTable);
          }

          return infoContainer;
        },
      }),
    );

    // Trigger autocompletion for text that begins with @, can contain dots
    const matchBeforeRegexes = [/@([\w.]+)?/];
    if (additionalCompletions) {
      matchBeforeRegexes.push(additionalCompletions.triggerCompletionRegex);
    }
    const allCompletions = additionalCompletions
      ? [...completions, ...additionalCompletions.completions]
      : completions;

    return [
      mentions(matchBeforeRegexes, allCompletions),
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
  }, [tablesMap, additionalCompletions, handleSubmit, handleEscape]);

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

function getItemMetadata(
  table: DataTable,
  column: DataTable["columns"][0],
): HTMLSpanElement | undefined {
  const isPrimaryKey = table.primary_keys?.includes(column.name);
  const isIndexed = table.indexes?.includes(column.name);
  if (isPrimaryKey || isIndexed) {
    const subtext = document.createElement("span");
    subtext.textContent = isPrimaryKey ? "PK" : "IDX";
    subtext.classList.add(
      "text-xs",
      "text-black",
      "bg-gray-100",
      "dark:invert",
      "rounded",
      "px-1",
      "ml-1",
    );
    return subtext;
  }
}
