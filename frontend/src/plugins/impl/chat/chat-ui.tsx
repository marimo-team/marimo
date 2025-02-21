/* Copyright 2024 Marimo. All rights reserved. */
import { Spinner } from "@/components/icons/spinner";
import { Logger } from "@/utils/Logger";
import { type Message, useChat } from "ai/react";
import React, { useEffect, useRef } from "react";
import type {
  ChatMessage,
  ChatConfig,
  ChatAttachment,
  ChatRole,
} from "./types";
import { ErrorBanner } from "../common/error-banner";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  BotMessageSquareIcon,
  ClipboardIcon,
  HelpCircleIcon,
  SendIcon,
  Trash2Icon,
  DownloadIcon,
  PaperclipIcon,
  X,
} from "lucide-react";
import { cn } from "@/utils/cn";
import { toast } from "@/components/ui/use-toast";
import { useState } from "react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Label } from "@/components/ui/label";
import { SettingsIcon } from "lucide-react";
import { NumberField } from "@/components/ui/number-field";
import { Objects } from "@/utils/objects";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { startCase } from "lodash-es";
import { ChatBubbleIcon } from "@radix-ui/react-icons";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { Input } from "@/components/ui/input";
import { PopoverAnchor } from "@radix-ui/react-popover";
import { copyToClipboard } from "@/utils/copy";
import {
  type AdditionalCompletions,
  PromptInput,
} from "@/components/editor/ai/add-cell-with-ai";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { useTheme } from "@/theme/useTheme";
import { moveToEndOfEditor } from "@/core/codemirror/utils";
import type { PluginFunctions } from "./ChatPlugin";
import { useAsyncData } from "@/hooks/useAsyncData";

interface Props extends PluginFunctions {
  prompts: string[];
  config: ChatConfig;
  showConfigurationControls: boolean;
  maxHeight: number | undefined;
  allowAttachments: boolean | string[];
  value: ChatMessage[];
  setValue: (messages: ChatMessage[]) => void;
}

