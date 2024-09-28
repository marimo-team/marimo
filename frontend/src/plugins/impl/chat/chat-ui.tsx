/* Copyright 2024 Marimo. All rights reserved. */
import { Spinner } from "@/components/icons/spinner";
import { Logger } from "@/utils/Logger";
import { type Message, useChat } from "ai/react";
import React from "react";
import type { ChatMessage, ChatConfig, SendMessageRequest } from "./types";
import { ErrorBanner } from "../common/error-banner";
import { Button } from "@/components/ui/button";
import {
  BotMessageSquareIcon,
  ClipboardIcon,
  HelpCircleIcon,
  SendIcon,
  Trash2Icon,
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

interface Props {
  prompts: string[];
  config: ChatConfig;
  showConfigurationControls: boolean;
  sendPrompt(req: SendMessageRequest): Promise<string>;
  value: ChatMessage[];
  setValue: (messages: ChatMessage[]) => void;
}

export const Chatbot: React.FC<Props> = (props) => {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [config, setConfig] = useState<ChatConfig>(props.config);

  const {
    messages,
    setMessages,
    input,
    setInput,
    handleInputChange,
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
        messages: ChatMessage[];
      };
      try {
        const response = await props.sendPrompt({
          ...body,
          config: {
            max_tokens: config.maxTokens,
            temperature: config.temperature,
            top_p: config.topP,
            top_k: config.topK,
            frequency_penalty: config.frequencyPenalty,
            presence_penalty: config.presencePenalty,
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
    onFinish: (message, { usage, finishReason }) => {
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

  const renderMessage = (message: Message) => {
    return message.role === "assistant"
      ? renderHTML({ html: message.content })
      : message.content;
  };

  return (
    <div className="flex flex-col h-full bg-[var(--slate-1)] rounded-lg shadow border border-[var(--slate-6)]">
      <div className="flex justify-end p-1">
        <Button variant="text" size="icon" onClick={() => setMessages([])}>
          <Trash2Icon className="h-3 w-3" />
        </Button>
      </div>
      <div className="flex-grow overflow-y-auto gap-4 py-4 px-2 flex flex-col">
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
              <p>{renderMessage(message)}</p>
            </div>
            <div className="flex justify-end text-xs gap-2 invisible group-hover:visible">
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(message.content);
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
      </div>

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

      <form
        onSubmit={handleSubmit}
        className="flex w-full border-t border-[var(--slate-6)] px-2 py-1"
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
                inputRef.current?.focus();
                inputRef.current?.setSelectionRange(
                  prompt.length,
                  prompt.length,
                );
              });
            }}
          />
        )}
        <input
          name="prompt"
          ref={inputRef}
          value={input}
          onChange={handleInputChange}
          className="flex w-full outline-none bg-transparent ml-2 text-[var(--slate-12)]"
          placeholder="Type your message..."
        />
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
  maxTokens: {
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
  topP: {
    min: 0,
    max: 1,
    step: 0.1,
    description: "Nucleus sampling: probability mass to consider",
  },
  topK: {
    min: 1,
    max: 100,
    description:
      "Top-k sampling: number of highest probability tokens to consider",
  },
  frequencyPenalty: {
    min: -2,
    max: 2,
    description: "Penalizes frequent tokens (-2: favor, 2: avoid)",
  },
  presencePenalty: {
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
  return (
    <DropdownMenu>
      <Tooltip content="Select a prompt">
        <DropdownMenuTrigger asChild={true}>
          <Button
            variant="outline"
            size="sm"
            className="border-none shadow-initial"
          >
            <ChatBubbleIcon className="h-3 w-3" />
          </Button>
        </DropdownMenuTrigger>
      </Tooltip>
      <DropdownMenuContent
        // To prevent focus back on button
        onCloseAutoFocus={(e) => e.preventDefault()}
        className="w-64 max-h-96 overflow-y-auto"
      >
        {prompts.map((prompt, index) => (
          <DropdownMenuItem
            key={index}
            onSelect={() => onSelect(prompt)}
            className="whitespace-normal text-left"
          >
            {prompt}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};
