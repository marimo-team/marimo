/* Copyright 2024 Marimo. All rights reserved. */

import { useChat } from "@ai-sdk/react";
import type { ReactCodeMirrorRef } from "@uiw/react-codemirror";
import type { Message } from "ai/react";
import { useAtom, useAtomValue } from "jotai";
import {
  BotMessageSquareIcon,
  ClockIcon,
  Loader2,
  PlusIcon,
  SendIcon,
  SettingsIcon,
  SquareIcon,
} from "lucide-react";
import {
  type Dispatch,
  memo,
  type SetStateAction,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { addMessageToChat } from "@/core/ai/chat-utils";
import {
  activeChatAtom,
  type Chat,
  type ChatState,
  chatStateAtom,
} from "@/core/ai/state";
import { getCodes } from "@/core/codemirror/copilot/getCodes";
import { aiAtom, aiEnabledAtom, userConfigAtom } from "@/core/config/config";
import type { UserConfig } from "@/core/config/config-schema";
import { saveUserConfig } from "@/core/network/requests";
import { useRuntimeManager } from "@/core/runtime/config";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { type ResolvedTheme, useTheme } from "@/theme/useTheme";
import { cn } from "@/utils/cn";
import { timeAgo } from "@/utils/dates";
import { Logger } from "@/utils/Logger";
import { generateUUID } from "@/utils/uuid";
import { KNOWN_AI_MODELS } from "../app-config/constants";
import { useOpenSettingsToTab } from "../app-config/state";
import { PromptInput } from "../editor/ai/add-cell-with-ai";
import { getAICompletionBody } from "../editor/ai/completion-utils";
import { PanelEmptyState } from "../editor/chrome/panels/empty-state";
import { CopyClipboardIcon } from "../icons/copy-icon";
import { Tooltip, TooltipProvider } from "../ui/tooltip";
import { MarkdownRenderer } from "./markdown-renderer";
import { ReasoningAccordion } from "./reasoning-accordion";

interface ChatHeaderProps {
  onNewChat: () => void;
  activeChatId: string | undefined;
  setActiveChat: (id: string | null) => void;
  chats: Chat[];
}

const ChatHeader: React.FC<ChatHeaderProps> = ({
  onNewChat,
  activeChatId,
  setActiveChat,
  chats,
}) => {
  const { handleClick } = useOpenSettingsToTab();

  return (
    <div className="flex border-b px-2 py-1 justify-between flex-shrink-0 items-center">
      <Tooltip content="New chat">
        <Button variant="text" size="icon" onClick={onNewChat}>
          <PlusIcon className="h-4 w-4" />
        </Button>
      </Tooltip>
      <div className="flex items-center gap-2">
        <Tooltip content="AI Settings">
          <Button
            variant="text"
            size="xs"
            className="hover:bg-foreground/10 py-2"
            onClick={() => handleClick("ai")}
          >
            <SettingsIcon className="h-4 w-4" />
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
                {chats.length === 0 && (
                  <PanelEmptyState
                    title="No chats yet"
                    description="Start a new chat to get started"
                    icon={<BotMessageSquareIcon />}
                  />
                )}
                {chats.map((chat) => (
                  <button
                    key={chat.id}
                    className={cn(
                      "p-3 rounded-md cursor-pointer hover:bg-accent",
                      chat.id === activeChatId && "bg-accent",
                    )}
                    onClick={() => {
                      setActiveChat(chat.id);
                    }}
                  >
                    <div className="font-medium">{chat.title}</div>
                    <div className="text-sm text-muted-foreground">
                      {timeAgo(chat.updatedAt)}
                    </div>
                  </button>
                ))}
              </div>
            </ScrollArea>
          </PopoverContent>
        </Popover>
      </div>
    </div>
  );
};

interface ChatMessageProps {
  message: Message;
  index: number;
  theme: ResolvedTheme;
  onEdit: (index: number, newValue: string) => void;
  setChatState: Dispatch<SetStateAction<ChatState>>;
  chatState: ChatState;
  isStreamingReasoning: boolean;
  totalMessages: number;
}

const ChatMessage: React.FC<ChatMessageProps> = memo(
  ({
    message,
    index,
    theme,
    onEdit,
    setChatState,
    chatState,
    isStreamingReasoning,
    totalMessages,
  }) => (
    <div
      className={cn(
        "flex group relative",
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
              onEdit(index, newValue);
            }}
            onClose={() => {
              // noop
            }}
          />
        </div>
      ) : (
        <div className="w-[95%]">
          <div className="absolute right-1 top-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <CopyClipboardIcon className="h-3 w-3" value={message.content} />
          </div>
          {message.parts?.map((part, i) => {
            switch (part.type) {
              case "text":
                return <MarkdownRenderer key={i} content={part.text} />;

              case "reasoning":
                return (
                  <ReasoningAccordion
                    reasoning={part.reasoning}
                    key={i}
                    index={i}
                    isStreaming={
                      index === totalMessages - 1 && isStreamingReasoning
                    }
                  />
                );

              /* handle other part types … */
              default:
                return null;
            }
          })}
        </div>
      )}
    </div>
  ),
);
ChatMessage.displayName = "ChatMessage";

