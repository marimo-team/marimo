/* Copyright 2024 Marimo. All rights reserved. */
import { useAtom } from "jotai";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ClockIcon, Loader2, PlusIcon } from "lucide-react";
import { chatStateAtom, activeChatAtom, type Chat } from "@/core/ai/state";
import { useState, useRef, useEffect } from "react";
import { generateUUID } from "@/utils/uuid";
import { useChat } from "ai/react";
import { PromptInput } from "../editor/ai/add-cell-with-ai";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import { Tooltip } from "../ui/tooltip";
import { asURL } from "@/utils/url";
import { API } from "@/core/network/api";
import { cn } from "@/utils/cn";
import { MarkdownRenderer } from "./markdown-renderer";
import { Logger } from "@/utils/Logger";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { getAICompletionBody } from "../editor/ai/completion-utils";
import { addMessageToChat } from "@/core/ai/chat-utils";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { useTheme } from "@/theme/useTheme";
import { ServerSelector } from "./server-selector";
import { Completion } from "@codemirror/autocomplete";

interface MCPResponse {
  value: string;
}

function isMCPResponse(obj: unknown): obj is MCPResponse {
  return typeof obj === 'object' && obj !== null && 'value' in obj && typeof (obj as MCPResponse).value === 'string';
}

export const ChatPanel = () => {
  const [chatState, setChatState] = useAtom(chatStateAtom);
  const [activeChat, setActiveChat] = useAtom(activeChatAtom);
  const [completionBody, setCompletionBody] = useState<object>({});
  const [newThreadInput, setNewThreadInput] = useState("");
  const [selectedServer, setSelectedServer] = useState<string | null>(null);
  const [completions, setCompletions] = useState<Completion[]>([]);
  const newThreadInputRef = useRef<ReactCodeMirrorRef>(null);
  const newMessageInputRef = useRef<ReactCodeMirrorRef>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  // Fetch completions when server changes
  useEffect(() => {
    const fetchCompletions = async () => {
      if (!selectedServer) {
        setCompletions([]);
        return;
      }

      try {
        const response = await fetch('/api/mcp/servers');
        if (!response.ok) {
          return;
        }

        const { servers }: { servers: Array<{ name: string; tools: Array<{ name: string; description: string }>; resources: Array<{ name: string; description: string }>; prompts: Array<{ name: string; description: string }> }> } = await response.json();
        const server = servers.find((s) => s.name === selectedServer);
        if (!server) {
          return;
        }

        const allCompletions = [
          ...server.tools.map((t) => ({ label: `!${t.name}()`, detail: t.description })),
          ...server.resources.map((r) => ({ label: `@${r.name}()`, detail: r.description })),
          ...server.prompts.map((p) => ({ label: `/${p.name}()`, detail: p.description })),
        ];

        setCompletions(allCompletions);
      } catch (error) {
        Logger.error('Error fetching completions:', error);
      }
    };

    fetchCompletions();
  }, [selectedServer]);

  // Process MCP function calls in the message
  const processMCPFunctions = async (message: string): Promise<string> => {
    if (!selectedServer) {
      return message;
    }

    const functionCalls = message.match(/[!/@]\w+\([^)]*\)/g) || [];
    let processedMessage = message;

    for (const call of functionCalls) {
      try {
        const response = await fetch(`/api/mcp/execute`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            server: selectedServer,
            call: call,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to execute MCP function: ${call}`);
        }

        const result = await response.json();
        if (!isMCPResponse(result)) {
          throw new Error('Invalid response format');
        }
        processedMessage = processedMessage.replace(call, result.value);
      } catch (error) {
        Logger.error("Error executing MCP function:", error);
      }
    }

    return processedMessage;
  };

  const {
    messages,
    input,
    setInput: setInputInternal,
    setMessages,
    append,
    error,
    isLoading,
    reload,
  } = useChat({
    keepLastMessageOnError: true,
    api: asURL("api/ai/chat").toString(),
    headers: API.headers(),
    body: {
      ...completionBody,
      includeOtherCode: getCodes(""),
    },
    streamProtocol: "text",
    onFinish: (message) => {
      if (!chatState.activeChatId) {
        Logger.warn("No active chat");
        return;
      }
      setChatState((prev) =>
        addMessageToChat(prev, prev.activeChatId, "assistant", message.content),
      );
    },
    onError: (error) => {
      Logger.error("An error occurred:", error);
    },
    onResponse: (response) => {
      Logger.debug("Received HTTP response from server:", response);
    },
  });

  const setInput = (newValue: string) => {
    setInputInternal(newValue);
    const messagesConcat = messages.map((m) => m.content).join("\n");
    setCompletionBody(getAICompletionBody(`${messagesConcat}\n\n${newValue}`));
  };

  const lastMessageText = messages.at(-1)?.content;
  useEffect(() => {
    if (isLoading) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading, lastMessageText]);

  const createNewThread = async (initialMessage: string) => {
    const processedMessage = await processMCPFunctions(initialMessage);
    const newChat: Chat = {
      id: generateUUID(),
      title: `${processedMessage.slice(0, 30)}...`,
      messages: [
        {
          role: "user",
          content: processedMessage,
          timestamp: Date.now(),
        },
      ],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };

    setChatState((prev) => ({
      chats: [...prev.chats, newChat],
      activeChatId: newChat.id,
    }));

    const nextCompletionBody = getAICompletionBody(processedMessage);
    setCompletionBody(nextCompletionBody);

    setMessages([]);
    setInput("");
    append(
      {
        role: "user",
        content: processedMessage,
      },
      {
        body: {
          ...nextCompletionBody,
          includeOtherCode: getCodes(""),
        },
      },
    );
  };

  // Modified handleSubmit to process MCP functions
  const handleSubmitWithMCP = async (e: KeyboardEvent | undefined, value: string) => {
    if (!value.trim()) {
      return;
    }

    const processedInput = await processMCPFunctions(value);
    append({
      role: "user",
      content: processedInput,
    });

    if (chatState.activeChatId) {
      setChatState((prev) =>
        addMessageToChat(prev, chatState.activeChatId, "user", processedInput),
      );
    }
  };

  return (
    <div className="flex flex-col h-[calc(100%-53px)]">
      <div className="flex border-b px-2 py-1 justify-between flex-shrink-0">
        <Tooltip content="New chat">
          <Button
            variant="text"
            size="icon"
            onClick={() => {
              setActiveChat(null);
              setMessages([]);
              setInput("");
              setNewThreadInput("");
            }}
          >
            <PlusIcon className="h-4 w-4" />
          </Button>
        </Tooltip>
        <Popover>
          <Tooltip content="Previous chats">
            <PopoverTrigger asChild={true}>
              <Button variant="text" size="icon">
                <ClockIcon className="h-4 w-4" />
              </Button>
            </PopoverTrigger>
          </Tooltip>
          <PopoverContent className="w-[520px] p-0" align="start" side="right">
            <ScrollArea className="h-[500px] p-4">
              <div className="space-y-4">
                {chatState.chats.map((chat) => (
                  <div
                    key={chat.id}
                    className={cn(
                      "p-3 rounded-md cursor-pointer hover:bg-accent",
                      chat.id === activeChat?.id && "bg-accent",
                    )}
                    onClick={() => {
                      setActiveChat(chat.id);
                      setMessages(
                        chat.messages.map(({ role, content, timestamp }) => ({
                          role,
                          content,
                          id: timestamp.toString(),
                        })),
                      );
                    }}
                  >
                    <div className="font-medium">{chat.title}</div>
                    <div className="text-sm text-muted-foreground">
                      {new Date(chat.updatedAt).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </PopoverContent>
        </Popover>
      </div>

      <ServerSelector onServerSelect={setSelectedServer} />

      <div className="flex-1 px-3 bg-[var(--slate-1)] gap-4 py-3 flex flex-col overflow-y-auto">
        {(!messages || messages.length === 0) && (
          <div className="flex rounded-md border px-1 bg-background">
            <PromptInput
              key="new-thread-input"
              value={newThreadInput}
              placeholder="Ask anything, @ for resources, ! for tools, / for prompts"
              theme={theme}
              onClose={() => newThreadInputRef.current?.editor?.blur()}
              onChange={setNewThreadInput}
              onSubmit={() =>
                newThreadInput.trim() && createNewThread(newThreadInput.trim())
              }
              additionalCompletions={{
                triggerCompletionRegex: /[!/@]\w+/,
                completions,
              }}
            />
          </div>
        )}

        {messages.map((message, idx) => (
          <div
            key={idx}
            className={cn(
              "flex",
              message.role === "user" ? "justify-end" : "justify-start",
            )}
          >
            {message.role === "user" ? (
              <div className="w-[95%] bg-background border p-1 rounded-sm">
                <PromptInput
                  key={message.id}
                  value={message.content}
                  theme={theme}
                  placeholder="Type your message..."
                  onChange={() => {
                    // noop
                  }}
                  onSubmit={(e, newValue) => {
                    if (!newValue.trim()) {
                      return;
                    }
                    // Remove all messages from here to the end
                    setMessages((messages) => messages.slice(0, idx));
                    setCompletionBody(getAICompletionBody(newValue));
                    append({
                      role: "user",
                      content: newValue,
                    });
                    if (chatState.activeChatId) {
                      setChatState((prev) =>
                        addMessageToChat(
                          prev,
                          chatState.activeChatId,
                          "user",
                          newValue,
                        ),
                      );
                    }
                  }}
                  onClose={() => {
                    // noop
                  }}
                  additionalCompletions={{
                    triggerCompletionRegex: /[!/@]\w+/,
                    completions,
                  }}
                />
              </div>
            ) : (
              <div className="w-[95%]">
                <MarkdownRenderer content={message.content} />
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-center py-4">
            <Loader2 className="h-4 w-4 animate-spin" />
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

        <div ref={messagesEndRef} />
      </div>

      {messages && messages.length > 0 && (
        <div className="px-2 py-3 border-t relative flex-shrink-0 min-h-[80px]">
          {isLoading && (
            <div className="flex justify-center mb-2 absolute -top-10 left-0 right-0">
              <Button
                variant="secondary"
                size="xs"
                onClick={() => stop()}
                className="text-muted-foreground hover:text-foreground"
              >
                Cancel
              </Button>
            </div>
          )}

          <PromptInput
            value={input}
            onChange={setInput}
            onSubmit={handleSubmitWithMCP}
            onClose={() => newMessageInputRef.current?.editor?.blur()}
            theme={theme}
            placeholder="Type your message..."
            additionalCompletions={{
              triggerCompletionRegex: /[!/@]\w+/,
              completions,
            }}
          />
        </div>
      )}
    </div>
  );
};
