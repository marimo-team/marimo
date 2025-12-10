/* Copyright 2024 Marimo. All rights reserved. */

import { type UIMessage, useChat } from "@ai-sdk/react";
import { ChatBubbleIcon } from "@radix-ui/react-icons";
import { PopoverAnchor } from "@radix-ui/react-popover";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { DefaultChatTransport, type FileUIPart, type ToolUIPart } from "ai";
import { startCase } from "lodash-es";
import { ReasoningAccordion } from "@/components/chat/reasoning-accordion";
import { ToolCallAccordion } from "@/components/chat/tool-call-accordion";
import {
  BotMessageSquareIcon,
  ClipboardIcon,
  DownloadIcon,
  HelpCircleIcon,
  PaperclipIcon,
  RotateCwIcon,
  SendIcon,
  SettingsIcon,
  Trash2Icon,
  X,
} from "lucide-react";
import React, { lazy, useEffect, useRef, useState } from "react";
import { convertToFileUIPart } from "@/components/chat/chat-utils";
import {
  type AdditionalCompletions,
  PromptInput,
} from "@/components/editor/ai/add-cell-with-ai";
import { Spinner } from "@/components/icons/spinner";
import { Button, buttonVariants } from "@/components/ui/button";
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
import { toast } from "@/components/ui/use-toast";
import { moveToEndOfEditor } from "@/core/codemirror/utils";
import { MarimoIncomingMessageEvent } from "@/core/dom/events";
import { useAsyncData } from "@/hooks/useAsyncData";
import {
  type HTMLElementNotDerivedFromRef,
  useEventListener,
} from "@/hooks/useEventListener";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import { ErrorBanner } from "../common/error-banner";
import type { PluginFunctions } from "./ChatPlugin";
import type { ChatConfig, ChatMessage } from "./types";

const LazyStreamdown = lazy(() =>
  import("streamdown").then((module) => ({ default: module.Streamdown })),
);

function isToolPart(part: UIMessage["parts"][number]): part is ToolUIPart {
  return part.type.startsWith("tool-");
}

function isReasoningPart(
  part: UIMessage["parts"][number],
): part is { type: "reasoning"; text: string } {
  return part.type === "reasoning";
}

interface Props extends PluginFunctions {
  prompts: string[];
  config: ChatConfig;
  showConfigurationControls: boolean;
  maxHeight: number | undefined;
  allowAttachments: boolean | string[];
  value: ChatMessage[];
  setValue: (messages: ChatMessage[]) => void;
  host: HTMLElement;
}

