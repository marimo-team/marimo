/* Copyright 2024 Marimo. All rights reserved. */
import { Spinner } from "@/components/icons/spinner";
import { Logger } from "@/utils/Logger";
import { useChat } from "ai/react";
import React from "react";
import type { ChatClientMessage } from "./types";
import { ErrorBanner } from "../common/error-banner";
import { Button } from "@/components/ui/button";
import { ClipboardIcon, SendIcon, Trash2Icon } from "lucide-react";
import { cn } from "@/utils/cn";
import { toast } from "@/components/ui/use-toast";
import { ChatBubbleIcon } from "@radix-ui/react-icons";

interface Props {
  onMessage: (message: string) => void;
  onError: (message: string) => void;
  keepLastMessageOnError?: boolean;
  sendPrompt(req: {
    messages: ChatClientMessage[];
    config: {
      max_tokens?: number;
      temperature?: number;
      top_p?: number;
      top_k?: number;
      frequency_penalty?: number;
      presence_penalty?: number;
    };
  }): Promise<string>;
}

export const Chatbot: React.FC<Props> = (props) => {
  const inputRef = React.useRef<HTMLInputElement>(null);

  const {
    messages,
    setMessages,
    input,
    handleInputChange,
    handleSubmit,
    isLoading,
    stop,
    error,
    reload,
  } = useChat({
    keepLastMessageOnError: true,
    streamProtocol: "text",
    fetch: async (url, request) => {
      const body = JSON.parse(request?.body as string) as {
        messages: ChatClientMessage[];
      };
      try {
        const response = await props.sendPrompt({
          ...body,
          config: {
            max_tokens: 100,
            temperature: 0.5,
            top_p: 1,
            top_k: 40,
            frequency_penalty: 0,
            presence_penalty: 0,
          },
        });
        return new Response(response);
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } catch (error: any) {
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

  return (
    <div className="flex flex-col h-full bg-[var(--slate-1)] rounded-lg shadow border border-[var(--slate-6)]">
      <div className="flex-grow overflow-y-auto gap-4 p-4 flex flex-col">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground text-center p-4">
            <ChatBubbleIcon className="h-12 w-12 mb-4" />
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
              <p>{message.content}</p>
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
        <div className="mb-4">
          <ErrorBanner error={error} />
          <Button
            variant="outline"
            size="sm"
            onClick={() => reload()}
            className="mt-2"
          >
            Retry
          </Button>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className="flex gap-2 w-full border-t border-[var(--slate-6)] px-2 py-1"
      >
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
