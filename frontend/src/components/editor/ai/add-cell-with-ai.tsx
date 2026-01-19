/* Copyright 2026 Marimo. All rights reserved. */

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
import { useAtom, useAtomValue, useStore } from "jotai";
import { atomWithStorage } from "jotai/utils";
import {
  AtSignIcon,
  ChevronsUpDown,
  DatabaseIcon,
  Loader2Icon,
  PaperclipIcon,
  SendHorizontal,
  SparklesIcon,
  XIcon,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import { z } from "zod";
import { AIModelDropdown } from "@/components/ai/ai-model-dropdown";
import { FileAttachmentPill } from "@/components/chat/chat-components";
import {
  buildCompletionRequestBody,
  convertToFileUIPart,
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
import { Input } from "@/components/ui/input";
import { Tooltip } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { AiModelId } from "@/core/ai/ids/ids";
import { stagedAICellsAtom, useStagedCells } from "@/core/ai/staged-cells";
import type { ToolNotebookContext } from "@/core/ai/tools/base";
import { useCellActions } from "@/core/cells/cells";
import { resourceExtension } from "@/core/codemirror/ai/resources";
import { aiAtom } from "@/core/config/config";
import { DEFAULT_AI_MODEL } from "@/core/config/config-schema";
import { useRequestClient } from "@/core/network/requests";
import type { AiCompletionRequest } from "@/core/network/types";
import { useRuntimeManager } from "@/core/runtime/config";
import { useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { prettyError } from "@/utils/errors";
import { jotaiJsonStorage } from "@/utils/storage/jotai";
import { ZodLocalStorage } from "@/utils/storage/typed";
import { PythonIcon } from "../cell/code/icons";
import { createAiCompletionOnKeydown } from "./completion-handlers";
import {
  addContextCompletion,
  CONTEXT_TRIGGER,
  mentionsCompletionSource,
} from "./completion-utils";
import { StreamingChunkTransport } from "./transport/chat-transport";

// File attachment support
const PROVIDERS_THAT_SUPPORT_ATTACHMENTS = new Set([
  "openai",
  "google",
  "anthropic",
] as const);
const SUPPORTED_ATTACHMENT_TYPES = ["image/*", "text/*"];
const MAX_ATTACHMENT_SIZE = 1024 * 1024 * 50; // 50MB

// Persist across sessions
const languageAtom = atomWithStorage<"python" | "sql">(
  "marimo:ai-language",
  "python",
  jotaiJsonStorage,
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
  const store = useStore();
  const [input, setInput] = useState("");

  const { deleteAllStagedCells, clearStagedCells, onStream, addStagedCell } =
    useStagedCells(store);
  const [language, setLanguage] = useAtom(languageAtom);
  const runtimeManager = useRuntimeManager();
  const { invokeAiTool, sendRun } = useRequestClient();

  const stagedAICells = useAtomValue(stagedAICellsAtom);
  const inputRef = useRef<ReactCodeMirrorRef>(null);

  // File attachment state
  const [files, setFiles] = useState<File[]>();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const ai = useAtomValue(aiAtom);

  const { createNewCell, prepareForRun } = useCellActions();
  const toolContext: ToolNotebookContext = {
    store,
    addStagedCell,
    createNewCell,
    prepareForRun,
    sendRun,
  };

  const { sendMessage, stop, status, addToolOutput } = useChat({
    // Throttle the messages and data updates to 100ms
    experimental_throttle: 100,
    transport: new StreamingChunkTransport(
      {
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
      },
      (chunk) => {
        onStream(chunk);
      },
    ),
    onToolCall: async ({ toolCall }) => {
      await handleToolCall({
        invokeAiTool,
        addToolOutput,
        toolCall: {
          toolName: toolCall.toolName,
          toolCallId: toolCall.toolCallId,
          input: toolCall.input as Record<string, never>,
        },
        toolContext,
      });
    },
    onError: (error) => {
      toast({
        title: "Generate with AI failed",
        description: prettyError(error),
      });
    },
  });

  const isLoading = status === "streaming" || status === "submitted";
  const hasCompletion = stagedAICells.size > 0;

  const submit = async () => {
    if (!isLoading) {
      if (inputRef.current?.view) {
        storePrompt(inputRef.current.view);
      }
      // TODO: When we have conversations, don't delete existing cells
      deleteAllStagedCells();

      // Convert files to FileUIPart format if present
      const fileParts = files ? await convertToFileUIPart(files) : undefined;

      sendMessage({ text: input, files: fileParts });

      // Clear files after sending
      setFiles(undefined);
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
      <DropdownMenuTrigger
        className="flex items-center justify-between h-7 text-xs px-2 py-0.5 border rounded-md hover:text-accent-foreground"
        data-testid="language-button"
      >
        {language === "python" ? pythonIcon : sqlIcon}
        <ChevronsUpDown className="ml-1 h-3.5 w-3.5 text-muted-foreground/70" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="center">
        <div className="px-2 py-1 font-semibold">Generate</div>
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

  // Determine if provider supports attachments
  const currentModel = ai?.models?.chat_model || DEFAULT_AI_MODEL;
  const currentProvider = AiModelId.parse(currentModel).providerId;
  const isAttachmentSupported = PROVIDERS_THAT_SUPPORT_ATTACHMENTS.has(
    currentProvider as "openai" | "google" | "anthropic",
  );

  const handleAddContext = () => {
    addContextCompletion(inputRef);
  };

  const onAddFiles = useEvent((newFiles: File[]) => {
    if (newFiles.length === 0) {
      return;
    }

    let fileSize = 0;
    for (const file of newFiles) {
      fileSize += file.size;
    }

    if (fileSize > MAX_ATTACHMENT_SIZE) {
      toast({
        title: "File size exceeds 50MB limit",
        variant: "danger",
      });
      return;
    }

    setFiles((prev) => [...(prev ?? []), ...newFiles]);
  });

  const removeFile = (fileToRemove: File) => {
    setFiles((prev) => prev?.filter((f) => f !== fileToRemove));
  };

  const handleAcceptCompletion = () => {
    clearStagedCells();
    onClose();
  };

  const handleDeclineCompletion = () => {
    deleteAllStagedCells();
  };

  const inputComponent = (
    <div className="flex items-start px-3">
      <SparklesIcon className="size-4 text-(--blue-11) mt-3 mr-2" />
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
        onAddFiles={onAddFiles}
        onKeyDown={createAiCompletionOnKeydown({
          handleAcceptCompletion,
          handleDeclineCompletion,
          isLoading,
          hasCompletion,
        })}
      />
      <Button variant="text" size="sm" className="mb-0 px-1" onClick={onClose}>
        <XIcon className="size-4" />
      </Button>
    </div>
  );

  const filesPills =
    files && files.length > 0 ? (
      <div className="flex flex-row gap-1 flex-wrap pl-10 pr-3 pt-1 pb-2">
        {files?.map((file, index) => (
          <FileAttachmentPill
            file={file}
            key={`${file.name}-${index}`}
            onRemove={() => removeFile(file)}
          />
        ))}
      </div>
    ) : null;

  const footerComponent = (
    <div className="px-3 pt-2 border-t border-border/20 flex flex-row items-center justify-between">
      <div className="flex items-center gap-2">
        <AIModelDropdown
          triggerClassName="h-7 text-xs max-w-64"
          iconSize="small"
          forRole="edit"
        />
        {languageDropdown}
      </div>
      <div className="flex flex-row items-center">
        <Tooltip content="Add context">
          <Button
            variant="text"
            size="icon"
            onClick={handleAddContext}
            disabled={isLoading}
          >
            <AtSignIcon className="h-3.5 w-3.5" />
          </Button>
        </Tooltip>
        {isAttachmentSupported && (
          <>
            <Tooltip content="Attach a file">
              <Button
                variant="text"
                size="icon"
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading}
              >
                <PaperclipIcon className="h-3.5 w-3.5" />
              </Button>
            </Tooltip>
            <Input
              ref={fileInputRef}
              type="file"
              multiple={true}
              hidden={true}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) => {
                if (event.target.files) {
                  onAddFiles([...event.target.files]);
                }
              }}
              accept={SUPPORTED_ATTACHMENT_TYPES.join(",")}
            />
          </>
        )}
        <Tooltip content={isLoading ? "Stop" : "Submit"}>
          <Button
            variant="text"
            size="sm"
            className="h-6 w-6 p-0 hover:bg-muted/30 cursor-pointer"
            onClick={isLoading ? stop : submit}
            disabled={isLoading ? false : !input.trim()}
          >
            {isLoading ? (
              <Loader2Icon className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <SendHorizontal className="h-3.5 w-3.5" />
            )}
          </Button>
        </Tooltip>
      </div>
    </div>
  );

  return (
    <div className={cn("flex flex-col w-full py-2")}>
      {inputComponent}
      {filesPills}
      {footerComponent}
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
      minHeight="3.5em"
      maxHeight={maxHeight}
      value={value}
      basicSetup={false}
      extensions={extensions}
      onChange={onChange}
      onKeyDown={onKeyDown}
      theme={theme === "dark" ? "dark" : "light"}
      placeholder={
        placeholder ||
        `Generate with AI, ${CONTEXT_TRIGGER} to include context about tables or dataframes.\nCode from other cells is automatically included. `
      }
    />
  );
};
