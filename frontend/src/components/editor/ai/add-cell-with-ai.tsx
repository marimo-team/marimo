/* Copyright 2024 Marimo. All rights reserved. */

import { useChat } from "@ai-sdk/react";
import {
  autocompletion,
  type Completion,
  type CompletionContext,
  type CompletionSource,
} from "@codemirror/autocomplete";
import { markdown } from "@codemirror/lang-markdown";
import { Prec } from "@codemirror/state";
import { promptHistory, storePrompt } from "@marimo-team/codemirror-ai";
import ReactCodeMirror, {
  EditorView,
  keymap,
  minimalSetup,
  type ReactCodeMirrorRef,
} from "@uiw/react-codemirror";
import { DefaultChatTransport } from "ai";
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
import { useEffect, useMemo, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { z } from "zod";
import { AIModelDropdown } from "@/components/ai/ai-model-dropdown";
import {
  buildCompletionRequestBody,
  handleToolCall,
} from "@/components/chat/chat-utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { toast } from "@/components/ui/use-toast";
import { stagedAICellsAtom, useStagedCells } from "@/core/ai/staged-cells";
import type { CellId } from "@/core/cells/ids";
import { resourceExtension } from "@/core/codemirror/ai/resources";
import { useRequestClient } from "@/core/network/requests";
import type { AiCompletionRequest } from "@/core/network/types";
import { useRuntimeManager } from "@/core/runtime/config";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { prettyError } from "@/utils/errors";
import { ZodLocalStorage } from "@/utils/localStorage";
import { PythonIcon } from "../cell/code/icons";
import {
  CompletionActions,
  createAiCompletionOnKeydown,
} from "./completion-handlers";
import {
  CONTEXT_TRIGGER,
  codeToCells,
  mentionsCompletionSource,
} from "./completion-utils";

// Persist across sessions
const languageAtom = atomWithStorage<"python" | "sql">(
  "marimo:ai-language",
  "python",
);

const KEY = "marimo:ai-prompt-history";
// Store the prompt history in local storage
const promptHistoryStorage = new ZodLocalStorage(z.array(z.string()), () => []);

/**
 * Add a cell with AI.
 */
export const AddCellWithAI: React.FC<{
  onClose: () => void;
}> = ({ onClose }) => {
  const [input, setInput] = useState("");
  const {
    deleteAllStagedCells,
    clearStagedCells,
    createStagedCell,
    updateStagedCell,
  } = useStagedCells();
  const [language, setLanguage] = useAtom(languageAtom);
  const runtimeManager = useRuntimeManager();
  const { invokeAiTool } = useRequestClient();

  const stagedAICells = useAtomValue(stagedAICellsAtom);
  const inputRef = useRef<ReactCodeMirrorRef>(null);

  const { messages, sendMessage, stop, status, addToolResult } = useChat({
    // Throttle the messages and data updates to 100ms
    experimental_throttle: 100,
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
          code: "",
          prompt: "", // Don't need prompt since we are using messages
          language: language,
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
        title: "Generate with AI failed",
        description: prettyError(error),
      });
    },
  });

  const aiResponses = messages.filter((m) => m.role === "assistant");
  const textResponse = aiResponses
    .flatMap((m) =>
      m.parts?.filter((p) => p.type === "text").map((p) => p.text),
    )
    .join("\n");
  const codeCells = codeToCells(textResponse);

  const [createdCells, setCreatedCells] = useState<CellId[]>([]);
  useEffect(() => {
    const newCells = codeCells.slice(createdCells.length);
    for (const cell of newCells) {
      const cellId = createStagedCell(cell.code);
      setCreatedCells((prev) => [...prev, cellId]);
    }

    const updatedCells = codeCells.slice(0, createdCells.length);
    for (const [idx, cell] of updatedCells.entries()) {
      const cellIdToUpdate = createdCells[idx];
      updateStagedCell(cellIdToUpdate, cell.code);
    }
  }, [codeCells, createStagedCell, createdCells, updateStagedCell]);

  const isLoading = status === "streaming" || status === "submitted";
  const hasCompletion = stagedAICells.cellIds.size > 0;
  const multipleCompletions = stagedAICells.cellIds.size > 1;

  const submit = () => {
    if (!isLoading) {
      if (inputRef.current?.view) {
        storePrompt(inputRef.current.view);
      }
      // TODO: When we have conversations, don't delete existing cells
      deleteAllStagedCells();
      sendMessage({ text: input });
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
    clearStagedCells();
    onClose();
  };

  const handleDeclineCompletion = () => {
    deleteAllStagedCells();
  };

  const inputComponent = (
    <div className="flex items-center px-3">
      <SparklesIcon className="size-4 text-(--blue-11) mr-2" />
      <PromptInput
        inputRef={inputRef}
        onClose={() => {
          deleteAllStagedCells();
          onClose();
        }}
        value={input}
        onChange={(newValue) => {
          setInput(newValue);
        }}
        onSubmit={submit}
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
          <CompletionActions
            isLoading={isLoading}
            onAccept={handleAcceptCompletion}
            onDecline={handleDeclineCompletion}
            size="sm"
            multipleCompletions={multipleCompletions}
          />
        )}
        <div className="ml-auto flex items-center gap-1">
          {languageDropdown}
          <AIModelDropdown
            triggerClassName="h-7 text-xs max-w-64"
            iconSize="small"
            forRole="edit"
          />
        </div>
      </div>
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
  onAddFiles?: (files: File[]) => void;
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
  onAddFiles,
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
      resourceExtension({
        language: markdownLanguage.language,
        store,
        onAddFiles,
      }),
      markdownLanguage.language.data.of({
        autocomplete: additionalCompletionsSource,
      }),
      promptHistory({
        storage: {
          load: () => promptHistoryStorage.get(KEY),
          save: (prompts) => promptHistoryStorage.set(KEY, prompts),
        },
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
    ];
  }, [
    store,
    onAddFiles,
    additionalCompletionsSource,
    handleSubmit,
    handleEscape,
  ]);

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
      placeholder={
        placeholder || `Generate with AI, ${CONTEXT_TRIGGER} to include context`
      }
    />
  );
};