export const Chatbot: React.FC<Props> = (props) => {
  const [config, setConfig] = useState<ChatConfig>(props.config);
  const [files, setFiles] = useState<FileList | undefined>(undefined);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const formRef = useRef<HTMLFormElement>(null);
  const codeMirrorInputRef = useRef<ReactCodeMirrorRef>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  const { data: initialMessages } = useAsyncData(async () => {
    const chatMessages = await props.get_chat_history({});
    const messages: Message[] = chatMessages.messages.map((message, idx) => ({
      id: idx.toString(),
      role: message.role,
      content: message.content,
      experimental_attachments: message.attachments,
    }));
    return messages;
  }, []);

  const {
    messages,
    setMessages,
    input,
    setInput,
    handleSubmit,
    isLoading,
    stop,
    error,
    reload,
  } = useChat({
    keepLastMessageOnError: true,
    streamProtocol: "text",
    fetch: async (_url, request) => {
      const body = JSON.parse(request?.body as string) as {
        messages: Message[];
      };
      try {
        const response = await props.send_prompt({
          messages: body.messages.map((m) => ({
            role: m.role as ChatRole,
            content: m.content,
            attachments: m.experimental_attachments,
          })),
          config: {
            max_tokens: config.max_tokens,
            temperature: config.temperature,
            top_p: config.top_p,
            top_k: config.top_k,
            frequency_penalty: config.frequency_penalty,
            presence_penalty: config.presence_penalty,
          },
        });
        return new Response(response);
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } catch (error: any) {
        // HACK: strip the error message to clean up the response
        const strippedError = error.message
          .split("failed with exception ")
          .pop();
        return new Response(strippedError, { status: 400 });
      }
    },
    initialMessages: initialMessages,
    onFinish: (message, { usage, finishReason }) => {
      setFiles(undefined);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
      Logger.debug("Finished streaming message:", message);
      Logger.debug("Token usage:", usage);
      Logger.debug("Finish reason:", finishReason);
    },
    onError: (error) => {
      Logger.error("An error occurred:", error);
    },
    onResponse: (response) => {
      Logger.debug("Received HTTP response from server:", response);
    },
  });

  const handleDelete = (id: string) => {
    setMessages(messages.filter((message) => message.id !== id));
  };

  const renderAttachment = (attachment: ChatAttachment) => {
    if (attachment.contentType?.startsWith("image")) {
      return (
        <img
          src={attachment.url}
          alt={attachment.name || "Attachment"}
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
        {attachment.name || "Attachment"}
      </a>
    );
  };

  const renderMessage = (message: Message) => {
    const content =
      message.role === "assistant"
        ? renderHTML({ html: message.content })
        : message.content;

    const attachments = message.experimental_attachments;

    return (
      <>
        {content}
        {attachments && attachments.length > 0 && (
          <div className="mt-2">
            {attachments.map((attachment, index) => (
              <div key={index} className="flex items-baseline gap-2 ">
                {renderAttachment(attachment)}
                <a
                  className={buttonVariants({
                    variant: "text",
                    size: "icon",
                  })}
                  href={attachment.url}
                  download={attachment.name}
                >
                  <DownloadIcon className="size-3" />
                </a>
              </div>
            ))}
          </div>
        )}
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

  return (
    <div
      className="flex flex-col h-full bg-[var(--slate-1)] rounded-lg shadow border border-[var(--slate-6)] overflow-hidden relative"
      style={{ maxHeight: props.maxHeight }}
    >
      <div className="absolute top-0 right-0 flex justify-end z-10 border border-[var(--slate-6)] bg-inherit rounded-bl-lg">
        <Button
          variant="text"
          size="icon"
          onClick={() => {
            setMessages([]);
            props.setValue([]);
          }}
        >
          <Trash2Icon className="h-3 w-3" />
        </Button>
      </div>
      <div
        className="flex-grow overflow-y-auto gap-4 pt-8 pb-4 px-2 flex flex-col"
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
        {messages.map((message) => (
          <div
            key={message.id}
            className={cn(
              "flex flex-col group gap-2",
              message.role === "user" ? "items-end" : "items-start",
            )}
          >
            <div
              className={`max-w-[80%] p-3 rounded-lg ${
                message.role === "user"
                  ? "bg-[var(--sky-11)] text-[var(--slate-1)]"
                  : "bg-[var(--slate-4)] text-[var(--slate-12)]"
              }`}
            >
              <p
                className={cn(message.role === "user" && "whitespace-pre-wrap")}
              >
                {renderMessage(message)}
              </p>
            </div>
            <div className="flex justify-end text-xs gap-2 invisible group-hover:visible">
              <button
                type="button"
                onClick={async () => {
                  await copyToClipboard(message.content);
                  toast({
                    title: "Copied to clipboard",
                  });
                }}
                className="text-xs text-[var(--slate-9)] hover:text-[var(--slate-11)]"
              >
                <ClipboardIcon className="h-3 w-3" />
              </button>
              <button
                type="button"
                onClick={() => handleDelete(message.id)}
                className="text-xs text-[var(--slate-9)] hover:text-[var(--slate-11)]"
              >
                <Trash2Icon className="h-3 w-3 text-[var(--red-9)]" />
              </button>
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center justify-center space-x-2 mb-4">
            <Spinner size="small" />
            <Button
              variant="link"
              size="sm"
              onClick={() => stop()}
              className="text-[var(--red-9)] hover:text-[var(--red-11)]"
            >
              Stop
            </Button>
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center space-x-2 mb-4">
            <ErrorBanner error={error} />
            <Button variant="outline" size="sm" onClick={() => reload()}>
              Retry
            </Button>
          </div>
        )}
      </div>

      <form
        onSubmit={(evt) => {
          handleSubmit(evt, {
            experimental_attachments: files,
          });
        }}
        ref={formRef}
        className="flex w-full border-t border-[var(--slate-6)] px-2 py-1 items-center"
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
                codeMirrorInputRef.current?.view?.focus();
                moveToEndOfEditor(codeMirrorInputRef.current?.view);
              });
            }}
          />
        )}
        <PromptInput
          className="rounded-sm mr-2"
          placeholder={promptInputPlaceholder}
          value={input}
          inputRef={codeMirrorInputRef}
          theme={theme}
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
            className="text-sm text-[var(--slate-11)] truncate flex-shrink-0 w-24"
          >
            {files[0].name}
          </span>
        )}
        {files && files.length > 1 && (
          <span
            title={[...files].map((f) => f.name).join("\n")}
            className="text-sm text-[var(--slate-11)] truncate flex-shrink-0"
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
                  setFiles(event.target.files);
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
          className="text-[var(--slate-11)]"
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