interface ChatInputFooterProps {
  input: string;
  onSendClick: () => void;
  isLoading: boolean;
  onStop: () => void;
}

const ChatInputFooter: React.FC<ChatInputFooterProps> = memo(
  ({ input, onSendClick, isLoading, onStop }) => {
    const ai = useAtomValue(aiAtom);
    const [userConfig, setUserConfig] = useAtom(userConfigAtom);
    // const currentMode = ai?.mode || "manual";
    const currentModel = ai?.open_ai?.model || "o4-mini";

    // const modeOptions = [
    //   {
    //     value: "ask",
    //     label: "Ask",
    //     subtitle: "Read-only tools",
    //   },
    //   {
    //     value: "manual",
    //     label: "Manual",
    //     subtitle: "No tools",
    //   },
    // ];

    // const handleModeChange = async (newMode: "ask" | "manual") => {
    //   const newConfig: UserConfig = {
    //     ...userConfig,
    //     ai: {
    //       ...userConfig.ai,
    //       mode: newMode,
    //     },
    //   };
    //   saveConfig(newConfig);
    // };

    const handleModelChange = async (newModel: string) => {
      const newConfig: UserConfig = {
        ...userConfig,
        ai: {
          ...userConfig.ai,
          open_ai: {
            ...userConfig.ai?.open_ai,
            model: newModel,
          },
        },
      };
      saveConfig(newConfig);
    };

    const saveConfig = async (newConfig: UserConfig) => {
      await saveUserConfig({ config: newConfig }).then(() => {
        setUserConfig(newConfig);
      });
    };

    return (
      <div className="px-3 py-2 border-t border-border/20 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* TODO: ADD BACK ONCE THERE ARE TOOLS FOR ASK MODE */}
          {/* <Select value={currentMode} onValueChange={handleModeChange}>
            <SelectTrigger className="h-6 text-xs border-border !shadow-none !ring-0 bg-muted hover:bg-muted/30 py-0 px-2 gap-1">
              <SelectValue placeholder="manual" />
            </SelectTrigger>
            <SelectContent>
              {modeOptions.map((option) => (
                <SelectItem 
                  key={option.value}
                  value={option.value} 
                  className="text-xs" 
                  subtitle={<div className="text-muted-foreground text-xs pl-2">{option.subtitle}</div>}
                >
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select> */}
          <Select value={currentModel} onValueChange={handleModelChange}>
            <SelectTrigger className="h-6 text-xs border-border !shadow-none !ring-0 bg-muted hover:bg-muted/30 py-0 px-2 gap-1">
              <SelectValue placeholder="Model" />
            </SelectTrigger>
            <SelectContent>
              {/* Show current model if it's not in the known models list */}
              {!(KNOWN_AI_MODELS as readonly string[]).includes(
                currentModel,
              ) && (
                <SelectItem
                  key={currentModel}
                  value={currentModel}
                  className="text-sm"
                >
                  {currentModel}
                </SelectItem>
              )}
              {KNOWN_AI_MODELS.map((model) => (
                <SelectItem key={model} value={model} className="text-sm">
                  {model}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="h-6 w-6 p-0 hover:bg-muted/30"
          onClick={isLoading ? onStop : onSendClick}
          disabled={isLoading ? false : !input.trim()}
        >
          {isLoading ? (
            <SquareIcon className="h-3 w-3 fill-current" />
          ) : (
            <SendIcon className="h-3 w-3" />
          )}
        </Button>
      </div>
    );
  },
);

ChatInputFooter.displayName = "ChatInputFooter";

interface ChatInputProps {
  input: string;
  setInput: (value: string) => void;
  onSubmit: (e: KeyboardEvent | undefined, value: string) => void;
  theme: ResolvedTheme;
  inputRef: React.RefObject<ReactCodeMirrorRef | null>;
  isLoading: boolean;
  onStop: () => void;
}

const ChatInput: React.FC<ChatInputProps> = memo(
  ({ input, setInput, onSubmit, theme, inputRef, isLoading, onStop }) => {
    const handleSendClick = () => {
      if (input.trim()) {
        onSubmit(undefined, input);
      }
    };

    return (
      <div className="border-t relative flex-shrink-0 min-h-[80px] flex flex-col">
        <div className="px-2 py-3 flex-1">
          <PromptInput
            value={input}
            onChange={setInput}
            onSubmit={onSubmit}
            onClose={() => inputRef.current?.editor?.blur()}
            theme={theme}
            placeholder="Type your message..."
          />
        </div>
        <ChatInputFooter
          input={input}
          onSendClick={handleSendClick}
          isLoading={isLoading}
          onStop={onStop}
        />
      </div>
    );
  },
);

ChatInput.displayName = "ChatInput";

export const ChatPanel = () => {
  const aiEnabled = useAtomValue(aiEnabledAtom);
  const { handleClick } = useOpenSettingsToTab();

  if (!aiEnabled) {
    return (
      <PanelEmptyState
        title="Chat with AI"
        description="AI is currently disabled. Add your API key to enable."
        action={
          <Button variant="outline" size="sm" onClick={() => handleClick("ai")}>
            Edit AI settings
          </Button>
        }
        icon={<BotMessageSquareIcon />}
      />
    );
  }

  return <ChatPanelBody />;
};

const ChatPanelBody = () => {
  const [chatState, setChatState] = useAtom(chatStateAtom);
  const [activeChat, setActiveChat] = useAtom(activeChatAtom);
  const [newThreadInput, setNewThreadInput] = useState("");
  const newThreadInputRef = useRef<ReactCodeMirrorRef>(null);
  const newMessageInputRef = useRef<ReactCodeMirrorRef>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();
  const runtimeManager = useRuntimeManager();

  const {
    messages,
    input,
    setInput,
    setMessages,
    append,
    handleSubmit,
    error,
    status,
    reload,
    stop,
  } = useChat({
    id: activeChat?.id,
    initialMessages: useMemo(() => {
      return activeChat
        ? activeChat.messages.map(({ role, content, timestamp, parts }) => ({
            role,
            content,
            id: timestamp.toString(),
            parts,
          }))
        : [];
    }, [activeChat]),
    keepLastMessageOnError: true,
    // Throttle the messages and data updates to 100ms
    experimental_throttle: 100,
    api: runtimeManager.getAiURL("chat").toString(),
    headers: runtimeManager.headers(),
    experimental_prepareRequestBody: (options) => {
      return {
        ...options,
        ...getAICompletionBody({
          input: options.messages.map((m) => m.content).join("\n"),
        }),
        includeOtherCode: getCodes(""),
      };
    },
    onFinish: (message) => {
      setChatState((prev) =>
        addMessageToChat(
          prev,
          prev.activeChatId,
          "assistant",
          message.content,
          message.parts,
        ),
      );
    },
    onToolCall: (_toolCall) => {
      // Logger.warn("Tool call:", toolCall);
      // TODO: Handle tool calls
    },
    onError: (error) => {
      Logger.error("An error occurred:", error);
    },
    onResponse: (response) => {
      Logger.debug("Received HTTP response from server:", response);
    },
  });

  const isLoading = status === "submitted" || status === "streaming";

  const isLastMessageReasoning = (messages: Message[]): boolean => {
    if (messages.length === 0) {
      return false;
    }

    const lastMessage = messages.at(-1);
    if (!lastMessage) {
      return false;
    }

    if (lastMessage.role !== "assistant" || !lastMessage.parts) {
      return false;
    }

    const parts = lastMessage.parts;
    if (parts.length === 0) {
      return false;
    }

    // Check if the last part is reasoning
    const lastPart = parts[parts.length - 1];
    return lastPart.type === "reasoning";
  };

  // Check if we're currently streaming reasoning in the latest message
  const isStreamingReasoning =
    isLoading && messages.length > 0 && isLastMessageReasoning(messages);

  // Scroll to the latest chat message at the bottom
  useEffect(() => {
    const scrollToBottom = () => {
      if (scrollContainerRef.current) {
        const container = scrollContainerRef.current;
        container.scrollTop = container.scrollHeight;
      }
    };

    requestAnimationFrame(scrollToBottom);
  }, [chatState.activeChatId]);

  const createNewThread = (initialMessage: string) => {
    const newChat: Chat = {
      id: generateUUID(),
      title: `${initialMessage.slice(0, 30)}...`,
      messages: [
        {
          role: "user",
          content: initialMessage,
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

    setInput("");
    append({
      role: "user",
      content: initialMessage,
    });
  };

  const handleNewChat = () => {
    setActiveChat(null);
    setInput("");
    setNewThreadInput("");
  };

  const handleMessageEdit = (index: number, newValue: string) => {
    // Truncate both useChat and storage
    setMessages((messages) => messages.slice(0, index));
    if (chatState.activeChatId) {
      setChatState((prev) => ({
        ...prev,
        chats: prev.chats.map((chat) =>
          chat.id === chatState.activeChatId
            ? {
                ...chat,
                messages: chat.messages.slice(0, index),
                updatedAt: Date.now(),
              }
            : chat,
        ),
      }));
    }

    // Add user message to useChat and storage
    append({
      role: "user",
      content: newValue,
    });
    if (chatState.activeChatId) {
      setChatState((prev) =>
        addMessageToChat(prev, chatState.activeChatId, "user", newValue),
      );
    }
  };

  const handleChatInputSubmit = (
    e: KeyboardEvent | undefined,
    newValue: string,
  ): void => {
    if (!newValue.trim()) {
      return;
    }
    handleSubmit(e);
    if (chatState.activeChatId) {
      setChatState((prev) =>
        addMessageToChat(prev, chatState.activeChatId, "user", newValue),
      );
    }
  };

  const handleReload = () => {
    reload();
  };

  const handleNewThreadSubmit = () => {
    newThreadInput.trim() && createNewThread(newThreadInput.trim());
  };

  const handleOnCloseThread = () => newThreadInputRef.current?.editor?.blur();

  return (
    <div className="flex flex-col h-[calc(100%-53px)]">
      <TooltipProvider>
        <ChatHeader
          onNewChat={handleNewChat}
          activeChatId={activeChat?.id}
          setActiveChat={setActiveChat}
          chats={chatState.chats}
        />
      </TooltipProvider>

      <div
        className="flex-1 px-3 bg-[var(--slate-1)] gap-4 py-3 flex flex-col overflow-y-auto"
        ref={scrollContainerRef}
      >
        {(!messages || messages.length === 0) && (
          <div className="flex flex-col rounded-md border bg-background">
            <div className="px-1">
              <PromptInput
                key="new-thread-input"
                value={newThreadInput}
                placeholder="Ask anything, @ to include context about tables or dataframes"
                theme={theme}
                onClose={handleOnCloseThread}
                onChange={setNewThreadInput}
                onSubmit={handleNewThreadSubmit}
              />
            </div>
            <ChatInputFooter
              input={newThreadInput}
              onSendClick={handleNewThreadSubmit}
              isLoading={isLoading}
              onStop={stop}
            />
          </div>
        )}

        {messages.map((message, idx) => (
          <ChatMessage
            key={idx}
            message={message}
            index={idx}
            theme={theme}
            onEdit={handleMessageEdit}
            setChatState={setChatState}
            chatState={chatState}
            isStreamingReasoning={isStreamingReasoning}
            totalMessages={messages.length}
          />
        ))}

        {isLoading && (
          <div className="flex justify-center py-4">
            <Loader2 className="h-4 w-4 animate-spin" />
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center space-x-2 mb-4">
            <ErrorBanner error={error} />
            <Button variant="outline" size="sm" onClick={handleReload}>
              Retry
            </Button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {isLoading && (
        <div className="w-full flex justify-center items-center z-20 border-t">
          <Button variant="linkDestructive" size="sm" onClick={stop}>
            Stop
          </Button>
        </div>
      )}

      {messages && messages.length > 0 && (
        <ChatInput
          input={input}
          setInput={setInput}
          onSubmit={handleChatInputSubmit}
          theme={theme}
          inputRef={newMessageInputRef}
          isLoading={isLoading}
          onStop={stop}
        />
      )}
    </div>
  );
};
