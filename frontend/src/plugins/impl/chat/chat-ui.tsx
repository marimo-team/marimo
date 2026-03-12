/* Copyright 2026 Marimo. All rights reserved. */

import { type UIMessage, useChat } from "@ai-sdk/react";
import { ChatBubbleIcon } from "@radix-ui/react-icons";
import { PopoverAnchor } from "@radix-ui/react-popover";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import {
  createUIMessageStreamResponse,
  DefaultChatTransport,
  type TextUIPart,
  type UIMessageChunk,
} from "ai";
import { startCase } from "lodash-es";
import {
  BotMessageSquareIcon,
  HelpCircleIcon,
  PaperclipIcon,
  RotateCwIcon,
  SendHorizontalIcon,
  SettingsIcon,
  Trash2Icon,
  X,
} from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { renderUIMessage } from "@/components/chat/chat-display";
import { convertToFileUIPart } from "@/components/chat/chat-utils";
import {
  type AdditionalCompletions,
  PromptInput,
} from "@/components/editor/ai/add-cell-with-ai";
import { CopyClipboardIcon } from "@/components/icons/copy-icon";
import { Spinner } from "@/components/icons/spinner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NumberField } from "@/components/ui/number-field";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Tooltip } from "@/components/ui/tooltip";
import { moveToEndOfEditor } from "@/core/codemirror/utils";
import { MarimoIncomingMessageEvent } from "@/core/dom/events";
import { useAsyncData } from "@/hooks/useAsyncData";
import {
  type HTMLElementNotDerivedFromRef,
  useEventListener,
} from "@/hooks/useEventListener";
import { cn } from "@/utils/cn";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import { ErrorBanner } from "../common/error-banner";
import type { PluginFunctions } from "./ChatPlugin";
import type { ChatConfig } from "./types";

interface Props extends PluginFunctions {
  prompts: string[];
  config: ChatConfig;
  showConfigurationControls: boolean;
  maxHeight: number | undefined;
  allowAttachments: boolean | string[];
  disabled: boolean;
  value: UIMessage[];
  setValue: (messages: UIMessage[]) => void;
  host: HTMLElement;
}

const ChatMessageIncomingSchema = z.object({
  type: z.literal("stream_chunk"),
  message_id: z.string(),
  content: z
    .any()
    .nullable()
    .transform((val) => val as UIMessageChunk | null),
  is_final: z.boolean().optional(),
});