export const Chatbot: React.FC<Props> = (props) => {
  const [input, setInput] = useState("");
  const [config, setConfig] = useState<ChatConfig>(props.config);
  const [files, setFiles] = useState<File[] | undefined>(undefined);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const codeMirrorInputRef = useRef<ReactCodeMirrorRef>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Track streaming state - maps backend message_id to frontend message index
  const streamingStateRef = useRef<{
    backendMessageId: string | null;
    frontendMessageIndex: number | null;
  }>({ backendMessageId: null, frontendMessageIndex: null });

  const { data: initialMessages } = useAsyncData(async () => {
    const chatMessages = await props.get_chat_history({});
    const messages: UIMessage[] = chatMessages.messages.map((message, idx) => ({
      id: idx.toString(),
      role: message.role,
      parts: message.parts ?? [],
    }));
    return messages;
  }, []);

  const {
    messages,
    sendMessage,
    setMessages,
    status,
    stop,
    error,
    regenerate,
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
        try {
          const messages = body.messages.map((m) => ({
            role: m.role,
            content: m.parts
              ?.map((p) => ("text" in p ? p.text : ""))
              .join("\n"),
            parts: m.parts,
          }));

          // Create a placeholder message for streaming
          const messageId = Date.now().toString();

          setMessages((prev) => [
            ...prev,
            {
              id: messageId,
              role: "assistant",
              parts: [{ type: "text", text: "" }],
            },
          ]);

          const response = await props.send_prompt({
            messages: messages,
            config: {
              max_tokens: config.max_tokens,
              temperature: config.temperature,
              top_p: config.top_p,
              top_k: config.top_k,
              frequency_penalty: config.frequency_penalty,
              presence_penalty: config.presence_penalty,
            },
          });

          // If streaming didn't happen (non-generator response), update the message
          // We track whether any chunks were received to avoid overwriting streamed parts
          // Note: streaming state is cleared when is_final chunk arrives, so we need
          // to check the message content, not just streaming state
          setMessages((prev) => {
            const updated = [...prev];
            const index = updated.findIndex((m) => m.id === messageId);
            if (index !== -1) {
              const currentMessage = updated[index];
              // Only overwrite if the message still has the initial empty placeholder
              // (meaning no streaming chunks were received)
              const firstPart = currentMessage.parts[0];
              const hasOnlyEmptyText =
                currentMessage.parts.length === 1 &&
                firstPart.type === "text" &&
                "text" in firstPart &&
                firstPart.text === "";

              if (hasOnlyEmptyText) {
                updated[index] = {
                  ...currentMessage,
                  parts: [{ type: "text", text: response }],
                };
              }
              // If streaming happened, parts were already updated by chunks - don't overwrite
            }
            return updated;
          });

          return new Response(response);
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } catch (error: any) {
          // Clear streaming state on error
          streamingStateRef.current = {
            backendMessageId: null,
            frontendMessageIndex: null,
          };

          // HACK: strip the error message to clean up the response
          const strippedError = error.message
            .split("failed with exception ")
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
      const message = e.detail.message;
      if (
        typeof message === "object" &&
        message !== null &&
        "type" in message &&
        message.type === "stream_chunk"
      ) {
        const chunkMessage = message as {
          type: string;
          message_id: string;
          content: string;
          parts?: UIMessage["parts"];
          is_final: boolean;
        };

        // Initialize streaming state on first chunk if not already set
        if (streamingStateRef.current.backendMessageId === null) {
          // Find the last assistant message (which should be the placeholder we created)
          setMessages((prev) => {
            const updated = [...prev];
            // Find the last assistant message
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].role === "assistant") {
                streamingStateRef.current = {
                  backendMessageId: chunkMessage.message_id,
                  frontendMessageIndex: i,
                };
                break;
              }
            }
            return updated;
          });
        }

        // Only process chunks for the current streaming message
        const frontendIndex = streamingStateRef.current.frontendMessageIndex;
        if (
          streamingStateRef.current.backendMessageId ===
            chunkMessage.message_id &&
          frontendIndex !== null
        ) {
          setMessages((prev) => {
            const updated = [...prev];
            const index = frontendIndex;

            // Update the message at the tracked index
            if (index < updated.length) {
              const messageToUpdate = updated[index];
              if (messageToUpdate.role === "assistant") {
                // Use parts if provided, otherwise fall back to text content
                const newParts: UIMessage["parts"] = chunkMessage.parts ?? [
                  { type: "text", text: chunkMessage.content },
                ];
                updated[index] = {
                  ...messageToUpdate,
                  parts: newParts,
                };
              }
            }

            return updated;
          });

          // Clear streaming state when final chunk arrives
          if (chunkMessage.is_final) {
            streamingStateRef.current = {
              backendMessageId: null,
              frontendMessageIndex: null,
            };
          }
        }
      }
    },
  );

  const isLoading = status === "submitted" || status === "streaming";

  const handleDelete = (id: string) => {
    const index = messages.findIndex((message) => message.id === id);
    if (index !== -1) {
      props.delete_chat_message({ index });
      setMessages((prev) => prev.filter((message) => message.id !== id));
    }
  };

  const renderAttachment = (attachment: FileUIPart) => {
    if (attachment.mediaType?.startsWith("image")) {
      return (
        <img
          src={attachment.url}
          alt={attachment.filename || "Attachment"}
          className="object-contain rounded-sm"
          width={100}
          height={100}
        />
      );
    }

    return (
      <a
        href={attachment.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-background hover:underline"
      >
        {attachment.filename || "Attachment"}
      </a>
    );
  };

  const renderMessage = (message: UIMessage) => {
    const parts = message.parts ?? [];

    // For user messages, just show text content
    if (message.role === "user") {
      const textContent = parts
        .filter((p) => p.type === "text")
        .map((p) => p.text)
        .join("\n");
      const attachments = parts.filter((p) => p.type === "file");

      return (
        <>
          {textContent}
          {attachments.length > 0 && (
            <div className="mt-2">
              {attachments.map((attachment, index) => (
                <div key={index} className="flex items-baseline gap-2">
                  {renderAttachment(attachment)}
                  <a
                    className={buttonVariants({
                      variant: "text",
                      size: "icon",
                    })}
                    href={attachment.url}
                    download={attachment.filename}
                  >
                    <DownloadIcon className="size-3" />
                  </a>
                </div>
              ))}
            </div>
          )}
        </>
      );
    }

    // For assistant messages, render each part in order
    return (
      <>
        {parts.map((part, index) => {
          if (isToolPart(part)) {
            return (
              <ToolCallAccordion
                key={index}
                index={index}
                toolName={part.type}
                result={part.output}
                className="my-2"
                state={part.state}
                input={part.input}
              />
            );
          }

          if (part.type === "text") {
            return (
              <LazyStreamdown key={index} className="mo-markdown-renderer">
                {part.text}
              </LazyStreamdown>
            );
          }

          if (part.type === "file") {
            return (
              <div key={index} className="flex items-baseline gap-2 mt-2">
                {renderAttachment(part)}
                <a
                  className={buttonVariants({
                    variant: "text",
                    size: "icon",
                  })}
                  href={part.url}
                  download={part.filename}
                >
                  <DownloadIcon className="size-3" />
                </a>
              </div>
            );
          }

          // Fallback for unknown part types - log and skip
          Logger.warn("Unknown part type:", part);
          return null;
        })}
      </>
    );
  };

  // Render only content parts (text, files - not tools or reasoning)
  const renderNonToolParts = (parts: UIMessage["parts"]) => {
    return (
      <>
        {parts.map((part, index) => {
          if (part.type === "text") {
            return (
              <LazyStreamdown key={index} className="mo-markdown-renderer">
                {part.text}
              </LazyStreamdown>
            );
          }

          if (part.type === "file") {
            return (
              <div key={index} className="flex items-baseline gap-2 mt-2">
                {renderAttachment(part)}
                <a
                  className={buttonVariants({
                    variant: "text",
                    size: "icon",
                  })}
                  href={part.url}
                  download={part.filename}
                >
                  <DownloadIcon className="size-3" />
                </a>
              </div>
            );
          }

          // Skip tool parts (handled separately) and unknown types
          return null;
        })}
      </>
    );
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
          onClick={() => {
            setMessages([]);
            props.setValue([]);
            props.delete_chat_history({});
          }}
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
        {messages.map((message) => {
          const textContent = message.parts
            ?.filter((p) => p.type === "text")
            .map((p) => p.text)
            .join("\n");

          // Separate tool parts, reasoning parts, and other parts for assistant messages
          const toolParts =
            message.role === "assistant"
              ? message.parts?.filter((p) => isToolPart(p))
              : [];
          const reasoningParts =
            message.role === "assistant"
              ? message.parts?.filter((p) => isReasoningPart(p))
              : [];
          const contentParts =
            message.role === "assistant"
              ? message.parts?.filter(
                  (p) => !isToolPart(p) && !isReasoningPart(p),
                )
              : message.parts;
          const hasContentParts =
            contentParts &&
            contentParts.length > 0 &&
            contentParts.some(
              (p) => p.type !== "text" || ("text" in p && p.text.trim() !== ""),
            );

          return (
            <div
              key={message.id}
              className={cn(
                "flex flex-col group gap-2",
                message.role === "user" ? "items-end" : "items-start",
              )}
            >
              {/* Reasoning rendered outside the message bubble */}
              {reasoningParts && reasoningParts.length > 0 && (
                <div className="w-full max-w-[90%] space-y-2">
                  {reasoningParts.map((part, index) =>
                    isReasoningPart(part) ? (
                      <ReasoningAccordion
                        key={`reasoning-${index}`}
                        reasoning={part.text}
                        index={index}
                      />
                    ) : null,
                  )}
                </div>
              )}
              {/* Tool calls rendered outside the message bubble */}
              {toolParts && toolParts.length > 0 && (
                <div className="w-full max-w-[90%] space-y-2">
                  {toolParts.map((part, index) =>
                    isToolPart(part) ? (
                      <ToolCallAccordion
                        key={`tool-${index}`}
                        index={index}
                        toolName={part.type}
                        result={part.output}
                        state={part.state}
                        input={part.input}
                      />
                    ) : null,
                  )}
                </div>
              )}
              {/* Message bubble for content (text, files, etc.) */}
              {(message.role === "user" || hasContentParts) && (
                <div
                  className={`max-w-[80%] p-3 rounded-lg ${
                    message.role === "user"
                      ? "bg-(--sky-11) text-(--slate-1) whitespace-pre-wrap"
                      : "bg-(--slate-4) text-(--slate-12)"
                  }`}
                >
                  {message.role === "user"
                    ? renderMessage(message)
                    : renderNonToolParts(contentParts ?? [])}
                </div>
              )}
              <div className="flex justify-end text-xs gap-2 invisible group-hover:visible">
                <button
                  type="button"
                  onClick={async () => {
                    await copyToClipboard(textContent);
                    toast({
                      title: "Copied to clipboard",
                    });
                  }}
                  className="text-xs text-(--slate-9) hover:text-(--slate-11)"
                >
                  <ClipboardIcon className="h-3 w-3" />
                </button>
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
        className="flex w-full border-t border-(--slate-6) px-2 py-1 items-center"
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
          size="sm"
          className="text-(--slate-11)"
        >
          <SendIcon className="h-5 w-5" />
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
  const [localConfig, setLocalConfig] = useState<ChatConfig>(config);
  const [open, setOpen] = useState(false);

  const handleChange = (key: keyof ChatConfig, value: number) => {
    const { min, max } = configDescriptions[key];
    const clampedValue = Math.max(min, Math.min(max, value));
    const newConfig = { ...localConfig, [key]: clampedValue };
    setLocalConfig(newConfig);
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
            className="border-none shadow-initial"
          >
            <SettingsIcon className="h-3 w-3" />
          </Button>
        </PopoverTrigger>
      </Tooltip>
      <PopoverContent className="w-70 border">
        <div className="grid gap-3">
          <h4 className="font-bold leading-none">Configuration</h4>
          {Objects.entries(localConfig).map(([key, value]) => (
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
                value={value}
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
                className="border-none shadow-initial"
              >
                <ChatBubbleIcon className="h-3 w-3 mx-1" />
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
