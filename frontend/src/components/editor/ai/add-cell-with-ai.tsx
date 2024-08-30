/* Copyright 2024 Marimo. All rights reserved. */
import { useCellActions } from "../../../core/cells/cells";
import { cn } from "@/utils/cn";
import { Button } from "@/components/ui/button";
import { ChevronsUpDown, Loader2Icon, SparklesIcon, XIcon } from "lucide-react";
import { toast } from "@/components/ui/use-toast";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { API } from "@/core/network/api";
import { prettyError } from "@/utils/errors";
import { useCompletion } from "ai/react";
import ReactCodeMirror, {
  EditorView,
  keymap,
  minimalSetup,
} from "@uiw/react-codemirror";
import { Prec } from "@codemirror/state";
import { customPythonLanguageSupport } from "@/core/codemirror/language/python";
import { asURL } from "@/utils/url";
import { mentions } from "@uiw/codemirror-extensions-mentions";
import { useMemo, useState } from "react";
import { store } from "@/core/state/jotai";
import { datasetTablesAtom } from "@/core/datasets/state";
import { Logger } from "@/utils/Logger";
import { Maps } from "@/utils/maps";
import type { DataTable } from "@/core/kernel/messages";
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

const pythonExtensions = [
  customPythonLanguageSupport(),
  EditorView.lineWrapping,
];
const sqlExtensions = [sql(), EditorView.lineWrapping];

function getCompletionBody(input: string): object {
  const datasets = extractDatasets(input);
  Logger.debug("Included datasets", datasets);

  return {
    includeOtherCode: getCodes(""),
    context: {
      schema: datasets.map((dataset) => ({
        name: dataset.name,
        columns: dataset.columns.map((column) => ({
          name: column.name,
          type: column.type,
        })),
      })),
    },
    code: "",
  };
}

function extractDatasets(input: string): DataTable[] {
  const datasets = store.get(datasetTablesAtom);
  const existingDatasets = Maps.keyBy(datasets, (dataset) => dataset.name);

  // Extract dataset mentions from the input
  const mentionedDatasets = input.match(/@(\w+)/g) || [];

  // Filter to only include datasets that exist
  return mentionedDatasets
    .map((mention) => mention.slice(1))
    .map((name) => existingDatasets.get(name))
    .filter(Boolean);
}

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
    streamMode: "text",
    body: {
      ...completionBody,
      language: language,
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
        onClose={() => {
          setCompletion("");
          onClose();
        }}
        value={input}
        onChange={(newValue) => {
          setInput(newValue);
          setCompletionBody(getCompletionBody(newValue));
        }}
        onSubmit={handleSubmit}
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
        <span className="text-xs text-muted-foreground px-3">
          You can mention{" "}
          <span className="text-[var(--cyan-11)]">@dataframe</span> or{" "}
          <span className="text-[var(--cyan-11)]">@sql_table</span> to pull
          additional context such as column names.
        </span>
      )}
      {completion && (
        <ReactCodeMirror
          value={completion}
          className="cm border-t"
          onChange={setCompletion}
          extensions={language === "python" ? pythonExtensions : sqlExtensions}
        />
      )}
    </div>
  );
};

interface PromptInputProps {
  value: string;
  onClose: () => void;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

const PromptInput = ({
  value,
  onChange,
  onSubmit,
  onClose,
}: PromptInputProps) => {
  const handleSubmit = onSubmit;
  const handleEscape = onClose;
  const tables = useAtomValue(datasetTablesAtom);

  const extensions = useMemo(() => {
    const completions = tables.map(
      (table): Completion => ({
        label: `@${table.name}`,
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
              const typeCell = row.insertCell();
              typeCell.textContent = column.type;
            });

            infoContainer.append(columnsTable);
          }

          return infoContainer;
        },
      }),
    );

    return [
      mentions(completions),
      EditorView.lineWrapping,
      minimalSetup(),
      Prec.highest(
        keymap.of([
          {
            key: "Enter",
            preventDefault: true,
            stopPropagation: true,
            run: () => {
              handleSubmit();
              return true;
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
    ];
  }, [tables, handleSubmit, handleEscape]);

  return (
    <ReactCodeMirror
      className="flex-1 font-sans"
      autoFocus={true}
      width="100%"
      value={value}
      basicSetup={false}
      extensions={extensions}
      onChange={onChange}
      placeholder={"Generate with AI"}
    />
  );
};