export const Chatbot: React.FC<Props> = (props) => {
  const [input, setInput] = useState("");
  const [config, setConfig] = useState<ChatConfig>(props.config);
  const [prevPropsConfig, setPrevPropsConfig] = useState<ChatConfig>(
    props.config,
  );
  const [files, setFiles] = useState<File[] | undefined>(undefined);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const codeMirrorInputRef = useRef<ReactCodeMirrorRef>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const configChanged = Object.keys(props.config).some(
    (key) =>
      props.config[key as keyof ChatConfig] !==
      prevPropsConfig[key as keyof ChatConfig],
  );

  if (configChanged) {
    setConfig(props.config);
    setPrevPropsConfig(props.config);
  }

  // Use a ref to avoid stale closure in the fetch callback
  const configRef = useRef<ChatConfig>(config);
  configRef.current = config;

  // Track streaming state - maps backend message_id to frontend message index
  const streamingStateRef = useRef<{
    backendMessageId: string | null;
    frontendMessageIndex: number | null;
  }>({ backendMessageId: null, frontendMessageIndex: null });

  // For frontend-managed streaming, create a controller to enqueue chunks to.
  const frontendStreamControllerRef =
    useRef<ReadableStreamDefaultController<UIMessageChunk> | null>(null);

  const { data: backendMessages } = useAsyncData(async () => {
    const response = await props.get_chat_history({});
    return response.messages;
  }, []);

  // Use props.value (persisted plugin state) if available,
  // otherwise fall back to backend messages.
  // This ensures messages persist when switching between edit/app views.
  const initialMessages =
    props.value.length > 0 ? props.value : backendMessages;

  const {
    messages,
    sendMessage,
    setMessages,
    status,
    stop,
    error,
    regenerate,
    clearError,
  } = useChat({
    transport: new DefaultChatTransport({
      fetch: async (
        request: RequestInfo | URL,
        init: RequestInit | undefined,
      ) => {
        if (init === undefined) {
          return fetch(request);
        }

        const body = JSON.parse(init.body as unknown as string) as {
          messages: UIMessage[];
        };

        // Catch signals like abort to stop the stream (when stop function is called from useChat)
        const signal = init.signal;

        const chatConfig: ChatConfig = {
          max_tokens: configRef.current.max_tokens,
          temperature: configRef.current.temperature,
          top_p: configRef.current.top_p,
          top_k: configRef.current.top_k,
          frequency_penalty: configRef.current.frequency_penalty,
          presence_penalty: configRef.current.presence_penalty,
        };

        try {
          // Content is added for backwards compatibility
          const messages = body.messages.map((m) => {
            return {
              ...m,
              content: m.parts
                ?.map((p) => ("text" in p ? p.text : ""))
                .join("\n"),
            };
          });

          const stream = new ReadableStream<UIMessageChunk>({
            start(controller) {
              frontendStreamControllerRef.current = controller;

              const abortHandler = () => {
                try {
                  controller.close();
                } catch (error) {
                  Logger.debug("Controller may already be closed", { error });
                }
                frontendStreamControllerRef.current = null;
              };
              signal?.addEventListener("abort", abortHandler);

              return () => {
                signal?.removeEventListener("abort", abortHandler);
              };
            },
            cancel() {
              frontendStreamControllerRef.current = null;
            },
          });

          // Start the prompt, chunks will be sent via events
          void props
            .send_prompt({
              messages: messages,
              config: chatConfig,
            })
            .catch((error: Error) => {
              frontendStreamControllerRef.current?.error(error);
              frontendStreamControllerRef.current = null;
            });

          return createUIMessageStreamResponse({ stream });
        } catch (error: unknown) {
          // Clear streaming state on error
          streamingStateRef.current = {
            backendMessageId: null,
            frontendMessageIndex: null,
          };

          // Handle abort gracefully without showing an error
          if (error instanceof Error && error.name === "AbortError") {
            return new Response("Aborted", { status: 499 });
          }

          // HACK: strip the error message to clean up the response
          const strippedError = (error as Error).message
            ?.split("failed with exception ")
            .pop();
          return new Response(strippedError, { status: 400 });
        }
      },
    }),
    messages: initialMessages,
    onFinish: (message) => {
      setFiles(undefined);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      Logger.debug("Finished streaming message:", message);

      // Clear streaming state
      streamingStateRef.current = {
        backendMessageId: null,
        frontendMessageIndex: null,
      };

      props.setValue(message.messages);
    },
    onError: (error) => {
      Logger.error("An error occurred:", error);
      // Clear streaming state on error
      streamingStateRef.current = {
        backendMessageId: null,
        frontendMessageIndex: null,
      };
    },
  });

  // Listen for streaming chunks from backend
  useEventListener(
    props.host as HTMLElementNotDerivedFromRef,
    MarimoIncomingMessageEvent.TYPE,
    (e) => {
      const parsedMessage = ChatMessageIncomingSchema.safeParse(
        e.detail.message,
      );
      if (!parsedMessage.success) {
        return;
      }
      const message = parsedMessage.data;

      // Push to the stream for useChat to process
      const controller = frontendStreamControllerRef.current;
      if (!controller) {
        return;
      }

      if (message.content) {
        controller.enqueue(message.content);
      }
      if (message.is_final) {
        controller.close();
        frontendStreamControllerRef.current = null;
      }

      return;
    },
  );

  const isLoading = status === "submitted" || status === "streaming";

  const handleDelete = (id: string) => {
    const index = messages.findIndex((message) => message.id === id);
    if (index !== -1) {
      const newMessages = messages.filter((message) => message.id !== id);
      props.delete_chat_message({ index });
      setMessages(newMessages);

      props.setValue(newMessages);
    }
  };

  const shouldShowAttachments =
    (Array.isArray(props.allowAttachments) &&
      props.allowAttachments.length > 0) ||
    props.allowAttachments === true;

  const promptCompletions: AdditionalCompletions = {
    // sentence has to begin with '/' to trigger autocomplete
    triggerCompletionRegex: /^\/(\w+)?/,
    completions: props.prompts.map((prompt) => ({
      label: `/${prompt}`,
      displayLabel: prompt,
      apply: prompt,
    })),
  };
  const promptInputPlaceholder =
    props.prompts.length > 0
      ? "Type your message here, / for prompts"
      : "Type your message here...";

  useEffect(() => {
    // When the message length changes, scroll to the bottom
    scrollContainerRef.current?.scrollTo({
      top: scrollContainerRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages.length, scrollContainerRef]);

  const codemirrorView = codeMirrorInputRef.current?.view;

  const resetInput = () => {
    // Clear input immediately by directly manipulating the editor
    // There is some delay if we use setInput("") only
    if (codemirrorView) {
      const docLength = codemirrorView.state.doc.length;
      codemirrorView.dispatch({
        changes: { from: 0, to: docLength, insert: "" },
      });
    }
    setInput("");
  };

  const resetChatbot = () => {
    setMessages([]);
    props.setValue([]);
    props.delete_chat_history({});
    clearError();
  };

  return (
    <div
      className="flex flex-col h-full bg-(--slate-1) rounded-lg shadow border border-(--slate-6) overflow-hidden relative"
      style={{ maxHeight: props.maxHeight }}
    >
      <div className="absolute top-0 right-0 flex justify-end z-10 border border-(--slate-6) bg-inherit rounded-bl-lg">
        <Button
          variant="text"
          size="icon"
          disabled={messages.length === 0}
          onClick={resetChatbot}
        >
          <RotateCwIcon className="h-3 w-3" />
        </Button>
      </div>
      <div
        className="grow overflow-y-auto gap-4 pt-8 pb-4 px-2 flex flex-col"
        ref={scrollContainerRef}
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-center p-4">
            <BotMessageSquareIcon className="h-12 w-12 mb-4" />
            <h3 className="text-lg font-semibold mb-2">No messages yet</h3>
            <p className="text-sm">
              Start a conversation by typing a message below.
            </p>
          </div>
        )}
        {messages.map((message, index) => {
          const textContent = message.parts
            ?.filter((p): p is TextUIPart => p.type === "text")
            .map((p) => p.text)
            .join("\n");
          const isLast = index === messages.length - 1;

          return (
            <div
              key={`${message.id}-${index}`}
              className={cn(
                "flex flex-col group gap-2",
                message.role === "user" ? "items-end" : "items-start",
              )}
            >
              <div
                className={`max-w-[80%] p-3 rounded-lg ${
                  message.role === "user"
                    ? "bg-(--sky-11) text-(--slate-1) whitespace-pre-wrap"
                    : "bg-(--slate-4) text-(--slate-12)"
                }`}
              >
                {renderUIMessage({
                  message,
                  isStreamingReasoning: status === "streaming",
                  isLast,
                })}
              </div>
              <div className="flex justify-end text-xs gap-2 invisible group-hover:visible">
                <CopyClipboardIcon
                  value={textContent}
                  className="h-3 w-3"
                  buttonClassName="text-xs text-(--slate-9) hover:text-(--slate-11)"
                />
                <button
                  type="button"
                  onClick={() => handleDelete(message.id)}
                  className="text-xs text-(--slate-9) hover:text-(--slate-11)"
                >
                  <Trash2Icon className="h-3 w-3 text-(--red-9)" />
                </button>
              </div>
            </div>
          );
        })}

        {isLoading && (
          <div className="flex items-center justify-center space-x-2 mb-4">
            <Spinner size="small" />
            <Button
              variant="link"
              size="sm"
              onClick={() => stop()}
              className="text-(--red-9) hover:text-(--red-11)"
            >
              Stop
            </Button>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center space-x-2 mb-4">
            <ErrorBanner error={error} />
            <Button variant="outline" size="sm" onClick={() => regenerate()}>
              Retry
            </Button>
          </div>
        )}
      </div>
      <form
        onSubmit={async (evt) => {
          evt.preventDefault();
          if (props.disabled) {
            return;
          }

          const fileParts = files
            ? await convertToFileUIPart(files)
            : undefined;

          sendMessage({
            role: "user",
            parts: [{ type: "text", text: input }, ...(fileParts ?? [])],
          });
          resetInput();
        }}
        ref={formRef}
        // biome-ignore lint/a11y/useSemanticElements: inert is used to disable the entire form
        inert={props.disabled || undefined}
        className={cn(
          "flex w-full border-t border-(--slate-6) px-2 py-1 items-center",
          props.disabled && "opacity-50 cursor-not-allowed",
        )}
      >
        {props.showConfigurationControls && (
          <ConfigPopup config={config} onChange={setConfig} />
        )}
        {props.prompts.length > 0 && (
          <PromptsPopover
            prompts={props.prompts}
            onSelect={(prompt) => {
              setInput(prompt);
              requestAnimationFrame(() => {
                codemirrorView?.focus();
                moveToEndOfEditor(codemirrorView);
              });
            }}
          />
        )}
        <PromptInput
          className="rounded-sm mr-2"
          placeholder={promptInputPlaceholder}
          value={input}
          inputRef={codeMirrorInputRef}
          maxHeight={props.maxHeight ? `${props.maxHeight / 2}px` : undefined}
          onChange={setInput}
          onSubmit={(_evt, newValue) => {
            if (!newValue.trim()) {
              return;
            }
            formRef.current?.requestSubmit();
          }}
          onClose={() => {
            // no-op
          }}
          additionalCompletions={promptCompletions}
        />
        {files && files.length === 1 && (
          <span
            title={files[0].name}
            className="text-sm text-(--slate-11) truncate shrink-0 w-fit max-w-24"
          >
            {files[0].name}
          </span>
        )}
        {files && files.length > 1 && (
          <span
            title={[...files].map((f) => f.name).join("\n")}
            className="text-sm text-(--slate-11) truncate shrink-0"
          >
            {files.length} files
          </span>
        )}
        {files && files.length > 0 && (
          <Button
            type="button"
            variant="text"
            size="sm"
            onClick={() => {
              setFiles(undefined);

              if (fileInputRef.current) {
                fileInputRef.current.value = "";
              }
            }}
          >
            <X className="size-3" />
          </Button>
        )}
        {shouldShowAttachments && (
          <>
            <Button
              type="button"
              variant="text"
              size="sm"
              onClick={() => fileInputRef.current?.click()}
            >
              <PaperclipIcon className="h-4" />
            </Button>
            <input
              type="file"
              ref={fileInputRef}
              className="hidden"
              multiple={true}
              accept={
                Array.isArray(props.allowAttachments)
                  ? props.allowAttachments.join(",")
                  : undefined
              }
              onChange={(event) => {
                if (event.target.files) {
                  setFiles([...event.target.files]);
                }
              }}
            />
          </>
        )}
        <Button
          type="submit"
          disabled={isLoading || !input}
          variant="outline"
          size="xs"
          className="text-(--slate-11)"
        >
          <SendHorizontalIcon className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
};

const configDescriptions: Record<
  keyof ChatConfig,
  { min: number; max: number; description: string; step?: number }
> = {
  max_tokens: {
    min: 1,
    max: 4096,
    description: "Maximum number of tokens to generate",
  },
  temperature: {
    min: 0,
    max: 2,
    step: 0.1,
    description: "Controls randomness (0: deterministic, 2: very random)",
  },
  top_p: {
    min: 0,
    max: 1,
    step: 0.1,
    description: "Nucleus sampling: probability mass to consider",
  },
  top_k: {
    min: 1,
    max: 100,
    description:
      "Top-k sampling: number of highest probability tokens to consider",
  },
  frequency_penalty: {
    min: -2,
    max: 2,
    description: "Penalizes frequent tokens (-2: favor, 2: avoid)",
  },
  presence_penalty: {
    min: -2,
    max: 2,
    description: "Penalizes new tokens (-2: favor, 2: avoid)",
  },
};

const ConfigPopup: React.FC<{
  config: ChatConfig;
  onChange: (newConfig: ChatConfig) => void;
}> = ({ config, onChange }) => {
  const [open, setOpen] = useState(false);

  const handleChange = (key: keyof ChatConfig, value: number | null) => {
    // NaN represents an empty field, treat as null
    const normalizedValue =
      value === null || Number.isNaN(value) ? null : value;
    let finalValue: number | null = normalizedValue;

    if (finalValue !== null) {
      const { min, max } = configDescriptions[key];
      const clampedValue = Math.max(min, Math.min(max, finalValue));
      finalValue = clampedValue;
    }

    const newConfig = { ...config, [key]: finalValue };
    onChange(newConfig);
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Enter") {
      event.preventDefault();
      setOpen(false);
    }
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <Tooltip content="Configuration">
        <PopoverTrigger asChild={true}>
          <Button
            variant="outline"
            size="sm"
            className="border-none shadow-none hover:bg-transparent"
          >
            <SettingsIcon className="h-3 w-3" />
          </Button>
        </PopoverTrigger>
      </Tooltip>
      <PopoverContent className="w-70 border">
        <div className="grid gap-3">
          <h4 className="font-bold leading-none">Configuration</h4>
          {Objects.entries(config).map(([key, value]) => (
            <div key={key} className="grid grid-cols-3 items-center gap-1">
              <Label
                htmlFor={key}
                className="flex w-full justify-between col-span-3 align-end"
              >
                {startCase(key)}
                <Tooltip
                  delayDuration={200}
                  side="top"
                  content={
                    <div className="text-xs flex flex-col">
                      {configDescriptions[key].description}
                    </div>
                  }
                >
                  <HelpCircleIcon
                    className={
                      "h-3 w-3 cursor-help text-muted-foreground hover:text-foreground"
                    }
                  />
                </Tooltip>
              </Label>
              <NumberField
                id={key}
                aria-label={key}
                value={value ?? Number.NaN}
                placeholder={"null"}
                minValue={configDescriptions[key].min}
                maxValue={configDescriptions[key].max}
                step={configDescriptions[key].step ?? 1}
                onChange={(num) => handleChange(key, num)}
                onKeyDown={handleKeyDown}
                className="col-span-3"
              />
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
};

const PromptsPopover: React.FC<{
  prompts: string[];
  onSelect: (prompt: string) => void;
}> = ({ prompts, onSelect }) => {
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState("");

  const handleSelection = (prompt: string) => {
    const variableRegex = /{{(\w+)}}/g;
    const matches = [...prompt.matchAll(variableRegex)];

    if (matches.length > 0) {
      setSelectedPrompt(prompt);
      setIsPopoverOpen(true);
    } else {
      onSelect(prompt);
    }
  };

  return (
    <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
      <PopoverAnchor>
        <DropdownMenu>
          <Tooltip content="Select a prompt">
            <DropdownMenuTrigger asChild={true}>
              <Button
                variant="outline"
                size="sm"
                className="border-none shadow-none hover:bg-transparent"
              >
                <ChatBubbleIcon className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
          </Tooltip>
          <DropdownMenuContent
            side="right"
            align="end"
            // To prevent focus back on button
            onCloseAutoFocus={(e) => e.preventDefault()}
            className="w-64 max-h-96 overflow-y-auto"
          >
            {prompts.map((prompt, index) => (
              <DropdownMenuItem
                key={index}
                onSelect={() => handleSelection(prompt)}
                className="whitespace-normal text-left"
              >
                {prompt}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </PopoverAnchor>

      <PopoverContent side="right" align="end" className="min-w-80 px-2">
        <PromptVariablesForm
          prompt={selectedPrompt}
          onClose={() => setIsPopoverOpen(false)}
          onSelect={onSelect}
        />
      </PopoverContent>
    </Popover>
  );
};

const PromptVariablesForm: React.FC<{
  prompt: string;
  onClose: () => void;
  onSelect: (prompt: string) => void;
}> = ({ prompt, onClose, onSelect }) => {
  const [variables, setVariables] = useState<{ [key: string]: string }>({});

  useEffect(() => {
    const variableRegex = /{{(\w+)}}/g;
    const matches = [...prompt.matchAll(variableRegex)];
    const initialVariables = matches.reduce<{ [key: string]: string }>(
      (acc, match) => {
        acc[match[1]] = "";
        return acc;
      },
      {},
    );
    setVariables(initialVariables);
  }, [prompt]);

  const handleVariableChange = (variable: string, value: string) => {
    setVariables((prev) => ({ ...prev, [variable]: value }));
  };

  const replacedPrompt = prompt.replaceAll(
    /{{(\w+)}}/g,
    (_, key) => variables[key] || `{{${key}}}`,
  );
  const isSubmitDisabled = Object.values(variables).some(
    (value) => value == null || value.trim() === "",
  );

  const handleSubmit = () => {
    onSelect(replacedPrompt);
    onClose();
  };

  return (
    <div className="grid gap-4">
      {Object.entries(variables).map(([key, value], index) => (
        <div key={key} className="grid grid-cols-4 items-center gap-2">
          <Label htmlFor={key} className="font-semibold text-base">
            {key}
          </Label>
          <Input
            id={key}
            value={value}
            onChange={(e) => handleVariableChange(key, e.target.value)}
            rootClassName="col-span-3 w-full"
            className="m-0"
            placeholder={`Enter value for ${key}`}
            autoFocus={index === 0}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !isSubmitDisabled) {
                handleSubmit();
              }
            }}
          />
        </div>
      ))}
      <div className="grid gap-2 prose dark:prose-invert">
        <blockquote className="text-sm">{replacedPrompt}</blockquote>
      </div>
      <Button onClick={handleSubmit} size="xs" disabled={isSubmitDisabled}>
        Submit
      </Button>
    </div>
  );
};
